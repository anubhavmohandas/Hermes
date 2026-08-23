#!/usr/bin/env bash
# palimpsest_gate.sh — UserPromptSubmit hook. Handles /palimpsest
# safe|aggressive|off|default <mode> and the "stop palimpsest" / "start
# palimpsest" natural-language phrases. Mirrors hooks/occam_mode_tracker.sh.
#
# Fail silent-safe: a mode-toggle miss just means no ack gets printed this
# turn — never blocks. The actual enforcement (file cleaning) lives in
# palimpsest_clean.sh (PostToolUse), not here.
#
# stdin:  JSON { prompt, session_id, cwd, hook_event_name, ... }
# stdout: JSON hookSpecificOutput.additionalContext, only when there's
#         something to say this turn.

INPUT="$(cat)"

if [ -z "$INPUT" ]; then
    exit 0
fi

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
    echo "$INPUT" | python3 "$HERMES_ROOT/meta/palimpsest.py" UserPromptSubmit 2>/dev/null
fi

exit 0
