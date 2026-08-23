#!/usr/bin/env bash
# palimpsest_activate.sh — SessionStart hook. Announces Palimpsest when its
# default/persistent mode isn't "off", mirroring hooks/occam_activate.sh /
# hooks/laconic_activate.sh exactly. meta/palimpsest.py prints nothing when
# the resolved mode is "off".
#
# stdin:  ignored (same convention as occam_activate.sh / skills_scan.sh).
# stdout: raw banner text, read directly by SessionStart.

cat >/dev/null

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
    python3 "$HERMES_ROOT/meta/palimpsest.py" SessionStart 2>/dev/null
fi

exit 0
