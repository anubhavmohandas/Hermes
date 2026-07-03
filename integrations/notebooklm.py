#!/usr/bin/env python3
"""
integrations/notebooklm.py — NotebookLM synthesis (Stage 5, opt-in).

Pattern source (reimplemented fresh, no code copied): the v1 blueprint's
"NotebookLM synthesis (opt-in, documented Google-API risk)". Per
HERMES_GOAL_Start_to_End.md Stage 5 and Invariant #5 ("NotebookLM → none"),
this is opt-in with an explicit fallback: with no Google API configured, it
does NOT call out — it produces a LOCAL deterministic synthesis outline from
the given sources (a source-grounded skeleton), and says plainly that it did.

Documented risk (surfaced, not buried): the online path would send your
source material to Google. It is OFF unless HERMES_NOTEBOOKLM=on AND a
credential is present, and even then this module only builds the request —
it never silently uploads. Sensitive material must never take the online
path (same rule as Tier 3); `prepare()` refuses when brain flags the sources
as sensitive.

CLI:
    python3 integrations/notebooklm.py synth source1.txt source2.md
    python3 integrations/notebooklm.py status
"""
import json
import os
import re
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT))
import brain  # noqa: E402


def online_enabled() -> bool:
    return (os.environ.get("HERMES_NOTEBOOKLM", "off").lower() == "on"
            and bool(os.environ.get("GOOGLE_API_KEY")))


def _sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _local_synthesis(sources: dict) -> dict:
    """Deterministic, offline, source-grounded outline. Not an LLM — it
    extracts each source's lead sentences and cross-lists shared key terms,
    so the output is traceable to inputs (no fabrication)."""
    outline = []
    term_freq = {}
    for name, text in sources.items():
        sents = _sentences(text)
        lead = sents[:3]
        outline.append({"source": name, "lead_points": lead,
                        "sentence_count": len(sents)})
        for w in re.findall(r"\b[a-z]{5,}\b", text.lower()):
            term_freq[w] = term_freq.get(w, 0) + 1
    shared = sorted((t for t, c in term_freq.items() if c > 1),
                    key=lambda t: -term_freq[t])[:10]
    return {"mode": "local-offline", "sources": list(sources.keys()),
            "per_source": outline, "shared_key_terms": shared,
            "note": "deterministic source-grounded outline — no model call, "
                    "nothing left this machine"}


def prepare(paths):
    sources = {}
    for p in paths:
        path = Path(p)
        if not path.exists():
            return {"prepared": False, "reason": f"source not found: {p}"}
        sources[path.name] = path.read_text(errors="replace")

    combined = "\n".join(sources.values())
    if brain.check_sensitivity(combined):
        # Sensitive material: local path only, online refused outright.
        result = _local_synthesis(sources)
        result["online_refused"] = "sources matched sensitivity rules — online " \
                                   "synthesis (which uploads to Google) refused"
        return result

    if online_enabled():
        return {"prepared": True, "mode": "online-request-built",
                "warning": "online synthesis uploads sources to Google — this only "
                           "BUILDS the request; a human sends it",
                "request": {"sources": list(sources.keys()),
                            "endpoint": "notebooklm (configure client separately)"}}
    result = _local_synthesis(sources)
    result["online_note"] = "online path off (set HERMES_NOTEBOOKLM=on + GOOGLE_API_KEY)"
    return result


def status():
    return {"online_enabled": online_enabled(),
            "env_flag": os.environ.get("HERMES_NOTEBOOKLM", "off"),
            "google_key_present": bool(os.environ.get("GOOGLE_API_KEY")),
            "fallback": "local deterministic source-grounded outline (always available)",
            "risk": "online path sends source material to Google; off by default; "
                    "sensitive sources are refused the online path unconditionally"}


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "status":
        print(json.dumps(status(), indent=2))
    elif args and args[0] == "synth" and len(args) >= 2:
        print(json.dumps(prepare(args[1:]), indent=2))
    else:
        print("usage: notebooklm.py synth <source>... | status", file=sys.stderr)
        sys.exit(2)
