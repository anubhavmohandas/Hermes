#!/usr/bin/env bash
# laconic_mode.sh — UserPromptSubmit hook. Opt-in token-reduction mode
# (module "laconic" in plugin.json modules.opt_in).
#
# Fires every turn alongside apollo_gate.sh. Logic lives in meta/laconic.py
# so it's unit-testable outside the hook harness; this script is a thin
# stdin/stdout wrapper matching the platform's UserPromptSubmit contract
# (additionalContext read only on exit 0 — see apollo_gate.sh for the
# same note, verified 2026-07-13).
#
# Fail silent-safe: laconic is a UX mode, not a security gate. Any error
# below just means no reminder gets injected this turn — never blocks.
#
# stdin:  JSON { prompt, session_id, cwd, hook_event_name, ... }
# stdout: JSON with hookSpecificOutput.additionalContext, only when
#         laconic is active, was just (de)activated, or a clarity
#         override needs to be flagged for this turn.

INPUT="$(cat)"

if [ -z "$INPUT" ]; then
    exit 0
fi

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
    echo "$INPUT" | python3 "$HERMES_ROOT/meta/laconic.py" 2>/dev/null
fi

exit 0
