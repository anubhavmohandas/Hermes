#!/usr/bin/env python3
"""
mnemos/memory_index.py — MEMORY.md index cap enforcement.

Pattern source (reimplemented fresh, no code copied): CC_SRC_PATTERNS.md
Pattern #6 — MEMORY.md hard caps + truncation.
  MAX_ENTRYPOINT_LINES = 200
  MAX_ENTRYPOINT_BYTES = 25_000
  Truncation order: lines first (natural boundary), then bytes at the last
  newline before the cap. Both caps are checked against the ORIGINAL content
  before truncation — this is what catches "200 short lines = fine, 200 long
  lines = 40KB+" as a distinct failure mode from the line-count cap alone.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meta.paths import state_file  # noqa: E402

MAX_LINES = 200
MAX_BYTES = 25_000

# The index is the user's memory, so it moves with the vault (meta/paths.py)
# instead of sitting in the plugin dir where an update deletes it.
DEFAULT_INDEX_PATH = state_file("mnemos", "vault", "MEMORY.md")


def enforce_caps(content: str):
    """
    Returns (final_content: str, truncated: bool, warning: str|None).
    Mirrors the exact two-stage cap logic: line cap first, then byte cap
    re-checked against what's left after the line cap (catches long-line case).
    """
    original_lines = content.splitlines(keepends=True)
    original_bytes = len(content.encode("utf-8"))

    truncated = False
    reasons = []

    lines = original_lines
    if len(original_lines) > MAX_LINES:
        lines = original_lines[:MAX_LINES]
        truncated = True
        reasons.append(f"line cap ({len(original_lines)} lines > {MAX_LINES})")

    working = "".join(lines)
    working_bytes = working.encode("utf-8")
    if len(working_bytes) > MAX_BYTES:
        # Truncate at the last newline before the byte cap — never cut mid-line.
        clipped = working_bytes[:MAX_BYTES]
        last_nl = clipped.rfind(b"\n")
        if last_nl == -1:
            clipped = b""
        else:
            clipped = clipped[:last_nl + 1]
        working = clipped.decode("utf-8", errors="ignore")
        truncated = True
        reasons.append(f"byte cap ({len(working_bytes)} bytes > {MAX_BYTES})")

    warning = None
    if truncated:
        reason_str = " and ".join(reasons)
        warning = (
            f"WARNING: MEMORY.md is over the {reason_str.split(' (')[0]}. "
            f"Only part of it was loaded ({reason_str}). "
            f"Keep index entries to one line under ~200 chars; move detail into topic files."
        )
        working = working + f"\n<!-- {warning} -->\n"

    return working, truncated, warning


def read_memory_index(path: Path = DEFAULT_INDEX_PATH):
    if not path.exists():
        return "", False, None
    content = path.read_text()
    final_content, truncated, warning = enforce_caps(content)
    return final_content, truncated, warning


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: memory_index.py check <path>", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "check":
        path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_INDEX_PATH
        content, truncated, warning = read_memory_index(path)
        print(f"lines={len(content.splitlines())} bytes={len(content.encode('utf-8'))} truncated={truncated}")
        if warning:
            print(warning)
        sys.exit(1 if truncated else 0)
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)
