#!/usr/bin/env python3
"""
curator/consolidate.py — Curator v1: reflexion consolidation.

Pattern source (reimplemented fresh, no code copied): SuperClaude
SelfCorrectionEngine (Pattern #153) — 6-category taxonomy, MD5 dedup,
recurrence tracking, canonical prevention rule per category.

Reads raw append-only logs/reflexion_seed.json (JSONL, one brain.py
log-failure call per line) and consolidates it into curator/reflexion.json —
a structured, deduplicated JSON array keyed by dedup_key, with
recurrence_count / first_seen / last_seen per distinct failure.

This does NOT delete or rewrite the raw log — reflexion_seed.json stays
append-only forever (it's the audit trail). This is a read-only
transformation that runs on demand (or via Dream consolidation, see
mnemos/dream.py) and overwrites ONLY curator/reflexion.json.
"""
import json
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT))
from meta.paths import state_file  # noqa: E402

# Runtime state under ~/.claude/hermes/ (meta/paths.py). STRUCTURED_OUT must
# resolve to the same file as propose.py's REFLEXION_PATH — this module
# overwrites it and propose.py reads it.
RAW_LOG = state_file("logs", "reflexion_seed.json")
STRUCTURED_OUT = state_file("curator", "reflexion.json")
CURATOR_DIR = STRUCTURED_OUT.parent

VALID_CATEGORIES = {"validation", "dependency", "logic", "assumption", "type", "unknown"}


def load_raw_entries(path: Path = RAW_LOG):
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # skip malformed lines rather than crash the whole consolidation
    return entries


def consolidate(raw_entries):
    """Groups raw entries by dedup_key. Returns list of structured records,
    sorted by recurrence_count descending (most-repeated mistakes first —
    that's the ordering that matters for a human reviewing what to fix)."""
    groups = {}
    for e in raw_entries:
        key = e.get("dedup_key")
        if not key:
            continue
        category = e.get("error_category", "unknown")
        if category not in VALID_CATEGORIES:
            category = "unknown"
        if key not in groups:
            groups[key] = {
                "id": f"err_{key}",
                "dedup_key": key,
                "category": category,
                "task": e.get("task", ""),
                "failure_mode": e.get("failure_mode", e.get("prevention_rule", "")),
                "prevention_rule": e.get("prevention_rule", ""),
                "recurrence_count": 0,
                "first_seen": e.get("timestamp"),
                "last_seen": e.get("timestamp"),
            }
        g = groups[key]
        g["recurrence_count"] += 1
        ts = e.get("timestamp", "")
        if ts and ts < g["first_seen"]:
            g["first_seen"] = ts
        if ts and ts > g["last_seen"]:
            g["last_seen"] = ts
            # prevention_rule can be refined over occurrences — keep the latest wording
            g["prevention_rule"] = e.get("prevention_rule", g["prevention_rule"])

    records = list(groups.values())
    records.sort(key=lambda r: r["recurrence_count"], reverse=True)
    return records


def run(raw_path: Path = RAW_LOG, out_path: Path = STRUCTURED_OUT):
    raw = load_raw_entries(raw_path)
    structured = consolidate(raw)
    out_path.write_text(json.dumps(structured, indent=2))
    return {
        "raw_entries_read": len(raw),
        "distinct_failures": len(structured),
        "recurring_failures": len([r for r in structured if r["recurrence_count"] > 1]),
        "output": str(out_path),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
