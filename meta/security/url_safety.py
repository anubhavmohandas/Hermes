#!/usr/bin/env python3
"""
url_safety.py — Layer 3/7: SSRF prevention.
Cloud metadata endpoints are ALWAYS blocked, no override.
Private/loopback ranges blocked by default, configurable via allow-list arg.
Reimplemented fresh from pattern (hermes-agent P16). No source copied.
"""
import ipaddress
import socket
import sys
from urllib.parse import urlparse

# Never reachable, no exceptions — cloud instance metadata services.
METADATA_HOSTS = {
    "169.254.169.254",           # AWS / GCP / Azure IMDS
    "metadata.google.internal",
    "metadata.azure.com",
    "100.100.100.200",           # Alibaba Cloud
}


def check_url(url: str, allow_private: bool = False):
    """Returns (allowed: bool, reason: str)."""
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"BLOCKED: unparseable URL — {e}"

    if parsed.scheme not in ("http", "https"):
        return False, f"BLOCKED: scheme '{parsed.scheme}' not allowed (http/https only)"

    host = parsed.hostname
    if not host:
        return False, "BLOCKED: no hostname in URL"

    if host in METADATA_HOSTS:
        return False, f"BLOCKED: '{host}' is a cloud metadata endpoint (never allowed, no override)"

    try:
        resolved = socket.gethostbyname(host)
        ip = ipaddress.ip_address(resolved)
    except (socket.gaierror, ValueError):
        # Can't resolve here (sandboxed/offline) — allow through to higher layers,
        # but flag explicitly rather than silently passing.
        return True, f"ALLOWED (unresolved at check-time, host={host})"

    if ip.is_loopback or ip.is_link_local:
        return False, f"BLOCKED: '{host}' resolves to loopback/link-local ({resolved})"

    if ip.is_private and not allow_private:
        return False, f"BLOCKED: '{host}' resolves to private range ({resolved}); pass allow_private=True to permit"

    return True, "ALLOWED"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: url_safety.py <url> [--allow-private]", file=sys.stderr)
        sys.exit(2)
    allow_private = "--allow-private" in sys.argv
    allowed, reason = check_url(sys.argv[1], allow_private)
    print(reason)
    sys.exit(0 if allowed else 1)
