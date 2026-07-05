#!/usr/bin/env python3
"""
fetcher/fetch.py — Fetcher (Phase 3C): safe live web access.

Pattern sources (reimplemented fresh, no code copied): tavily-mcp search
endpoint shape, firecrawl-mcp scrape/format params, mcp-playwright SAFE_MODE
action gating, browser-harness fetch caps. Per HERMES_GOAL_Start_to_End.md
Stage 3 item 3: Tavily / Firecrawl / Playwright routing with SAFE_MODE;
replaces the Phase-1 WebSearch backend in skills/research.

Security is layered, not optional:
  - EVERY url — initial and every redirect hop — goes through
    meta/security/url_safety.check_url (SSRF layer 3). A redirect to a
    metadata endpoint or private range aborts the fetch. There is no flag
    to skip this.
  - SAFE_MODE (default ON): GET only, no cookies or auth headers forwarded,
    response capped at MAX_BYTES, hard timeout, max 5 redirect hops.
    SAFE_MODE=off (env HERMES_FETCH_SAFE_MODE=off) only lifts the GET-only
    restriction — the SSRF layer stays.
  - Fetched content is UNTRUSTED INPUT. It is returned as data with an
    `untrusted: true` marker; nothing here executes or interprets it.

Backend routing (first available wins, each degrades to the next —
Invariant #5):
  search:  Tavily (TAVILY_API_KEY) → Firecrawl (FIRECRAWL_API_KEY) →
           unavailable (stated plainly; a fetcher with no key does NOT
           pretend to search)
  fetch:   direct stdlib urllib GET (always available) — Playwright MCP is
           deliberately routed through Connect once a playwright MCP server
           is configured; this module stays dependency-free.

CLI:
    python3 fetcher/fetch.py fetch <url> [--max-bytes N]
    python3 fetcher/fetch.py search "<query>" [--max-results 5]
    python3 fetcher/fetch.py status
"""
import argparse
import http.client
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import partial
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT / "meta" / "security"))
import url_safety  # noqa: E402
import redact      # noqa: E402

MAX_BYTES = 2 * 1024 * 1024   # 2 MB cap — a fetcher is not a downloader
TIMEOUT_SECONDS = 30
MAX_REDIRECTS = 5
USER_AGENT = "HERMES-Fetcher/1.0 (personal research agent)"


def _ssl_context() -> ssl.SSLContext:
    """Verified TLS, always — there is deliberately no insecure fallback.
    python.org macOS builds ship without the system trust store wired in
    (fetches fail with CERTIFICATE_VERIFY_FAILED); certifi fills that gap
    when installed. If neither works, the fetch fails loudly and the fix is
    named in the error, not worked around by disabling verification."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def safe_mode_on() -> bool:
    return os.environ.get("HERMES_FETCH_SAFE_MODE", "on").lower() != "off"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface redirects to the caller instead of auto-following, so every
    hop re-enters url_safety. Auto-follow is how redirect-SSRF happens."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# --- DNS-rebind defense: connect to the exact IP url_safety vetted, instead
# of letting urllib re-resolve the hostname (the re-resolution is the rebinding
# window). The hostname is still used for the Host header, TLS SNI, and cert
# verification — only the socket's connect target is pinned. (audit M1)
class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args, pinned_ip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._pinned_ip = pinned_ip

    def connect(self):
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self._tunnel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, pinned_ip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._pinned_ip = pinned_ip

    def connect(self):
        sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
            sock = self.sock
        # server_hostname = self.host (the NAME) => SNI + cert check target the
        # hostname even though the TCP connection went to the pinned IP.
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _PinnedHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, pinned_ip):
        super().__init__()
        self._pinned_ip = pinned_ip

    def http_open(self, req):
        return self.do_open(partial(_PinnedHTTPConnection, pinned_ip=self._pinned_ip), req)


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, context, pinned_ip):
        super().__init__(context=context)
        self._pinned_ip = pinned_ip

    def https_open(self, req):
        # Forward the verified SSL context (certifi-backed) — without it the
        # pinned connection falls back to the empty system trust store and
        # every HTTPS fetch fails verification. The context already carries
        # check_hostname=True, so hostname verification stays on.
        return self.do_open(partial(_PinnedHTTPSConnection, pinned_ip=self._pinned_ip),
                            req, context=self._context)


def fetch_url(url: str, max_bytes: int = MAX_BYTES):
    """GET one URL with SSRF checks on every hop. Returns a dict; never
    raises for policy blocks — the block reason IS the result."""
    hops = []
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        allowed, reason, ips = url_safety.resolve_and_validate(current)
        if not allowed:
            return {"fetched": False, "url": current, "hops": hops,
                    "reason": f"SSRF layer: {reason}"}
        pinned_ip = ips[0]
        req = urllib.request.Request(current, headers={"User-Agent": USER_AGENT},
                                     method="GET")
        opener = urllib.request.build_opener(
            _PinnedHTTPHandler(pinned_ip),
            _PinnedHTTPSHandler(_ssl_context(), pinned_ip), _NoRedirect)
        started = time.time()
        try:
            resp = opener.open(req, timeout=TIMEOUT_SECONDS)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get("Location")
                if not location:
                    return {"fetched": False, "url": current, "hops": hops,
                            "reason": f"redirect {e.code} without Location header"}
                hops.append(current)
                current = urllib.parse.urljoin(current, location)
                continue
            return {"fetched": False, "url": current, "hops": hops,
                    "reason": f"HTTP {e.code}"}
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            return {"fetched": False, "url": current, "hops": hops,
                    "reason": f"network error: {e}"}
        body = resp.read(max_bytes + 1)
        truncated = len(body) > max_bytes
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "fetched": True,
            "url": current,
            "hops": hops,
            "status": resp.status,
            "content_type": resp.headers.get("Content-Type", ""),
            "bytes": min(len(body), max_bytes),
            "truncated": truncated,
            "elapsed_ms": elapsed_ms,
            "untrusted": True,  # web content is input, never instructions
            "content": body[:max_bytes].decode("utf-8", errors="replace"),
        }
    return {"fetched": False, "url": current, "hops": hops,
            "reason": f"more than {MAX_REDIRECTS} redirects"}


# ---------------------------------------------------------------------------
# search backends — key-gated, never faked
# ---------------------------------------------------------------------------

def _post_json(url: str, payload: dict, headers: dict):
    allowed, reason = url_safety.check_url(url)
    if not allowed:
        return None, f"SSRF layer: {reason}"
    if safe_mode_on() and not url.startswith("https://"):
        return None, "SAFE_MODE: search API calls must be https"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS,
                                    context=_ssl_context()) as resp:
            return json.loads(resp.read(MAX_BYTES).decode("utf-8", errors="replace")), None
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return None, f"backend error: {e}"


def _search_tavily(query: str, max_results: int):
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return None, "no TAVILY_API_KEY"
    body, err = _post_json("https://api.tavily.com/search",
                           {"query": query, "max_results": max_results},
                           {"Authorization": f"Bearer {key}"})
    if err:
        return None, err
    results = [{"title": r.get("title", ""), "url": r.get("url", ""),
                "snippet": (r.get("content") or "")[:500]}
               for r in body.get("results", [])[:max_results]]
    return {"backend": "tavily", "results": results,
            "answer": body.get("answer")}, None


def _search_firecrawl(query: str, max_results: int):
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        return None, "no FIRECRAWL_API_KEY"
    body, err = _post_json("https://api.firecrawl.dev/v1/search",
                           {"query": query, "limit": max_results},
                           {"Authorization": f"Bearer {key}"})
    if err:
        return None, err
    results = [{"title": r.get("title", ""), "url": r.get("url", ""),
                "snippet": (r.get("description") or r.get("markdown") or "")[:500]}
               for r in body.get("data", [])[:max_results]]
    return {"backend": "firecrawl", "results": results}, None


def search(query: str, max_results: int = 5):
    """Try each key-gated backend in order. No key, no search — say so."""
    attempts = {}
    for name, fn in (("tavily", _search_tavily), ("firecrawl", _search_firecrawl)):
        result, err = fn(query, max_results)
        if result is not None:
            result["untrusted"] = True
            return result
        attempts[name] = err
    return {"backend": None, "results": [],
            "reason": "no search backend available — set TAVILY_API_KEY or "
                      "FIRECRAWL_API_KEY (results are never faked)",
            "attempts": attempts}


def status():
    return {
        "safe_mode": safe_mode_on(),
        "max_bytes": MAX_BYTES,
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_redirects": MAX_REDIRECTS,
        "backends": {
            "tavily": bool(os.environ.get("TAVILY_API_KEY")),
            "firecrawl": bool(os.environ.get("FIRECRAWL_API_KEY")),
            "direct_fetch": True,
            "playwright": "via Connect — configure a playwright MCP server",
        },
    }


def main():
    parser = argparse.ArgumentParser(prog="fetcher/fetch.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("url")
    p_fetch.add_argument("--max-bytes", type=int, default=MAX_BYTES)

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--max-results", type=int, default=5)

    sub.add_parser("status")

    args = parser.parse_args()
    if args.command == "fetch":
        out = fetch_url(args.url, args.max_bytes)
        # content can carry anything — scrub secrets before it hits a terminal/log
        if out.get("content"):
            out["content"] = redact.redact(out["content"])
        print(json.dumps(out, indent=2))
        sys.exit(0 if out["fetched"] else 1)
    elif args.command == "search":
        print(json.dumps(search(args.query, args.max_results), indent=2))
    elif args.command == "status":
        print(json.dumps(status(), indent=2))


if __name__ == "__main__":
    main()
