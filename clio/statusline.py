#!/usr/bin/env python3
"""
clio/statusline.py — Clio's live status line: 5-hour + 7-day rate-limit
usage as a progress bar, rendered in Claude Code's own status row.

TERMINAL CLI ONLY. Verified 2026-08-04: the VS Code extension panel never
invokes the statusLine command — its webview has no status row, and an
entire multi-turn session in the panel appended nothing to usage_log.jsonl.
statusLine is a terminal-CLI surface; in VS Code use `/usage` instead.

Data source: Claude Code sends `rate_limits.five_hour.used_percentage` and
`rate_limits.seven_day.used_percentage` via stdin JSON on every status-line
refresh. This is Anthropic's own server-side number for Pro/Max accounts —
not something Clio estimates. Absent for API-key (pay-as-you-go) billing,
and absent until the first API response in a session.

This is part of HERMES, lives in the plugin repo, and requires nothing
installed outside it — no separate extension, no ~/.vscode/extensions
folder. The only thing that has to exist outside the repo is the one-line
pointer in settings.json telling Claude Code to run this file (Claude
Code's statusLine mechanism is inherently a settings.json-level hook; there
is no way to make a plugin manifest ship it directly — plugin settings.json
only supports the `agent` and `subagentStatusLine` keys, confirmed against
code.claude.com/docs/en/plugins-reference).

Every run appends one line to ~/.claude/hermes/clio/usage_log.jsonl (see
meta/paths.py — NOT next to this file, which a plugin update would wipe).
That builds a history of rate-limit usage over time rather than only a live
snapshot. Note that clio/tracker.py does not read this file yet; it reports
on logs/reasoning_seed.jsonl and clio/benchmark_history.jsonl. Wiring the
usage history into tracker.py is still open.

Install — user-scoped, so it works in whatever project HERMES is assisting.
Add to ~/.claude/settings.json (the path is resolved at run time so plugin
updates don't break it):

  "statusLine": {
    "type": "command",
    "command": "python3 \"$(ls -d $HOME/.claude/plugins/cache/hermes/hermes/*/clio/statusline.py | sort -V | tail -1)\""
  }

Test manually:
  echo '{"model":{"display_name":"Sonnet"},"rate_limits":{"five_hour":{"used_percentage":23.5,"resets_at":1893456000},"seven_day":{"used_percentage":61.2,"resets_at":1893456000}}}' | python3 clio/statusline.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

CLIO_DIR = Path(__file__).resolve().parent
HERMES_ROOT = CLIO_DIR.parent
BAR_WIDTH = 10


def usage_log():
    """Resolved lazily, not at import: this file runs as Claude Code's status
    line, where an exception at import time renders a traceback into the
    user's prompt row. log_snapshot()'s existing OSError guard covers the
    directory creation this does."""
    sys.path.insert(0, str(HERMES_ROOT))
    from meta.paths import state_file
    return state_file("clio", "usage_log.jsonl")

GREEN, YELLOW, RED, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def bar(pct, width=BAR_WIDTH):
    pct = max(0, min(100, pct))
    filled = round(pct * width / 100)
    return "█" * filled + "░" * (width - filled)


def color_for(pct):
    if pct >= 90:
        return RED
    if pct >= 70:
        return YELLOW
    return GREEN


def fmt_reset(epoch):
    if not epoch:
        return ""
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).astimezone().strftime("%a %H:%M")
    except (ValueError, OSError):
        return ""


def log_snapshot(model, five_h, seven_d):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "five_hour_pct": five_h,
        "seven_day_pct": seven_d,
    }
    try:
        with open(usage_log(), "a") as f:
            f.write(json.dumps(entry) + "\n")
    except (OSError, ImportError):
        pass  # never let logging failure break the status line


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("[HERMES] usage: --")
        return

    model = (data.get("model") or {}).get("display_name", "claude")
    rate = data.get("rate_limits") or {}
    five_h = (rate.get("five_hour") or {}).get("used_percentage")
    seven_d = (rate.get("seven_day") or {}).get("used_percentage")
    five_h_reset = (rate.get("five_hour") or {}).get("resets_at")
    seven_d_reset = (rate.get("seven_day") or {}).get("resets_at")

    log_snapshot(model, five_h, seven_d)

    if five_h is None and seven_d is None:
        print(f"[HERMES · {model}] rate limits: n/a (API-key billing, or no data yet this session)")
        return

    parts = [f"[HERMES · {model}]"]
    if five_h is not None:
        r = fmt_reset(five_h_reset)
        parts.append(f"5h {color_for(five_h)}{bar(five_h)}{RESET} {five_h:.0f}%" + (f" (resets {r})" if r else ""))
    if seven_d is not None:
        r = fmt_reset(seven_d_reset)
        parts.append(f"wk {color_for(seven_d)}{bar(seven_d)}{RESET} {seven_d:.0f}%" + (f" (resets {r})" if r else ""))

    print("  |  ".join(parts))


if __name__ == "__main__":
    main()
