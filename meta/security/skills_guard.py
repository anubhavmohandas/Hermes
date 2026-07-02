#!/usr/bin/env python3
"""
skills_guard.py — Layer 4/7: static analysis on skill installs.
Every new/modified skill file is scanned before activation. Findings block
activation; the skill lands in a quarantine state instead.
Reimplemented fresh from pattern (hermes-agent P16). No source copied.
"""
import re
import sys
from pathlib import Path

DANGEROUS_PATTERNS = [
    (r"\beval\s*\(", "eval() — arbitrary code execution"),
    (r"\bexec\s*\(", "exec() — arbitrary code execution"),
    (r"os\.system\s*\(", "os.system() — shell injection risk"),
    (r"subprocess\.\w+\([^)]*shell\s*=\s*True", "subprocess with shell=True — injection risk"),
    (r"curl\s+[^\n|]*\|\s*(ba)?sh", "curl | sh — remote code execution pattern"),
    (r"wget\s+[^\n|]*\|\s*(ba)?sh", "wget | sh — remote code execution pattern"),
    (r"base64\s+-d.*\|\s*(ba)?sh", "base64 decode piped to shell — obfuscated execution"),
    (r"rm\s+-rf\s+/(?!\S)", "rm -rf / — destructive root wipe"),
    (r"chmod\s+777", "chmod 777 — world-writable permissions"),
    (r":\(\)\{.*\};:", "fork bomb pattern"),
    (r"\bimport\s+socket\b.*\bconnect\b", "raw socket connect — possible exfil channel"),
    (r"os\.environ\s*\[.*(KEY|SECRET|TOKEN)", "reads secret env vars — flag for review"),
]
_COMPILED = [(re.compile(p, re.IGNORECASE | re.DOTALL), desc) for p, desc in DANGEROUS_PATTERNS]


def scan_skill_text(text: str):
    """Returns list of (pattern_desc, matched_snippet) findings. Empty list = clean."""
    findings = []
    for pattern, desc in _COMPILED:
        m = pattern.search(text)
        if m:
            snippet = m.group(0)[:80]
            findings.append((desc, snippet))
    return findings


def scan_skill_path(path: str):
    p = Path(path)
    if not p.exists():
        return False, [("error", f"path does not exist: {path}")]
    if p.is_dir():
        all_findings = []
        for f in p.rglob("*"):
            if f.is_file() and f.suffix in (".py", ".sh", ".md", ".js", ".ts"):
                try:
                    text = f.read_text(errors="ignore")
                except Exception:
                    continue
                for desc, snippet in scan_skill_text(text):
                    all_findings.append((f"{f.relative_to(p)}: {desc}", snippet))
        return (len(all_findings) == 0), all_findings
    else:
        text = p.read_text(errors="ignore")
        findings = scan_skill_text(text)
        return (len(findings) == 0), findings


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: skills_guard.py <skill_path>", file=sys.stderr)
        sys.exit(2)
    clean, findings = scan_skill_path(sys.argv[1])
    if clean:
        print("CLEAN — no dangerous patterns found")
        sys.exit(0)
    print(f"QUARANTINE — {len(findings)} finding(s):")
    for desc, snippet in findings:
        print(f"  - {desc} :: {snippet!r}")
    sys.exit(1)
