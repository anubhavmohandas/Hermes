#!/usr/bin/env python3
"""
file_safety.py — Layer 1/7: write denylist.
Blocks writes to credential stores, shell init files, and system auth files
regardless of what tool or prompt is asking for the write.
Reimplemented fresh from pattern (hermes-agent P16). No source copied.
"""
import fnmatch
import sys
from pathlib import Path

DENY_PATTERNS = [
    "*/.ssh/*", "*/.ssh/id_*", "*/.ssh/authorized_keys", "*/.ssh/known_hosts",
    "*.env", "*.env.*", "*/.env",
    "*/.bashrc", "*/.zshrc", "*/.bash_profile", "*/.profile", "*/.bash_login",
    "*/.netrc", "*/.npmrc", "*/.pypirc", "*/.git-credentials",
    "*/.aws/credentials", "*/.aws/config",
    "/etc/sudoers", "/etc/sudoers.d/*", "/etc/shadow", "/etc/passwd", "/etc/hosts",
    "*/id_rsa*", "*/id_ed25519*", "*/id_ecdsa*",
    "*.pem", "*.key", "*_rsa", "*.pfx", "*.p12",
    "*/HERMES.local.md",  # config carries local secrets — never let a skill overwrite it
]


def is_write_blocked(path: str):
    """Returns (blocked: bool, reason: str)."""
    if not path:
        return False, "no path given"
    norm = str(Path(path).as_posix())
    basename = Path(norm).name
    for pattern in DENY_PATTERNS:
        # Full-path match always applies.
        if fnmatch.fnmatch(norm, pattern):
            return True, f"BLOCKED: write to '{path}' matches denylist pattern '{pattern}'"
        # Basename-only fallback ONLY for patterns that are themselves a bare
        # filename glob (no '/' in them) — e.g. "*.env", "*.pem". Patterns that
        # contain '/' (e.g. "*/.ssh/*") must never degrade to matching a lone
        # basename against "*", which would match everything.
        if "/" not in pattern and fnmatch.fnmatch(basename, pattern):
            return True, f"BLOCKED: write to '{path}' matches denylist pattern '{pattern}'"
    return False, "ALLOWED"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: file_safety.py <path>", file=sys.stderr)
        sys.exit(2)
    blocked, reason = is_write_blocked(sys.argv[1])
    print(reason)
    sys.exit(1 if blocked else 0)
