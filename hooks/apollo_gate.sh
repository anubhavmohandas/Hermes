#!/usr/bin/env bash
# apollo_gate.sh — UserPromptSubmit hook. Fires once per turn, before Claude
# processes the prompt, in EVERY session where the hermes plugin is enabled —
# CLI or Cowork, any project folder, not just ones named/referencing HERMES.
#
# Why this exists: Apollo (SKILL.md) previously only activated when its own
# description matched the prompt closely enough (skill-matching heuristic).
# On 2026-07-12 that heuristic failed to fire for a raw "build a website"
# request in a non-HERMES project (Aegis), so the request got handled by an
# ad-hoc skill instead of routing through skills/create -> skills/webdev.
# Skill-matching is a judgment call the model makes per turn; it is not a
# hard gate. This hook is the harder gate: it injects a system reminder into
# EVERY turn's context, regardless of what the model would have picked on
# its own, per Claude Code's UserPromptSubmit -> additionalContext mechanism
# (code.claude.com/docs/en/hooks, verified 2026-07-13).
#
# This does NOT force a tool call — hooks cannot invoke skills directly, only
# inject context. It cannot be a true 100% guarantee, only the strongest
# nudge the platform exposes. Deliberately non-blocking (exit 0 always):
# blocking every prompt over a routing preference would break plain
# conversation, which is not what was asked for.
#
# stdin:  JSON { prompt, session_id, cwd, hook_event_name: "UserPromptSubmit", ... }
# stdout: JSON with hookSpecificOutput.additionalContext (exit 0 only —
#         UserPromptSubmit JSON is only read on exit 0, per platform contract).

INPUT="$(cat)"

# Fail silent-safe, not fail-closed: this is a nudge, not a security gate.
# An empty/malformed prompt still lets the turn proceed normally.
if [ -z "$INPUT" ]; then
    exit 0
fi

if command -v python3 >/dev/null 2>&1; then
    python3 -c '
import json, os, sys
try:
    d = json.load(sys.stdin)
    prompt = d.get("prompt", "")
    cwd = d.get("cwd", "") or ""
except Exception:
    prompt = ""
    cwd = ""

reminder = (
    "HERMES plugin is active in this session (any project folder, CLI or Cowork). "
    "Apollo (hermes/SKILL.md) is the required first stop for this request per its "
    "routing table (Section 3) — classify intent there before reaching for any "
    "standalone skill directly. This applies in EVERY project, not only ones named "
    "or referencing HERMES: a plain \"build me a website/app/report/deck\" request "
    "still routes through skills/create -> the matching sub-skill (webdev, documents, "
    "research, tasks) BEFORE freelancing with frontend-design or any other skill on "
    "its own. If Apollo genuinely does not apply to this request (casual conversation, "
    "a direct factual question), proceeding without it is fine — just do not silently "
    "skip it for anything that is actually a create/build/make request."
)

# Per-project decision/flow log (skills/create §3b scaffolds these for
# website/mobile/tool projects). Checked from disk every turn, not just at
# SessionStart, so it survives context compaction and new chats in the same
# project — the actual problem this was built to solve (2026-08-11).
try:
    if cwd and os.path.isfile(os.path.join(cwd, "hermes", "decisions.md")):
        reminder += (
            " This project has hermes/decisions.md and hermes/flow.md — append "
            "any non-obvious decision (library choice, architecture, rejected "
            "alternative) to decisions.md and update flow.md when the entry "
            "point or call order changes; never create a new dated copy of "
            "either file. Before asking the user to accept a major change, "
            "quiz yourself on it first — what it does, why this approach over "
            "the alternatives, what it risks — and only ask for acceptance if "
            "you would pass."
        )
except Exception:
    pass

out = {
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": reminder
    }
}
print(json.dumps(out))
' <<< "$INPUT"
fi

exit 0
