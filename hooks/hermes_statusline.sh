#!/usr/bin/env bash
# hermes_statusline.sh — combined mode badge for HERMES's flag-file-backed
# behavioral modes (Occam, Laconic). Ported from the source project's own
# ponytail-statusline.sh (single-mode badge), extended to read both flags
# since HERMES now has two independent modes sharing the same IPC pattern
# (meta/occam.py, meta/laconic.py). Not wired automatically — plugins can't
# write to a user's own ~/.claude/settings.json statusLine key themselves;
# hooks/occam_activate.sh nudges the user to add it once, same as the
# source project's own SessionStart nudge.
#
# CLAUDE_CONFIG_DIR overrides ~/.claude, matching where the hooks write
# both flags.

dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
occam_flag="$dir/.hermes-occam-active"
laconic_flag="$dir/.hermes-laconic-active"

out=""

if [ -f "$occam_flag" ]; then
    mode=$(head -n1 "$occam_flag" | tr -d '[:space:]')
    color=108
    [ "$mode" = "ultra" ] && color=173
    [ "$mode" = "review" ] && color=110
    if [ -z "$mode" ] || [ "$mode" = "full" ]; then
        out="${out}\033[38;5;${color}m[OCCAM]\033[0m "
    else
        upper=$(printf '%s' "$mode" | tr '[:lower:]' '[:upper:]')
        out="${out}\033[38;5;${color}m[OCCAM:${upper}]\033[0m "
    fi
fi

if [ -f "$laconic_flag" ]; then
    mode=$(head -n1 "$laconic_flag" | tr -d '[:space:]')
    out="${out}\033[38;5;150m[LACONIC]\033[0m "
fi

printf '%b' "$out"
