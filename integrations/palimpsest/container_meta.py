#!/usr/bin/env python3
"""
integrations/palimpsest/container_meta.py — OOXML (docx/xlsx/pptx), PDF,
HTML, Markdown and SVG metadata/watermark stripping.

Pattern source (reimplemented fresh, no code copied): a third-party
watermark-removal project's container cleaners. See image_meta.py's
docstring for the same disclosure pattern this file follows: state what's
covered, name what isn't, never fake a result.

Key simplification vs. the source project (an actual improvement, not just
a port): OOXML/HTML/Markdown/SVG are all text-based XML-ish formats where
every Layer-A carrier codepoint (zero-width space, bidi override, tag
chars, ...) is non-ASCII and structurally inert — none of them are `<`,
`>`, `&`, `"`, `'`, or `=`. That means text_unicode.clean_text() can run
over an ENTIRE XML/HTML/Markdown member safely, with no tag-aware parsing
needed, and it cannot corrupt markup. The source project instead extracts
and rewrites individual `<w:t>`/`<a:t>` text runs with dedicated regexes
per format. This file does the simpler thing and gets the same coverage
for invisible-Unicode carriers; entity-encoded carriers (`&#8203;` etc.)
get one shared regex pass (text_unicode.clean_entity_references) instead
of a per-format decode/re-encode cycle.

What this file does NOT do: it does not rewrite visible document text, does
not touch embedded media, and for PDF it does not perform a structural
rebuild — see clean_pdf()'s docstring for the honest limits of a stdlib,
no-qpdf byte-level pass.
"""

from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path

from text_unicode import clean_entity_references, clean_text

# Zip-bomb guard: refuse to process an archive whose *declared* uncompressed
# size is absurd relative to a document. This is a sanity cap, not a
# security boundary on its own — HERMES's meta/security layer covers the
# rest of the write path.
MAX_UNCOMPRESSED_BYTES = 300 * 1024 * 1024


def detect_container_format(path: Path, data: bytes) -> str:
    ext = path.suffix.lower()
    if ext in (".docx", ".xlsx", ".pptx"):
        return ext[1:]
    if ext == ".pdf":
        return "pdf"
    if ext in (".html", ".htm"):
        return "html"
    if ext in (".md", ".markdown", ".mdx"):
        return "markdown"
    if ext == ".svg":
        return "svg"

    if data.startswith(b"%PDF-"):
        return "pdf"
    if data[:4] == b"PK\x03\x04":
        try:
            names = set(zipfile.ZipFile(BytesIO(data)).namelist())
        except zipfile.BadZipFile:
            return "unknown"
        if "word/document.xml" in names:
            return "docx"
        if "xl/workbook.xml" in names:
            return "xlsx"
        if "ppt/presentation.xml" in names:
            return "pptx"
        return "unknown"
    head = data[:4096].lstrip()
    if head[:1] == b"<" and (b"<svg" in head.lower()[:200]):
        return "svg"
    if b"<html" in head.lower() or b"<!doctype html" in head.lower():
        return "html"
    return "unknown"


# ---------------------------------------------------------------------
# OOXML (docx / xlsx / pptx)
# ---------------------------------------------------------------------

_BINARY_MEMBER_RE = re.compile(
    r"(^|/)media/.*\.(png|jpe?g|gif|bmp|emf|wmf|tiff?|webp|ico|bin)$", re.IGNORECASE
)

_CORE_PROPS_TO_BLANK = (
    "dc:creator", "cp:lastModifiedBy", "dc:title", "dc:subject",
    "dc:description", "cp:keywords", "cp:category", "cp:contentStatus",
)
_APP_PROPS_TO_BLANK = ("Application", "AppVersion", "Company", "Manager", "HyperlinkBase")


def _blank_tags(xml_text: str, tags: tuple[str, ...]) -> tuple[str, int]:
    count = 0
    for tag in tags:
        pattern = re.compile(rf"(<{re.escape(tag)}(?:\s[^>]*)?>)([^<]*)(</{re.escape(tag)}>)")

        def _sub(m: re.Match) -> str:
            nonlocal count
            if m.group(2):
                count += 1
            return m.group(1) + m.group(3)

        xml_text = pattern.sub(_sub, xml_text)
    return xml_text, count


_VT_LEAF_RE = re.compile(r"(<vt:\w+(?:\s[^>]*)?>)([^<]*)(</vt:\w+>)")


def _blank_custom_props(xml_text: str) -> tuple[str, int]:
    count = 0

    def _sub(m: re.Match) -> str:
        nonlocal count
        if m.group(2):
            count += 1
        return m.group(1) + m.group(3)

    return _VT_LEAF_RE.sub(_sub, xml_text), count


def clean_ooxml(data: bytes) -> tuple[bytes, list[str]]:
    src = zipfile.ZipFile(BytesIO(data))
    if sum(zi.file_size for zi in src.infolist()) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("archive exceeds Palimpsest's uncompressed-size guard")

    actions: list[str] = []
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for zi in src.infolist():
            raw = src.read(zi.filename)
            name = zi.filename

            if name == "docProps/core.xml":
                try:
                    text = raw.decode("utf-8")
                    text, n = _blank_tags(text, _CORE_PROPS_TO_BLANK)
                    if n:
                        actions.append(f"blanked {n} identifying field(s) in docProps/core.xml")
                    raw = text.encode("utf-8")
                except UnicodeDecodeError:
                    pass
            elif name == "docProps/app.xml":
                try:
                    text = raw.decode("utf-8")
                    text, n = _blank_tags(text, _APP_PROPS_TO_BLANK)
                    if n:
                        actions.append(f"blanked {n} field(s) in docProps/app.xml")
                    raw = text.encode("utf-8")
                except UnicodeDecodeError:
                    pass
            elif name == "docProps/custom.xml":
                try:
                    text = raw.decode("utf-8")
                    text, n = _blank_custom_props(text)
                    if n:
                        actions.append(f"blanked {n} custom propert{'y' if n == 1 else 'ies'}")
                    raw = text.encode("utf-8")
                except UnicodeDecodeError:
                    pass
            elif name.lower().endswith((".xml", ".rels")) and not _BINARY_MEMBER_RE.search(name):
                try:
                    text = raw.decode("utf-8")
                    text, n_entity = clean_entity_references(text)
                    text, stats = clean_text(text)
                    n = n_entity + stats["removed_count"] + stats["replaced_count"]
                    if n:
                        actions.append(f"stripped {n} invisible-Unicode carrier(s) from {name}")
                    raw = text.encode("utf-8")
                except UnicodeDecodeError:
                    pass

            dst.writestr(zi, raw)

    return buf.getvalue(), actions


# ---------------------------------------------------------------------
# PDF — best-effort byte-level pass (no qpdf dependency, no structural
# rebuild). Same-length in-place blanking keeps the file's byte offsets
# (and therefore its xref table) valid without re-parsing the whole
# object graph.
# ---------------------------------------------------------------------

_PDF_INFO_KEYS = (b"/Title", b"/Author", b"/Subject", b"/Keywords", b"/Creator", b"/Producer")


def _find_literal_string_span(data: bytes, start: int) -> tuple[int, int] | None:
    """Given *start* pointing at the '(' of a PDF literal string, return
    (content_start, content_end) — the span strictly inside the parens,
    honoring backslash escapes and balanced nested parens (PDF spec 7.3.4.2)."""
    if start >= len(data) or data[start:start + 1] != b"(":
        return None
    i = start + 1
    depth = 1
    n = len(data)
    while i < n:
        c = data[i:i + 1]
        if c == b"\\":
            i += 2
            continue
        if c == b"(":
            depth += 1
        elif c == b")":
            depth -= 1
            if depth == 0:
                return start + 1, i
        i += 1
    return None


def _blank_info_dict_strings(data: bytearray) -> int:
    count = 0
    for key in _PDF_INFO_KEYS:
        pos = 0
        while True:
            idx = bytes(data).find(key, pos)
            if idx == -1:
                break
            paren = bytes(data).find(b"(", idx, idx + 40)
            hexstr = bytes(data).find(b"<", idx, idx + 40)
            if paren != -1 and (hexstr == -1 or paren < hexstr):
                span = _find_literal_string_span(bytes(data), paren)
                if span:
                    cstart, cend = span
                    if cend > cstart:
                        data[cstart:cend] = b" " * (cend - cstart)
                        count += 1
                    pos = cend
                    continue
            elif hexstr != -1:
                end = bytes(data).find(b">", hexstr)
                if end != -1 and end > hexstr + 1:
                    data[hexstr + 1:end] = b"0" * (end - hexstr - 1)
                    count += 1
                    pos = end
                    continue
            pos = idx + len(key)
    return count


def _blank_xmp_packet(data: bytearray) -> bool:
    raw = bytes(data)
    begin = raw.find(b"<?xpacket begin=")
    if begin == -1:
        return False
    begin_pi_end = raw.find(b"?>", begin)
    end_pi = raw.find(b"<?xpacket end=", begin)
    if begin_pi_end == -1 or end_pi == -1 or end_pi <= begin_pi_end:
        return False
    content_start = begin_pi_end + 2
    content_end = end_pi
    if content_end <= content_start:
        return False
    # XMP packets are spec-designed to tolerate padding whitespace inside
    # the packet for exactly this kind of in-place edit.
    data[content_start:content_end] = b" " * (content_end - content_start)
    return True


def clean_pdf(data: bytes) -> tuple[bytes, list[str]]:
    """Best-effort PDF metadata blank. Honest limits:

    - Only finds /Info dictionary entries and an XMP packet stored as
      *plain, uncompressed* bytes in the file. A PDF 1.5+ file that packs
      its Info dict into a compressed cross-reference/object stream
      (uncommon for /Info, common for xref) will not be touched here —
      this function reports zero actions rather than a false positive.
    - Does not rebuild the object/xref graph, so it cannot remove a
      /Metadata stream entirely, only blank its visible content in place.
    A full structural rewrite needs a real PDF library (pikepdf) or the
    external qpdf binary — neither is a stdlib dependency, so neither is
    silently assumed present here.
    """
    buf = bytearray(data)
    actions: list[str] = []
    n_info = _blank_info_dict_strings(buf)
    if n_info:
        actions.append(f"blanked {n_info} /Info dictionary string(s)")
    if _blank_xmp_packet(buf):
        actions.append("blanked XMP metadata packet content")
    if not actions and b"/ObjStm" in data:
        actions.append(
            "no plain-text Info/XMP fields found; this PDF may store metadata in a "
            "compressed object stream (PDF 1.5+) — a structural tool (e.g. qpdf/pikepdf) "
            "would be needed to reach it"
        )
    return bytes(buf), actions


# ---------------------------------------------------------------------
# HTML / Markdown / SVG
# ---------------------------------------------------------------------

_GENERATOR_META_RE = re.compile(
    r"<meta\s+[^>]*name\s*=\s*[\"']generator[\"'][^>]*>\s*", re.IGNORECASE
)
_SIGNATURE_COMMENT_RE = re.compile(
    r"<!--(?:(?!-->).)*?(generated by|powered by|claude|chatgpt|gpt-\d|gemini|copilot)"
    r"(?:(?!-->).)*?-->",
    re.IGNORECASE | re.DOTALL,
)
_SVG_METADATA_BLOCK_RE = re.compile(r"<metadata\b[^>]*>.*?</metadata>", re.IGNORECASE | re.DOTALL)
_RDF_BLOCK_RE = re.compile(r"<rdf:RDF\b[^>]*>.*?</rdf:RDF>", re.IGNORECASE | re.DOTALL)


def _layer_a_pass(text: str) -> tuple[str, int]:
    text, n_entity = clean_entity_references(text)
    text, stats = clean_text(text)
    return text, n_entity + stats["removed_count"] + stats["replaced_count"]


def clean_html(text: str) -> tuple[str, list[str]]:
    actions: list[str] = []
    text, n_meta = _GENERATOR_META_RE.subn("", text)
    if n_meta:
        actions.append(f"removed {n_meta} <meta name=generator> tag(s)")
    text, n_comment = _SIGNATURE_COMMENT_RE.subn("", text)
    if n_comment:
        actions.append(f"removed {n_comment} generator/signature comment(s)")
    text, n_layer_a = _layer_a_pass(text)
    if n_layer_a:
        actions.append(f"stripped {n_layer_a} invisible-Unicode carrier(s)")
    return text, actions


def clean_markdown(text: str) -> tuple[str, list[str]]:
    actions: list[str] = []
    text, n_comment = _SIGNATURE_COMMENT_RE.subn("", text)
    if n_comment:
        actions.append(f"removed {n_comment} generator/signature comment(s)")
    text, n_layer_a = _layer_a_pass(text)
    if n_layer_a:
        actions.append(f"stripped {n_layer_a} invisible-Unicode carrier(s)")
    return text, actions


def clean_svg(data: bytes) -> tuple[bytes, list[str]]:
    text = data.decode("utf-8", errors="surrogateescape")
    actions: list[str] = []
    text, n_meta = _SVG_METADATA_BLOCK_RE.subn("", text)
    if n_meta:
        actions.append(f"removed {n_meta} <metadata> block(s)")
    text, n_rdf = _RDF_BLOCK_RE.subn("", text)
    if n_rdf:
        actions.append(f"removed {n_rdf} RDF metadata block(s)")
    text, n_layer_a = _layer_a_pass(text)
    if n_layer_a:
        actions.append(f"stripped {n_layer_a} invisible-Unicode carrier(s)")
    return text.encode("utf-8", errors="surrogateescape"), actions
