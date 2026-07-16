#!/usr/bin/env bash
# occam_mode_tracker.sh — UserPromptSubmit hook. Detects /occam and
# /occam-review commands, mode switches, and "stop occam"/"normal mode"
# deactivation; while a mode is active, re-injects a short per-turn
# reminder (see meta/occam.py per_turn_reminder() docstring for why this
# deliberately deviates from the source project's SessionStart-only design).
#
# Fail silent-safe: this is a UX/behavioral mode, not a security gate.
#
# stdin:  JSON { prompt, session_id, cwd, hook_event_name, ... }
# stdout: JSON with hookSpecificOutput.additionalContext, only when there's
#         something to say this turn.

INPUT="$(cat)"

if [ -z "$INPUT" ]; then
    exit 0
fi

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
    echo "$INPUT" | python3 "$HERMES_ROOT/meta/occam.py" UserPromptSubmit 2>/dev/null
fi

exit 0
