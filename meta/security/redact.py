#!/usr/bin/env python3
"""
redact.py — Layer 7/7: secret redaction.
Display/log layer ONLY — never mutates what's actually stored in memory or
sent to a model; this scrubs what gets written to logs and printed to the
user. Reimplemented fresh from pattern (hermes-agent P16). No source copied.
"""
import os
import re
import sys

PATTERNS = [
    # Anthropic keys are shaped sk-ant-api03-<random>-<random> — hyphens
    # INSIDE the key body, not just as a prefix separator. A plain
    # [a-zA-Z0-9]{20,} class stops at the first embedded hyphen and never
    # reaches the 20-char floor, so it silently fails to match real keys.
    # Audited 2026-07-02 — confirmed live: real key passed through in cleartext.
    # underscore included: key alphabets commonly use base64url-ish charsets (-_)
    (re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"), "ANTHROPIC_KEY"),
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}"), "ANTHROPIC/OPENAI_KEY"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS_ACCESS_KEY"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "GITHUB_TOKEN"),
    (re.compile(r"gho_[a-zA-Z0-9]{36}"), "GITHUB_OAUTH_TOKEN"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "GOOGLE_API_KEY"),
    (re.compile(r"xox[baprs]-[0-9a-zA-Z-]{10,}"), "SLACK_TOKEN"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----.*?-----END (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", re.DOTALL), "PRIVATE_KEY"),
    # Secret-ish assignments: only redact hex/base64-looking values when they
    # appear in a key-ish context (secret=, token:, api_key=...). A bare
    # \b[0-9a-fA-F]{32,64}\b rule redacted every git SHA, MD5/SHA-256 digest,
    # and CVE PoC hash — for a security researcher that corrupts normal
    # output (audited 2026-07-02, C2). Bare hex now lives in AGGRESSIVE_PATTERNS.
    (re.compile(r"(?i)\b(?:secret|token|api[_-]?key|access[_-]?key|auth|bearer|passwd|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+=.]{8,}"), "SECRET_ASSIGNMENT"),
]

# Opt-in only: HERMES_REDACT_AGGRESSIVE=1 (or redact(..., aggressive=True)).
# Redacts any bare 32-64 char hex blob — catches naked secrets pasted without
# context, at the cost of eating git SHAs and file digests.
AGGRESSIVE_PATTERNS = [
    (re.compile(r"\b[0-9a-fA-F]{32,64}\b"), "HEX_SECRET_CANDIDATE"),
]


def redact(text: str, aggressive: bool = None) -> str:
    if not text:
        return text
    if aggressive is None:
        aggressive = os.environ.get("HERMES_REDACT_AGGRESSIVE", "") == "1"
    out = text
    for pattern, label in PATTERNS:
        out = pattern.sub(f"[REDACTED:{label}]", out)
    if aggressive:
        for pattern, label in AGGRESSIVE_PATTERNS:
            out = pattern.sub(f"[REDACTED:{label}]", out)
    return out


if __name__ == "__main__":
    data = sys.stdin.read() if not sys.argv[1:] else " ".join(sys.argv[1:])
    print(redact(data))
