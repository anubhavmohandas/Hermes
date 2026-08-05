#!/usr/bin/env bash
# verify.sh — PreToolUse hook. Layer 2 of HERMES architecture.
# Fires at the platform level before every tool call. Cannot be bypassed by
# any prompt — a hook returning non-zero blocks the call regardless of what
# the model was told to do.
#
# stdin:  JSON { tool_name, tool_input, event: "PreToolUse", ... }
# stdout: human-readable status (also echoed to stderr on block, per hook convention)
# exit 0 = ALLOW, exit 2 = BLOCK.
#   Claude Code's PreToolUse contract: ONLY exit 2 blocks the tool call (stderr
#   is fed back to the model). Exit 0 allows; ANY OTHER non-zero code is a
#   NON-BLOCKING error — the tool call proceeds. So every fail-closed path here
#   MUST exit 2, never 1, or the gate fails open. (Verified against
#   code.claude.com/docs/en/hooks, 2026-07-05.)
#
# Chains two independent checks — either can block:
#   Layer A: brain.py       — tier/sensitivity classification + model enforcement
#   Layer B: meta/security/gate.py — 7-layer defense-in-depth dispatch

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRAIN="$HERMES_ROOT/brain.py"
GATE="$HERMES_ROOT/meta/security/gate.py"

# python3 is the only hard dependency. jq was removed 2026-07-05 (audit L2): a
# missing jq used to fail closed on EVERY tool call with a confusing "malformed
# JSON" message. python3 is already required by brain.py/gate.py, so parsing
# JSON with it keeps the hook functional wherever the gate can run at all.
if ! command -v python3 >/dev/null 2>&1; then
    echo "verify.sh: ERROR — python3 not found; cannot run the security gate. Failing closed (BLOCK)." >&2
    exit 2
fi

# Extract one top-level field from a JSON blob on stdin. $1=key $2=default.
json_field() {
    python3 -c 'import json,sys
try:
    print(json.load(sys.stdin).get(sys.argv[1], sys.argv[2]))
except Exception:
    print(sys.argv[2])' "$1" "$2" 2>/dev/null
}

INPUT="$(cat)"

if [ -z "$INPUT" ]; then
    echo "verify.sh: ERROR — empty stdin, cannot verify. Failing closed (BLOCK)." >&2
    exit 2
fi

# Parse tool_name + a flat task description in one python3 pass. This ALSO
# validates the JSON: a parse failure exits nonzero and we fail closed.
PARSED=$(printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(3)
tn = d.get("tool_name") or "unknown"
ti = d.get("tool_input") or {}
try:
    desc = " ".join(f"{k}={v}" for k, v in ti.items())
except Exception:
    desc = ""
desc = " ".join(str(desc).split())  # collapse newlines/whitespace to single spaces
# Cap before this becomes an argv below. A Write of a >1MB file made the whole
# tool_input exceed ARG_MAX, brain.py failed to exec, and the hook fail-closed
# on a perfectly ordinary large write (reproduced 2026-08-05 at 1.5MB; 900KB
# passed). Layer A cannot block on task content anyway — only
# check_model_allowed blocks, and that reads --model, not --task — so the cap
# costs nothing enforcement-side. Layer B still sees the FULL input on stdin.
print(tn)
print(desc[:100000])
')
if [ $? -ne 0 ]; then
    echo "verify.sh: ERROR — malformed JSON on stdin. Failing closed (BLOCK)." >&2
    exit 2
fi
{ read -r TOOL_NAME; read -r TASK_DESC; } <<< "$PARSED"
[ -z "$TASK_DESC" ] && TASK_DESC="$TOOL_NAME"

MODEL="${HERMES_MODEL:-claude-sonnet-5}"

# --- Layer A: brain.py tier / sensitivity check ---
BRAIN_OUT=$(python3 "$BRAIN" check --task "$TASK_DESC" --model "$MODEL" 2>&1)
BRAIN_EXIT=$?

if [ "$BRAIN_EXIT" -ne 0 ]; then
    echo "verify.sh: BLOCKED — brain.py tier check failed (tool=$TOOL_NAME)" >&2
    echo "$BRAIN_OUT" >&2
    exit 2
fi

# --- Layer B: meta/security 7-layer gate ---
GATE_OUT=$(echo "$INPUT" | python3 "$GATE")
GATE_EXIT=$?

if [ "$GATE_EXIT" -ne 0 ]; then
    echo "verify.sh: BLOCKED — meta/security gate failed (tool=$TOOL_NAME)" >&2
    echo "$GATE_OUT" >&2
    GATE_REASON=$(printf '%s' "$GATE_OUT" | json_field reason "unknown")
    python3 "$BRAIN" log-failure --task "$TASK_DESC" --category validation --rule "$GATE_REASON" >/dev/null 2>&1
    exit 2
fi

# Native bash regex, not another python3 spawn: this runs on EVERY allowed tool
# call and only feeds a log line, so it must not cost a process. json_field is
# still used on the block path, where one extra spawn is affordable.
TIER="?"
[[ "$BRAIN_OUT" =~ \"tier\":[[:space:]]*([0-9]+) ]] && TIER="${BASH_REMATCH[1]}"
echo "verify.sh: ALLOWED (tool=$TOOL_NAME, tier=$TIER)" >&2
exit 0
