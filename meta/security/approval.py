#!/usr/bin/env python3
"""
approval.py — Layer 5/7: dangerous command gate.
Classifies shell commands as safe / needs-human-approval / block.
This module NEVER auto-approves — it only classifies. As of 2026-07-02,
the "needs-human-approval" verdict is enforced as a hard block at the hook
layer (gate.py) — there is no live interactive prompt path yet. See
docs/DECISIONS.md (D1) for why, and what Option B (a real interactive path)
would require. Reimplemented fresh from pattern (hermes-agent P16). No
source copied.
"""
import re
import sys

BLOCK_PATTERNS = [
    (r"\brm\s+-rf\s+/(?:\s|$)", "rm -rf / — wipes root filesystem"),
    (r"\bdd\s+if=.*\s+of=/dev/(sd|nvme|disk)", "dd to raw disk device — destroys disk"),
    (r"\bmkfs(\.\w+)?\s+/dev/", "mkfs on device — reformats disk"),
    (r">\s*/dev/(sd|nvme|disk)", "raw write to disk device"),
    # Closed 2026-07-05 (audit finding): url_safety.py's SSRF guard only ran
    # on webfetch/fetch/websearch tool inputs — a shell network tool (curl,
    # wget, nc...) aimed at the cloud metadata endpoint or the wider
    # 169.254.0.0/16 link-local range sailed through this module's denylist
    # untouched, since it has no metadata-IP pattern at all. Mirrors the
    # "never allowed, no override" stance METADATA_HOSTS/link-local get in
    # url_safety.py — same severity, same targets, different entry point.
    (r"\b(curl|wget|nc|ncat|telnet|ftp)\b[^\n]*\b"
     r"(169\.254\.\d{1,3}\.\d{1,3}|::ffff:169\.254\.\d{1,3}\.\d{1,3}|"
     r"fe80::[0-9a-fA-F:]*|metadata\.google\.internal|metadata\.azure\.com|"
     r"100\.100\.100\.200)\b",
     "network tool aimed at cloud metadata / link-local endpoint — SSRF"),
]

APPROVAL_PATTERNS = [
    (r"\bsudo\b", "sudo — elevated privileges"),
    (r"\bgit\s+push\s+.*--force", "force push — rewrites remote history"),
    (r"\bgit\s+reset\s+--hard", "hard reset — discards local changes"),
    (r"\bchmod\s+-R\s+777", "recursive world-writable permissions"),
    (r"\bDROP\s+TABLE\b", "SQL DROP TABLE — destructive", ),
    (r"\bTRUNCATE\s+TABLE\b", "SQL TRUNCATE — destructive"),
    (r"\bcurl\b.*\|\s*(ba)?sh", "curl | sh — remote script execution"),
    (r"\bkill\s+-9\s+-1", "kill -9 -1 — kills all processes"),
    (r"\bcrontab\s+-r\b", "crontab -r — wipes all scheduled jobs"),
    (r"\b(rm|mv)\s+-rf?\s+~", "recursive op on home directory"),
]
_BLOCK = [(re.compile(p, re.IGNORECASE), d) for p, d in BLOCK_PATTERNS]
_APPROVE = [(re.compile(p, re.IGNORECASE), d) for p, d in APPROVAL_PATTERNS]


def classify_command(cmd: str):
    """Returns (verdict: 'block'|'approval'|'safe', reason: str)."""
    if not cmd:
        return "safe", "empty command"
    for pattern, desc in _BLOCK:
        if pattern.search(cmd):
            return "block", f"BLOCKED: {desc}"
    for pattern, desc in _APPROVE:
        if pattern.search(cmd):
            return "approval", f"NEEDS HUMAN APPROVAL: {desc}"
    return "safe", "no dangerous pattern matched"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: approval.py \"<command>\"", file=sys.stderr)
        sys.exit(2)
    verdict, reason = classify_command(" ".join(sys.argv[1:]))
    print(f"{verdict}: {reason}")
    sys.exit({"safe": 0, "approval": 1, "block": 2}[verdict])
