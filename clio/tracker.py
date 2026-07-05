#!/usr/bin/env python3
"""
clio/tracker.py — Clio v1: token tracking per session.

Pattern source (reimplemented fresh, no code copied): codeburn pattern —
18-tool token tracking by READING DISK FILES. No proxy, no request
interception, no wrapping the Anthropic client. HERMES already writes
tokens/latency into logs/reasoning_seed.jsonl via brain.py.log_request() —
Clio's only job is to aggregate what's already on disk.
"""
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
REASONING_LOG = HERMES_ROOT / "logs" / "reasoning_seed.jsonl"

# Rough $/1K-token estimates for reporting only — NOT used for any billing
# decision, purely observability. Update as pricing changes.
TIER_RATES_PER_1K = {
    1: 0.006,   # Tier 1 — Claude API (blended estimate)
    2: 0.0,     # Tier 2 — Ollama local, no per-token API cost
    3: 0.004,   # Tier 3 — NYX fallback (external, EU/US only)
}


def load_entries(log_path: Path = REASONING_LOG, since: str = None):
    if not log_path.exists():
        return []
    entries = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and entry.get("timestamp", "") < since:
                continue
            entries.append(entry)
    return entries


def aggregate(entries, group_by: str = "tier"):
    """Group the trace by any field the line carries — 'tier', 'model',
    'task_type', 'decision', 'outcome' (V1_CHECKLIST §3: the trace can be
    sliced by which tier/model served and what decision was made). Cost is
    accumulated from each entry's own tier, so it stays correct under any
    grouping, not just group_by='tier'."""
    groups = defaultdict(lambda: {"count": 0, "tokens": 0, "latency_ms": 0,
                                   "success": 0, "failure": 0, "est_cost_usd": 0.0})
    for e in entries:
        # a present-but-null field (e.g. model on a pre-§3 line) reads as 'unknown'
        key = e.get(group_by)
        if key is None:
            key = "unknown"
        g = groups[key]
        g["count"] += 1
        tokens = e.get("tokens", 0) or 0
        g["tokens"] += tokens
        g["latency_ms"] += e.get("latency_ms", 0) or 0
        g["est_cost_usd"] += (tokens / 1000.0) * TIER_RATES_PER_1K.get(e.get("tier"), 0.006)
        if e.get("success") is True:
            g["success"] += 1
        elif e.get("success") is False:
            g["failure"] += 1
    # add derived fields
    for key, g in groups.items():
        g["avg_latency_ms"] = round(g["latency_ms"] / g["count"], 1) if g["count"] else 0
        g["est_cost_usd"] = round(g["est_cost_usd"], 4)
    return dict(groups)


def estimate_total_cost(entries):
    total = 0.0
    for e in entries:
        tier = e.get("tier")
        tokens = e.get("tokens", 0) or 0
        total += (tokens / 1000.0) * TIER_RATES_PER_1K.get(tier, 0.006)
    return round(total, 4)


def report(group_by: str = "tier", since: str = None):
    entries = load_entries(since=since)
    agg = aggregate(entries, group_by)
    total_cost = estimate_total_cost(entries)
    return {
        "total_requests": len(entries),
        "total_tokens": sum(e.get("tokens", 0) or 0 for e in entries),
        "est_total_cost_usd": total_cost,
        "grouped_by": group_by,
        "groups": agg,
    }


if __name__ == "__main__":
    group_by = "tier"
    since = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--group-by" and i + 1 < len(args):
            group_by = args[i + 1]
        if a == "--since" and i + 1 < len(args):
            since = args[i + 1]
    result = report(group_by=group_by, since=since)
    print(json.dumps(result, indent=2))
