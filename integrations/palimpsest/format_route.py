#!/usr/bin/env python3
"""
integrations/palimpsest/format_route.py — single entry point: given a file
on disk, decide which pipeline (text / image / container) owns it and run
it. Named format_route.py, not dispatch.py, on purpose: HERMES already has
`delegation/dispatch.py` on the same sys.path in test_hermes.py, and a
second same-named module would shadow one of them silently.

CLI:
    python3 format_route.py <path> [--in-place] [--aggressive] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

from container_meta import (
    clean_html,
    clean_markdown,
    clean_ooxml,
    clean_pdf,
    clean_svg,
    detect_container_format,
)
from image_meta import clean_image, detect_format as detect_image_format
from text_unicode import clean_entity_references, clean_text

Kind = Literal["text", "image", "container", "unknown"]

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
CONTAINER_EXTS = {".docx", ".xlsx", ".pptx", ".pdf", ".html", ".htm", ".md", ".markdown", ".mdx", ".svg"}
# Generic source/text files Palimpsest treats as Layer-A-only. Deliberately
# NOT '*' — an unrecognized binary extension stays "unknown" and untouched
# rather than being decoded as UTF-8 and possibly mangled.
TEXT_EXTS = {
    ".txt", ".text", ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".jsonc",
    ".yaml", ".yml", ".toml", ".css", ".scss", ".csv", ".sh", ".bash",
    ".rb", ".go", ".rs", ".java", ".c", ".h", ".cpp", ".hpp", ".sql",
    ".ini", ".cfg", ".xml",
}

# Never touch these regardless of extension — a "cleaned" secrets file is
# a contradiction, not a feature. Mirrors the sensitive-path spirit of
# meta/laconic.py's DENYLIST_PATTERNS / meta/security/file_safety.py,
# reimplemented small and local rather than imported, since this module
# must keep working even if meta/security's import path isn't on sys.path
# for a given caller.
import re as _re

_DENYLIST_RE = [
    _re.compile(p, _re.IGNORECASE)
    for p in (r"\.env(\..*)?$", r"\.ssh", r"\.aws", r"\.gnupg", r"credentials",
              r"secrets", r"id_rsa", r"\.pem$", r"\.key$")
]


def is_denylisted(path: Path) -> bool:
    s = str(path)
    return any(p.search(s) for p in _DENYLIST_RE)


def classify(path: Path, data: bytes | None = None) -> Kind:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in CONTAINER_EXTS:
        return "container"
    if ext in TEXT_EXTS:
        return "text"
    if data is None:
        try:
            data = path.read_bytes()
        except OSError:
            return "unknown"
    if detect_image_format(data[:64]) is not None:
        return "image"
    if detect_container_format(path, data) != "unknown":
        return "container"
    return "unknown"


def clean_path(path: Path, *, in_place: bool = True, aggressive: bool = False) -> dict:
    """Clean *path* and, when in_place, write the result back only if it
    actually changed anything. Returns a result dict with at least
    {"status", "format"} and, on success, {"actions", "bytes_in", "bytes_out"}.
    """
    if not path.is_file():
        return {"status": "error", "reason": f"not a file: {path}"}
    if is_denylisted(path):
        return {"status": "skipped", "reason": "path matches Palimpsest's sensitive-file denylist"}

    data = path.read_bytes()
    kind = classify(path, data)

    if kind == "unknown":
        return {"status": "unsupported", "format": None, "reason": "unrecognized format"}

    if kind == "image":
        result = clean_image(data)
        if result["status"] != "cleaned":
            return result
        out_bytes = result.pop("data")
        if in_place and out_bytes != data:
            path.write_bytes(out_bytes)
        result["written"] = in_place and out_bytes != data
        return result

    if kind == "container":
        fmt = detect_container_format(path, data)
        try:
            if fmt in ("docx", "xlsx", "pptx"):
                out_bytes, actions = clean_ooxml(data)
            elif fmt == "pdf":
                out_bytes, actions = clean_pdf(data)
            elif fmt == "svg":
                out_bytes, actions = clean_svg(data)
            elif fmt == "html":
                text, actions = clean_html(data.decode("utf-8", errors="surrogateescape"))
                out_bytes = text.encode("utf-8", errors="surrogateescape")
            elif fmt == "markdown":
                text, actions = clean_markdown(data.decode("utf-8", errors="surrogateescape"))
                out_bytes = text.encode("utf-8", errors="surrogateescape")
            else:
                return {"status": "unsupported", "format": fmt, "reason": "container format not yet handled"}
        except Exception as e:  # noqa: BLE001 — never let a malformed file crash the hook
            return {"status": "error", "format": fmt, "reason": f"{type(e).__name__}: {e}"}
        changed = out_bytes != data
        if in_place and changed:
            path.write_bytes(out_bytes)
        return {
            "status": "cleaned", "format": fmt, "actions": actions,
            "bytes_in": len(data), "bytes_out": len(out_bytes), "written": in_place and changed,
        }

    # text
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"status": "unsupported", "format": "text", "reason": "not valid UTF-8 — refusing to guess"}
    text, n_entity = clean_entity_references(text)
    text, stats = clean_text(text, aggressive_confusables=aggressive)
    n = n_entity + stats["removed_count"] + stats["replaced_count"]
    out_bytes = text.encode("utf-8")
    changed = out_bytes != data
    if in_place and changed:
        path.write_bytes(out_bytes)
    actions = [f"stripped {n} invisible-Unicode carrier(s)"] if n else []
    return {
        "status": "cleaned", "format": "text", "actions": actions,
        "bytes_in": len(data), "bytes_out": len(out_bytes), "written": in_place and changed,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("path", type=Path)
    p.add_argument("--in-place", action="store_true")
    p.add_argument("--aggressive", action="store_true", help="also fold Cyrillic/fullwidth Latin confusables")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    result = clean_path(args.path, in_place=args.in_place, aggressive=args.aggressive)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{result['status']}: {result.get('format')} — {result.get('reason', result.get('actions'))}")
    return 0 if result["status"] in ("cleaned", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
