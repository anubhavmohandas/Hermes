#!/usr/bin/env bash
# occam_subagent.sh — SubagentStart hook. SessionStart context is
# parent-thread only and never reaches a Task-spawned subagent, so without
# this every subagent runs Occam-unaware while the parent session has it
# active (same gap the source project's own SubagentStart hook closes).
#
# stdin: passed through to meta/occam.py, which only reads it when
#        OCCAM_SUBAGENT_MATCHER is set (agent_type scoping, ported from
#        the source's own issue #506) — the default no-matcher path stays
#        synchronous and stdin-independent by design.
# stdout: JSON hookSpecificOutput.additionalContext (SubagentStart needs the
#         JSON form, not raw stdout — see meta/laconic.py's sibling hooks
#         for the same SessionStart-vs-other-events contract split).

INPUT="$(cat)"

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
    echo "$INPUT" | python3 "$HERMES_ROOT/meta/occam.py" SubagentStart 2>/dev/null
fi

exit 0
