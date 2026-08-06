#!/usr/bin/env bash
# laconic_activate.sh — SessionStart hook. Announces Laconic when the
# persistent flag is set, so a mode left on is visible on every new chat
# instead of silently active. Mirrors hooks/occam_activate.sh exactly;
# meta/laconic.py prints nothing when the flag is absent.
#
# stdin:  ignored (same convention as occam_activate.sh / skills_scan.sh).
# stdout: raw banner + ruleset text, read directly by SessionStart.

cat >/dev/null

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
    python3 "$HERMES_ROOT/meta/laconic.py" SessionStart 2>/dev/null
fi

exit 0
