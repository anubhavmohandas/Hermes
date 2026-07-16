#!/usr/bin/env bash
# occam_activate.sh — SessionStart hook. Writes the mode flag and emits the
# full ladder ruleset once per session (ponytail's own architecture: full
# text at SessionStart, short reminders per turn thereafter — see
# meta/occam.py per_turn_reminder() for why this file only fires once).
#
# stdin:  ignored (matches hooks/skills_scan.sh convention — this hook
#         doesn't need the SessionStart payload, only env + disk state).
# stdout: raw ruleset text (Claude Code SessionStart reads stdout directly,
#         same as apollo_gate.sh's contract for UserPromptSubmit's JSON
#         form — different event, different accepted shape).

cat >/dev/null

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
    python3 "$HERMES_ROOT/meta/occam.py" SessionStart 2>/dev/null
fi

exit 0
