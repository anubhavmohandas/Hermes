#!/usr/bin/env bash
# verify.sh — PreToolUse hook. Layer 2 of HERMES architecture.
# Fires at the platform level before every tool call. Cannot be bypassed by
# any prompt — a hook returning non-zero blocks the call regardless of what
# the model was told to do.
#
# stdin:  JSON { tool_name, tool_input, event: "PreToolUse", ... }
# stdout: human-readable status (also echoed to stderr on block, per hook convention)
# exit 0 = ALLOW, exit 1 = BLOCK
#
# Chains two independent checks — either can block:
#   Layer A: brain.py       — tier/sensitivity classification + model enforcement
#   Layer B: meta/security/gate.py — 7-layer defense-in-depth dispatch

HERMES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRAIN="$HERMES_ROOT/brain.py"
GATE="$HERMES_ROOT/meta/security/gate.py"

INPUT="$(cat)"

if [ -z "$INPUT" ]; then
    echo "verify.sh: ERROR — empty stdin, cannot verify. Failing closed (BLOCK)." >&2
    exit 1
fi

if ! echo "$INPUT" | jq -e . >/dev/null 2>&1; then
    echo "verify.sh: ERROR — malformed JSON on stdin. Failing closed (BLOCK)." >&2
    exit 1
fi

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
TOOL_INPUT_JSON=$(echo "$INPUT" | jq -c '.tool_input // {}')
TASK_DESC=$(echo "$TOOL_INPUT_JSON" | jq -r 'to_entries | map("\(.key)=\(.value|tostring)") | join(" ")' 2>/dev/null)
[ -z "$TASK_DESC" ] && TASK_DESC="$TOOL_NAME"

MODEL="${HERMES_MODEL:-claude-sonnet-5}"
VIA="${HERMES_MODEL_VIA:-api}"

# --- Layer A: brain.py tier / sensitivity check ---
BRAIN_OUT=$(python3 "$BRAIN" check --task "$TASK_DESC" --model "$MODEL" --via "$VIA" 2>&1)
BRAIN_EXIT=$?

if [ "$BRAIN_EXIT" -ne 0 ]; then
    echo "verify.sh: BLOCKED — brain.py tier check failed (tool=$TOOL_NAME)" >&2
    echo "$BRAIN_OUT" >&2
    exit 1
fi

# --- Layer B: meta/security 7-layer gate ---
GATE_OUT=$(echo "$INPUT" | python3 "$GATE")
GATE_EXIT=$?

if [ "$GATE_EXIT" -ne 0 ]; then
    echo "verify.sh: BLOCKED — meta/security gate failed (tool=$TOOL_NAME)" >&2
    echo "$GATE_OUT" >&2
    GATE_REASON=$(echo "$GATE_OUT" | jq -r '.reason // "unknown"' 2>/dev/null)
    python3 "$BRAIN" log-failure --task "$TASK_DESC" --category validation --rule "$GATE_REASON" >/dev/null 2>&1
    exit 1
fi

echo "verify.sh: ALLOWED (tool=$TOOL_NAME, tier=$(echo "$BRAIN_OUT" | jq -r '.tier'))" >&2
exit 0
