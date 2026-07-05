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
import ipaddress
import re
import sys

BLOCK_PATTERNS = [
    (r"\brm\s+-rf\s+/(?:\s|$)", "rm -rf / — wipes root filesystem"),
    (r"\bdd\s+if=.*\s+of=/dev/(sd|nvme|disk)", "dd to raw disk device — destroys disk"),
    (r"\bmkfs(\.\w+)?\s+/dev/", "mkfs on device — reformats disk"),
    (r">\s*/dev/(sd|nvme|disk)", "raw write to disk device"),
]

# Closed 2026-07-05 (audit finding), hardened same day (live-test follow-up):
# url_safety.py's SSRF guard only ran on webfetch/fetch/websearch tool
# inputs — a shell network tool (curl, wget, nc...) aimed at the cloud
# metadata endpoint or the wider 169.254.0.0/16 link-local range sailed
# through this module's denylist untouched. First pass was a single
# tool-then-target regex; that missed two things a live probe would hit:
#   1. Order independence — `IP=169.254.169.254; curl $IP` puts the literal
#      BEFORE the tool name, so a regex requiring tool-then-target misses it.
#      Fixed by checking "network tool anywhere" AND "target anywhere" as
#      two independent searches, not one ordered pattern.
#   2. Decimal-encoded IPs — 169.254.169.254 written as the plain integer
#      2852039166 (`curl http://2852039166/`) never matches a dotted-quad
#      regex at all. Fixed by scanning standalone 7-10 digit tokens and
#      converting each candidate through ipaddress to see if it lands in the
#      link-local range.
# Still NOT covered (documented limitation, not silently missed): octal/hex
# IP notation (0251.0376.0251.0376, 0xA9FEA9FE), and hostnames that resolve
# to a blocked IP only at DNS time. The durable fix for those is extracting
# hosts from Bash commands and resolving them through url_safety.py itself,
# same as fetcher/fetch.py does — not implemented, out of scope for this pass.
_NETWORK_TOOL_RE = re.compile(r"\b(curl|wget|nc|ncat|telnet|ftp)\b", re.IGNORECASE)
_METADATA_TARGET_RE = re.compile(
    r"(169\.254\.\d{1,3}\.\d{1,3}|::ffff:169\.254\.\d{1,3}\.\d{1,3}|"
    r"fe80::[0-9a-fA-F:]*|metadata\.google\.internal|metadata\.azure\.com|"
    r"100\.100\.100\.200)",
    re.IGNORECASE,
)
_STANDALONE_NUMBER_RE = re.compile(r"\b\d{7,10}\b")


def _decimal_token_is_link_local(token: str) -> bool:
    """A bare 32-bit integer written where an IP could be interpreted as one
    (curl accepts http://2852039166/ and treats it as an IP). Only flags it
    if converting lands in the link-local range (169.254.0.0/16, which
    includes the AWS/GCP/Azure metadata IP) — narrow on purpose, so an
    ordinary large number (a timestamp, a PID) in an unrelated command
    doesn't false-positive unless it happens to decode into that exact
    /16, which is astronomically unlikely by accident."""
    try:
        n = int(token)
    except ValueError:
        return False
    if not (0 <= n <= 0xFFFFFFFF):
        return False
    return ipaddress.ip_address(n).is_link_local


def _bash_network_ssrf_check(cmd: str):
    """Returns a block reason string, or None if this specific check doesn't
    fire. Separate from the regex BLOCK_PATTERNS list because it needs
    order-independent matching and integer decoding, not a single pattern."""
    if not _NETWORK_TOOL_RE.search(cmd):
        return None
    if _METADATA_TARGET_RE.search(cmd):
        return "network tool aimed at cloud metadata / link-local endpoint — SSRF"
    for token in _STANDALONE_NUMBER_RE.findall(cmd):
        if _decimal_token_is_link_local(token):
            return (f"network tool aimed at a decimal-encoded metadata/"
                    f"link-local address ({token}) — SSRF")
    return None


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
    ssrf_reason = _bash_network_ssrf_check(cmd)
    if ssrf_reason:
        return "block", f"BLOCKED: {ssrf_reason}"
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
