#!/usr/bin/env python3
"""
gate.py — combines all 7 security layers into one dispatcher keyed on tool_name.
This is what hooks/verify.sh actually shells out to for the meta/security checks
(brain.py handles tier/sensitivity separately — see hooks/verify.sh for the
full chain). Any one layer can block; layers are independent, per
hermes-agent P16 "defense in depth" design intent.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import file_safety
import path_security
import url_safety
import skills_guard
import approval
import tirith_security
import redact

HERMES_ROOT = Path(__file__).resolve().parents[2]


def run_gate(tool_name: str, tool_input: dict):
    """Returns (allowed: bool, layer: str, reason: str)."""
    tool_name = (tool_name or "").lower()

    if tool_name in ("write", "edit"):
        path = tool_input.get("file_path") or tool_input.get("path") or ""
        blocked, reason = file_safety.is_write_blocked(path)
        if blocked:
            return False, "file_safety", reason
        safe, reason = path_security.check_traversal(str(HERMES_ROOT), path)
        if not safe and path:
            # Only enforce traversal when a relative path was given; absolute
            # paths outside HERMES_ROOT are legitimate (user's own files).
            if not Path(path).is_absolute():
                return False, "path_security", reason

    if tool_name in ("webfetch", "fetch", "websearch"):
        url = tool_input.get("url", "")
        if url:
            allowed, reason = url_safety.check_url(url)
            if not allowed:
                return False, "url_safety", reason

    if tool_name == "bash":
        cmd = tool_input.get("command", "")
        verdict, reason = approval.classify_command(cmd)
        if verdict == "block":
            return False, "approval", reason
        if verdict == "approval":
            # Audited 2026-07-02 (M1): this DOES hard-block today. PreToolUse
            # hooks are non-interactive — allow/deny only, no mechanism to
            # pause and ask a human mid-call. Fail-safe (deny) is the
            # correct default until a real interactive-approval path exists.
            # See docs/DECISIONS.md for the deferred design (Apollo would
            # need to ask via AskUserQuestion BEFORE invoking Bash, then
            # pass an approval token this hook can check) — not built yet.
            return False, "approval", reason + " — BLOCKED by default (no interactive approval path exists yet; see docs/DECISIONS.md)"

    if tool_name == "skillinstall":
        path = tool_input.get("path", "")
        clean, findings = skills_guard.scan_skill_path(path)
        if not clean:
            return False, "skills_guard", f"quarantined: {findings}"

    if tool_name == "exec":
        path = tool_input.get("path", "")
        safe, findings = tirith_security.scan_binary(path)
        if not safe:
            return False, "tirith_security", f"flagged: {findings}"

    return True, "none", "ALLOWED"


if __name__ == "__main__":
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps({"allowed": False, "layer": "gate", "reason": "malformed JSON input"}))
        sys.exit(1)

    allowed, layer, reason = run_gate(data.get("tool_name"), data.get("tool_input", {}))
    print(json.dumps({"allowed": allowed, "layer": layer, "reason": redact.redact(reason)}))
    sys.exit(0 if allowed else 1)
