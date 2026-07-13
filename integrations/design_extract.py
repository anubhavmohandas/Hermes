#!/usr/bin/env python3
"""
integrations/design_extract.py — site-to-design-tokens extractor (Stage 5,
opt-in), for skills/webdev/SKILL.md step 1 ("clone/match this reference
site's design system").

Pattern source (reimplemented fresh, no code copied — Invariant #4):
Extractions/design-extract/DESIGN_EXTRACT_PATTERNS.md, a Playwright-based
extractor that does a deep interaction pass (scroll/hover/open modals)
before pulling computed styles, clusters colors in OKLCH, and grades the
result on an 8-dimension A-F scale.

Why this is a STATIC extractor, not the interaction-driven one the pattern
describes: HERMES's own network-touching code goes through
`fetcher/fetch.py`'s SSRF-checked `fetch_url()` (every hop validated,
GET-only in SAFE_MODE) rather than spinning up a raw headless browser —
that discipline is deliberate (see `fetcher/fetch.py`'s own docstring: full
Playwright/interaction capability is "deliberately routed through Connect
once a playwright MCP server is configured", not bolted on directly). So
this script extracts what's determinable from raw HTML + linked/inline CSS
— real colors, real font-family declarations, real CSS custom properties —
safely and with zero new dependencies. It does NOT get computed styles
after JS execution, hover states, or anything behind a modal/interaction,
because that needs a real browser. That gap is reported explicitly in the
output, not silently absent.

CLI:
    python3 integrations/design_extract.py <url> [--out <dir>]
    python3 integrations/design_extract.py status
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetcher.fetch import fetch_url  # noqa: E402 — SSRF-checked, GET-only

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
RGB_RE = re.compile(r"rgba?\([\d.,\s%]+\)")
HSL_RE = re.compile(r"hsla?\([\d.,\s%]+\)")
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}\n]+)", re.I)
CUSTOM_PROP_RE = re.compile(r"(--[a-zA-Z0-9-]+)\s*:\s*([^;}\n]+);")
LINK_CSS_RE = re.compile(
    r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']', re.I)
STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.I | re.S)

MAX_CSS_FILES = 5  # cap how many linked stylesheets we follow — polite, bounded


def _clean(s: str) -> str:
    return s.strip().strip('"\'')


def extract_from_css(css: str) -> dict:
    colors = set(m.group(0).lower() for m in HEX_RE.finditer(css))
    colors |= set(_clean(m.group(0)) for m in RGB_RE.finditer(css))
    colors |= set(_clean(m.group(0)) for m in HSL_RE.finditer(css))
    fonts = set(_clean(m.group(1)) for m in FONT_FAMILY_RE.finditer(css))
    custom_props = {m.group(1): _clean(m.group(2))
                     for m in CUSTOM_PROP_RE.finditer(css)}
    return {"colors": sorted(colors), "fonts": sorted(fonts),
            "custom_properties": custom_props}


def extract(url: str) -> dict:
    result = {
        "source_url": url,
        "method": "static (raw HTML + linked/inline CSS via fetch_url — no browser)",
        "gaps": [
            "no computed styles after JS execution",
            "no hover/focus/interaction states",
            "no content behind modals or client-rendered routes",
            "colors are NOT clustered/deduped by perceptual distance "
            "(no OKLCH clustering — that needs real color-science libs, "
            "not wired here) — expect near-duplicate values in the raw list",
        ],
        "colors": [],
        "fonts": [],
        "custom_properties": {},
        "stylesheets_checked": [],
        "errors": [],
    }

    page = fetch_url(url)
    if not page.get("fetched"):
        result["errors"].append(f"page fetch failed: {page.get('reason')}")
        return result

    html = page["content"]
    merged_css = ""
    for m in STYLE_BLOCK_RE.finditer(html):
        merged_css += m.group(1) + "\n"

    hrefs = [urljoin(url, m.group(1)) for m in LINK_CSS_RE.finditer(html)]
    for href in hrefs[:MAX_CSS_FILES]:
        css_resp = fetch_url(href)
        result["stylesheets_checked"].append(
            {"url": href, "fetched": css_resp.get("fetched", False)})
        if css_resp.get("fetched"):
            merged_css += css_resp["content"] + "\n"
        else:
            result["errors"].append(
                f"stylesheet fetch failed: {href} — {css_resp.get('reason')}")
    if len(hrefs) > MAX_CSS_FILES:
        result["errors"].append(
            f"{len(hrefs) - MAX_CSS_FILES} additional stylesheet(s) not "
            f"followed (MAX_CSS_FILES={MAX_CSS_FILES} cap)")

    extracted = extract_from_css(merged_css)
    result["colors"] = extracted["colors"]
    result["fonts"] = extracted["fonts"]
    result["custom_properties"] = extracted["custom_properties"]
    return result


def status() -> dict:
    return {
        "mode": "static extraction only (fetch_url-based, SSRF-checked, no browser)",
        "full_pattern_needs": "a playwright MCP server via connect/mcp_client.py "
                               "for computed styles + interaction states + OKLCH "
                               "clustering + the 8-dimension A-F grade — not "
                               "configured by default",
        "toolchain_required": False,
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: design_extract.py <url> [--out <dir>] | status", file=sys.stderr)
        sys.exit(2)
    if args[0] == "status":
        print(json.dumps(status(), indent=2))
        sys.exit(0)

    url = args[0]
    out_dir = None
    if "--out" in args:
        i = args.index("--out")
        out_dir = Path(args[i + 1])

    data = extract(url)
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "extracted-tokens.json").write_text(json.dumps(data, indent=2))
        print(json.dumps({"written": str(out_dir / "extracted-tokens.json")}, indent=2))
    else:
        print(json.dumps(data, indent=2))
