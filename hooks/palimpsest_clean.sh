#!/usr/bin/env bash
# palimpsest_clean.sh — PostToolUse hook (matcher: Write|Edit, see
# .claude-plugin/plugin.json). This is the actual enforcement point: right
# after a Write/Edit tool call finishes, it runs the just-written file
# through integrations/palimpsest and rewrites it in place if anything
# watermark-shaped was found. New hook type in this codebase (the existing
# hooks cover SessionStart/UserPromptSubmit/PreToolUse/SubagentStart) —
# PostToolUse is the only event that fires after a file actually has
# content on disk to inspect.
#
# Fail silent-safe, same doctrine as every other mode hook here: a bad
# input file, a missing engine module, or any exception inside
# meta/palimpsest.py must never turn into a blocked or failed tool call.
# The tool call already succeeded; this hook can only add a note or do
# nothing.
#
# stdin:  JSON { tool_name, tool_input: { file_path, ... }, tool_response,
#         session_id, cwd, hook_event_name, ... }
# stdout: JSON hookSpecificOutput.additionalContext, only when a file was
#         actually cleaned.

INPUT="$(cat)"

if [ -z "$INPUT" ]; then
    exit 0
fi

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
    echo "$INPUT" | python3 "$HERMES_ROOT/meta/palimpsest.py" PostToolUse 2>/dev/null
fi

exit 0
