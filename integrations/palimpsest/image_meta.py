#!/usr/bin/env python3
"""
integrations/palimpsest/image_meta.py — PNG / JPEG ancillary-metadata
stripper (C2PA / EXIF / XMP / text-comment provenance).

Pattern source (reimplemented fresh, no code copied): a third-party
watermark-removal project's raster-metadata cleaner. Reduced scope,
disclosed not silent — see the module docstring in dispatch/__init__ for
what's covered vs. not: this file handles PNG and JPEG only. WebP, AVIF,
HEIC, BMP, GIF and TIFF each need their own container parser (RIFF,
ISOBMFF box tree, BMP/GIF-specific trailers, TIFF IFDs); porting those is
real work, not a one-line extension, so they are out of scope for this
pass rather than a rushed, unverified copy. format_route.py reports them
as "unsupported" plainly instead of pretending to clean them.

Both formats are cleaned the same way: parse into (type, payload) units,
drop the ones that only ever carry metadata, and re-serialize the rest
byte-for-byte unchanged. Nothing here touches pixel data.
"""

from __future__ import annotations

import struct
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"
JPEG_SOI = b"\xff\xd8"

# PNG ancillary chunk types that only ever carry metadata/provenance, never
# pixels or rendering-required data. tEXt/zTXt/iTXt hold arbitrary
# key/value text (generator name, prompt, C2PA-adjacent free text); eXIf is
# the PNG EXIF chunk (spec-legal since PNG third edition); tIME and dSIG
# are a timestamp and a deprecated signature chunk, respectively. Nothing
# else is touched — unknown ancillary chunks are kept, because an allow-
# list of "chunks known safe to keep" would silently drop chunks this
# module has never seen (e.g. APNG's acTL/fcTL/fdAT), which is a
# correctness bug (a broken image), not a safety win.
PNG_STRIP_CHUNKS: frozenset[bytes] = frozenset({b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME", b"dSIG"})

# JPEG marker segments that carry only metadata. APP1 (0xE1) is EXIF and/or
# XMP; APP11 (0xEB) is commonly JUMBF/C2PA; COM (0xFE) is a free-text
# comment. APP0 (JFIF) and every other APPn are left alone — some (APP14
# Adobe) carry color-transform data that changes decoded pixel colors if
# dropped.
JPEG_STRIP_MARKERS: frozenset[int] = frozenset({0xE1, 0xEB, 0xFE})
# Markers with no following length/payload (standalone).
_JPEG_NO_PAYLOAD = frozenset({0x01} | set(range(0xD0, 0xD9)))


def detect_format(data: bytes) -> str | None:
    if data.startswith(PNG_SIG):
        return "png"
    if data.startswith(JPEG_SOI):
        return "jpeg"
    return None


def clean_png(data: bytes) -> tuple[bytes, list[str]]:
    if not data.startswith(PNG_SIG):
        raise ValueError("not a PNG (bad signature)")
    out = bytearray(PNG_SIG)
    actions: list[str] = []
    pos = len(PNG_SIG)
    n = len(data)
    while pos + 8 <= n:
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk_end = pos + 8 + length + 4  # header + payload + CRC
        if chunk_end > n:
            # Truncated/corrupt tail — keep the remainder verbatim rather
            # than guess; refusing to fabricate a fix is safer than a
            # plausible-looking corrupt rewrite.
            out += data[pos:]
            break
        if ctype in PNG_STRIP_CHUNKS:
            actions.append(f"dropped PNG chunk {ctype.decode('ascii', 'replace')} ({length} bytes)")
        else:
            out += data[pos:chunk_end]
        pos = chunk_end
        if ctype == b"IEND":
            break
    return bytes(out), actions


def clean_jpeg(data: bytes) -> tuple[bytes, list[str]]:
    if not data.startswith(JPEG_SOI):
        raise ValueError("not a JPEG (bad SOI)")
    out = bytearray(JPEG_SOI)
    actions: list[str] = []
    pos = 2
    n = len(data)
    while pos + 1 < n:
        if data[pos] != 0xFF:
            # Not aligned on a marker (shouldn't happen in a well-formed
            # file at this point) — copy the remainder untouched.
            out += data[pos:]
            break
        marker = data[pos + 1]
        if marker == 0xD9:  # EOI
            out += data[pos:pos + 2]
            break
        if marker == 0xDA:  # SOS — header then entropy-coded scan data with
            # no further markers except stray 0xFF00 stuffing and RSTn;
            # copy verbatim through to EOI (or EOF if EOI is missing).
            if pos + 4 > n:
                out += data[pos:]
                break
            (seg_len,) = struct.unpack(">H", data[pos + 2:pos + 4])
            header_end = pos + 2 + seg_len
            eoi = data.find(b"\xff\xd9", header_end)
            end = eoi if eoi != -1 else n
            out += data[pos:end]
            pos = end
            continue
        if marker in _JPEG_NO_PAYLOAD:
            out += data[pos:pos + 2]
            pos += 2
            continue
        if pos + 4 > n:
            out += data[pos:]
            break
        (seg_len,) = struct.unpack(">H", data[pos + 2:pos + 4])
        seg_end = pos + 2 + seg_len
        if seg_end > n:
            out += data[pos:]
            break
        if marker in JPEG_STRIP_MARKERS:
            actions.append(f"dropped JPEG segment 0xFF{marker:02X} ({seg_len} bytes)")
        else:
            out += data[pos:seg_end]
        pos = seg_end
    return bytes(out), actions


def clean_image(data: bytes) -> dict:
    fmt = detect_format(data)
    if fmt == "png":
        cleaned, actions = clean_png(data)
    elif fmt == "jpeg":
        cleaned, actions = clean_jpeg(data)
    else:
        return {"status": "unsupported", "format": fmt, "reason": "not PNG or JPEG"}
    return {
        "status": "cleaned",
        "format": fmt,
        "data": cleaned,
        "actions": actions,
        "bytes_in": len(data),
        "bytes_out": len(cleaned),
    }


def clean_image_file(path: Path, out: Path) -> dict:
    result = clean_image(path.read_bytes())
    if result["status"] == "cleaned":
        out.write_bytes(result.pop("data"))
        result["output"] = str(out)
    return result
