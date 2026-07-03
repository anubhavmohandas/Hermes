#!/usr/bin/env bash
# skills_scan.sh — SessionStart hook. Layer 4 (skills_guard) directory sweep.
#
# Why this exists: gate.py's "skillinstall" dispatch never fires through the
# PreToolUse hook because that's not a real tool name (audited 2026-07-02,
# C1). Write-time enforcement now lives in gate.py's write/edit branch; this
# hook covers the remaining gap — skill files that changed OUTSIDE a HERMES
# session (git pull, manual edit, another tool) get scanned when the next
# session starts.
#
# SessionStart hooks are advisory (they cannot block a session), so this
# always exits 0 — findings are printed loudly for Apollo's status line and
# the user, per SKILL.md §1 ("say so plainly rather than silently continuing").

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARD="$HERMES_ROOT/meta/security/skills_guard.py"

STATUS=0
for target in "$HERMES_ROOT/skills" "$HERMES_ROOT/SKILL.md" "$HERMES_ROOT/.claude-plugin"; do
    [ -e "$target" ] || continue
    OUT="$(python3 "$GUARD" "$target" 2>&1)" || STATUS=1
    if [ "$STATUS" -ne 0 ]; then
        echo "skills_scan.sh: QUARANTINE finding in $target — treat these skills as untrusted until reviewed:" >&2
        echo "$OUT" >&2
        STATUS=0  # keep scanning remaining targets; hook stays advisory
        FOUND=1
    fi
done

if [ -n "$FOUND" ]; then
    echo "skills_scan.sh: dangerous patterns found in skill files (see above). Enforcement: writes to skill files are blocked at the PreToolUse gate; this sweep catches out-of-band edits." >&2
else
    echo "skills_scan.sh: all skill files CLEAN" >&2
fi
exit 0
