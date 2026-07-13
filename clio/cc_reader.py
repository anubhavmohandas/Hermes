#!/usr/bin/env python3
"""
clio/cc_reader.py — reads REAL Claude Code CLI session transcripts off
disk. This is the actual gap that made Clio only a partial reimplementation
of the codeburn pattern: tracker.py previously only aggregated HERMES's
own internal log (logs/reasoning_seed.jsonl), never external tools'
session files. codeburn's actual value-add is reading 18 different
tools' native on-disk formats with no proxy/API key. This module adds
the first and most relevant one for this project: the Claude Code CLI
itself.

Format note (confidence: LIKELY, not CERTAIN — verify against your own
~/.claude/projects/ before trusting cost numbers for anything but rough
direction): Claude Code CLI writes one JSONL file per session under
~/.claude/projects/<project-path-hash>/<session-id>.jsonl. Each line is
one turn. Assistant turns carry a "message" object with "model" and a
"usage" object: {input_tokens, output_tokens, cache_creation_input_tokens,
cache_read_input_tokens}. This format is not officially documented and
may change between CLI versions — this reader is defensive (skips
unparseable lines, tolerates missing fields) rather than strict.

No proxy, no wrapper, no API key: this only reads files already on disk.
"""
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def default_projects_dir() -> Path:
    d = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(d) if d else Path.home() / ".claude"
    return base / "projects"


def _iter_session_files(projects_dir: Path):
    if not projects_dir.exists():
        return
    for p in projects_dir.rglob("*.jsonl"):
        yield p


def _parse_session_file(path: Path):
    """Yields normalized usage records: dict with session_id, timestamp,
    model, input_tokens, output_tokens, cache_creation_tokens,
    cache_read_tokens, tokens (total)."""
    session_id = path.stem
    try:
        with open(path, errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = entry.get("message")
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not isinstance(usage, dict):
                    continue
                inp = usage.get("input_tokens", 0) or 0
                out = usage.get("output_tokens", 0) or 0
                cache_c = usage.get("cache_creation_input_tokens", 0) or 0
                cache_r = usage.get("cache_read_input_tokens", 0) or 0
                yield {
                    "source": "claude-code-cli",
                    "session_id": session_id,
                    "timestamp": entry.get("timestamp", ""),
                    "model": msg.get("model", "unknown"),
                    "input_tokens": inp,
                    "output_tokens": out,
                    "cache_creation_tokens": cache_c,
                    "cache_read_tokens": cache_r,
                    "tokens": inp + out + cache_c + cache_r,
                }
    except OSError:
        return


def load_cc_sessions(projects_dir: Path = None, since: str = None):
    """Read every Claude Code CLI session JSONL under projects_dir
    (default ~/.claude/projects). Returns a flat list of usage records.
    Returns [] gracefully if the directory doesn't exist — this is the
    common case on any machine that isn't running the CLI locally."""
    projects_dir = projects_dir or default_projects_dir()
    records = []
    for path in _iter_session_files(projects_dir):
        for rec in _parse_session_file(path):
            if since and rec["timestamp"] and rec["timestamp"] < since:
                continue
            records.append(rec)
    return records


# Public Anthropic API list pricing, $/1M tokens, input/output — CONFIDENCE:
# LIKELY as of this codebase's last verification, NOT guaranteed current.
# Anthropic changes pricing without notice; this table is for rough
# observability only, never for billing. Re-verify against
# https://docs.claude.com/en/docs/about-claude/pricing before trusting
# a specific dollar figure.
MODEL_PRICING_PER_1M = {
    "claude-opus-4-8":        {"input": 15.00, "output": 75.00},
    "claude-sonnet-5":        {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "_default":               {"input": 3.00,  "output": 15.00},
}


def _model_key(model: str) -> str:
    if not model:
        return "_default"
    for key in MODEL_PRICING_PER_1M:
        if key != "_default" and key in model:
            return key
    return "_default"


def estimate_cc_cost(records) -> float:
    total = 0.0
    for r in records:
        rates = MODEL_PRICING_PER_1M[_model_key(r.get("model", ""))]
        total += (r.get("input_tokens", 0) / 1_000_000.0) * rates["input"]
        total += (r.get("output_tokens", 0) / 1_000_000.0) * rates["output"]
        # cache read tokens are billed far cheaper than fresh input in the
        # real API (roughly 10% of input rate) — approximate, not exact.
        total += (r.get("cache_read_tokens", 0) / 1_000_000.0) * rates["input"] * 0.1
    return round(total, 4)


def report_cc_sessions(projects_dir: Path = None, since: str = None) -> dict:
    records = load_cc_sessions(projects_dir, since)
    by_session = defaultdict(lambda: {"turns": 0, "tokens": 0})
    by_model = defaultdict(lambda: {"turns": 0, "tokens": 0})
    for r in records:
        by_session[r["session_id"]]["turns"] += 1
        by_session[r["session_id"]]["tokens"] += r["tokens"]
        by_model[r["model"]]["turns"] += 1
        by_model[r["model"]]["tokens"] += r["tokens"]
    return {
        "source": "claude-code-cli",
        "projects_dir_checked": str(projects_dir or default_projects_dir()),
        "sessions_found": len(by_session),
        "total_turns": len(records),
        "total_tokens": sum(r["tokens"] for r in records),
        "est_cost_usd": estimate_cc_cost(records),
        "by_session": dict(by_session),
        "by_model": dict(by_model),
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(report_cc_sessions(), indent=2))
