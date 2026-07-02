#!/usr/bin/env python3
"""
tirith_security.py — Layer 6/7: pre-exec binary scanner.
Named after the Tirith pattern (hermes-agent P16) — a gate that stands before
anything gets executed. Checks magic bytes vs extension, flags setuid/setgid,
flags extension/content mismatches before a file is ever run.
Reimplemented fresh from pattern. No source copied.
"""
import stat
import sys
from pathlib import Path

MAGIC_SIGNATURES = {
    b"\x7fELF": "ELF executable (Linux)",
    b"MZ": "PE executable (Windows)",
    b"\xfe\xed\xfa\xce": "Mach-O executable (macOS, 32-bit)",
    b"\xfe\xed\xfa\xcf": "Mach-O executable (macOS, 64-bit)",
    b"\xcf\xfa\xed\xfe": "Mach-O executable (macOS, 64-bit, reversed)",
    b"#!": "script with shebang",
}

TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".xml", ".html"}


def scan_binary(path: str):
    """Returns (safe: bool, findings: list[str])."""
    p = Path(path)
    findings = []
    if not p.exists():
        return False, [f"path does not exist: {path}"]

    try:
        head = p.open("rb").read(64)
    except Exception as e:
        return False, [f"could not read file: {e}"]

    detected = None
    for magic, desc in MAGIC_SIGNATURES.items():
        if head.startswith(magic):
            detected = desc
            break

    # Extension/content mismatch — a file claiming to be text but is actually a binary.
    if detected and detected != "script with shebang" and p.suffix.lower() in TEXT_EXTENSIONS:
        findings.append(f"MISMATCH: '{p.name}' has text extension '{p.suffix}' but contains {detected}")

    try:
        mode = p.stat().st_mode
        if mode & stat.S_ISUID:
            findings.append(f"setuid bit set on '{p.name}' — flag for review")
        if mode & stat.S_ISGID:
            findings.append(f"setgid bit set on '{p.name}' — flag for review")
    except Exception:
        pass

    return (len(findings) == 0), findings


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: tirith_security.py <path>", file=sys.stderr)
        sys.exit(2)
    safe, findings = scan_binary(sys.argv[1])
    if safe:
        print("CLEAN")
        sys.exit(0)
    for f in findings:
        print(f"FLAG: {f}")
    sys.exit(1)
