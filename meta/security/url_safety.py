#!/usr/bin/env python3
"""
url_safety.py — Layer 3/7: SSRF prevention.
Cloud metadata endpoints are ALWAYS blocked, no override.
Private/loopback ranges blocked by default, configurable via allow-list arg.
Reimplemented fresh from pattern (hermes-agent P16). No source copied.

Hardened 2026-07-05 (audit M1). The original checked only the first IPv4 A
record via socket.gethostbyname and FAILED OPEN when resolution failed. Three
bypasses closed here:
  1. IPv6 blindness — gethostbyname is IPv4-only, so an AAAA-only host that
     resolves to ::1 or fc00::/7 sailed past the check and urllib then
     connected over IPv6. Now getaddrinfo enumerates EVERY A and AAAA record.
  2. Multi-record bypass — a host with one public and one private address
     passed on the public one. Now ANY bad address in the set blocks.
  3. Fail-open — an unresolvable-at-check-time host returned "allowed"; urllib
     could still resolve it a moment later (or via a different resolver). Now
     resolution failure FAILS CLOSED.
The remaining DNS-rebind TOCTOU (resolve here, urllib re-resolves at fetch)
is closed by the CALLER pinning the connection to the vetted IP returned by
resolve_and_validate() — see fetcher/fetch.py. check_url() stays the simple
(allowed, reason) seam that gate.py and the tests use.
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


def _classify_ip(ip: ipaddress._BaseAddress, allow_private: bool):
    """Returns (ok: bool, why: str) for one resolved address. The loopback /
    link-local / multicast / unspecified / reserved classes are ALWAYS
    refused — allow_private only lifts ordinary RFC1918-style private ranges,
    never the metadata/link-local range (169.254/16, fe80::/10)."""
    # IPv4-mapped IPv6 (::ffff:a.b.c.d) — classify on the embedded v4 so
    # ::ffff:169.254.169.254 can't smuggle the metadata IP past the v6 checks.
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip.is_loopback:
        return False, f"loopback ({ip})"
    if ip.is_link_local:
        return False, f"link-local ({ip}) — includes cloud metadata 169.254/16"
    if ip.is_multicast:
        return False, f"multicast ({ip})"
    if ip.is_unspecified:
        return False, f"unspecified ({ip})"
    if ip.is_reserved:
        return False, f"reserved ({ip})"
    if ip.is_private and not allow_private:
        return False, f"private ({ip}); pass allow_private=True to permit"
    return True, "ok"


def resolve_and_validate(url: str, allow_private: bool = False):
    """Returns (allowed: bool, reason: str, ips: list[str]).

    `ips` is the set of vetted addresses the URL's host resolves to — the
    caller should pin its connection to one of these rather than re-resolving
    the hostname (that re-resolution is the DNS-rebinding window). For a URL
    whose host is already an IP literal, `ips` is just that literal."""
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"BLOCKED: unparseable URL — {e}", []

    if parsed.scheme not in ("http", "https"):
        return False, f"BLOCKED: scheme '{parsed.scheme}' not allowed (http/https only)", []

    host = parsed.hostname
    if not host:
        return False, "BLOCKED: no hostname in URL", []

    if host in METADATA_HOSTS:
        return False, f"BLOCKED: '{host}' is a cloud metadata endpoint (never allowed, no override)", []

    # Host is already an IP literal — validate it directly, no DNS.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        ok, why = _classify_ip(ip, allow_private)
        if not ok:
            return False, f"BLOCKED: '{host}' is {why}", []
        return True, "ALLOWED", [str(ip)]

    # Hostname — resolve EVERY address (v4 + v6). Fail CLOSED on failure: a
    # name that won't resolve at check-time must not be handed to a fetcher
    # that might resolve it differently a moment later.
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError, UnicodeError) as e:
        return False, (f"BLOCKED: cannot resolve '{host}' ({e}) — failing closed "
                       f"(an unresolvable name must not be fetched)"), []

    ips = []
    for info in infos:
        sockaddr = info[4]
        ipstr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ipstr)
        except ValueError:
            continue
        ok, why = _classify_ip(ip, allow_private)
        if not ok:
            return False, f"BLOCKED: '{host}' resolves to {ipstr} which is {why}", []
        if ipstr not in ips:
            ips.append(ipstr)

    if not ips:
        return False, f"BLOCKED: '{host}' produced no usable A/AAAA records", []
    return True, "ALLOWED", ips


def check_url(url: str, allow_private: bool = False):
    """Backward-compatible (allowed, reason) seam used by gate.py and the
    tests. Drops the resolved-IP list; callers that need to pin (fetch) call
    resolve_and_validate directly."""
    allowed, reason, _ips = resolve_and_validate(url, allow_private)
    return allowed, reason


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: url_safety.py <url> [--allow-private]", file=sys.stderr)
        sys.exit(2)
    allow_private = "--allow-private" in sys.argv
    allowed, reason, ips = resolve_and_validate(sys.argv[1], allow_private)
    print(f"{reason}" + (f"  ips={ips}" if ips else ""))
    sys.exit(0 if allowed else 1)
