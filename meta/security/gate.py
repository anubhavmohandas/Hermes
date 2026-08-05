#!/usr/bin/env python3
"""
gate.py — combines all 7 security layers into one dispatcher keyed on tool_name.
This is what hooks/verify.sh actually shells out to for the meta/security checks
(brain.py handles tier/sensitivity separately — see hooks/verify.sh for the
full chain). Any one layer can block; layers are independent, per
hermes-agent P16 "defense in depth" design intent.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import file_safety
import path_security
import url_safety
import skills_guard
import approval
import approval_token
import tirith_security
import redact

HERMES_ROOT = Path(__file__).resolve().parents[2]
# Boundary contract (V1_CHECKLIST §2) lives in the frozen meta/ kernel.
sys.path.insert(0, str(HERMES_ROOT))
from meta.contracts import SecurityDecision  # noqa: E402

# Interpreters whose first path argument is what actually gets executed.
_INTERPRETERS = {"bash", "sh", "zsh", "dash", "python", "python3", "node", "ruby", "perl", "source"}


def _extract_exec_paths(cmd: str):
    """File paths a shell command would execute: the head of each pipeline
    segment when it's path-like (./x, /usr/bin/x), plus the first non-flag
    argument after a known interpreter (bash x.sh, python3 x.py)."""
    paths = []
    for segment in re.split(r"&&|\|\||[;|&]", cmd or ""):
        tokens = segment.strip().split()
        if not tokens:
            continue
        head = tokens[0]
        if "/" in head:
            paths.append(head)
        elif head in _INTERPRETERS:
            for t in tokens[1:]:
                if not t.startswith("-"):
                    paths.append(t)
                    break
    return paths


def _resolve_write_path(path: str) -> str:
    """Absolute, normalized form of a write target, for denylist matching.
    Relative paths resolve against the CWD, which is what the tool itself
    does. strict=False so a not-yet-existing file still normalizes; on any
    resolution failure the original string is returned so the denylist still
    gets its best look at it rather than the check being skipped."""
    if not path:
        return path
    try:
        return str(Path(path).expanduser().resolve())
    except (OSError, RuntimeError, ValueError):
        return path


def _is_skill_path(path: str) -> bool:
    if not path:
        return False
    p = Path(path)
    return "skills" in p.parts or ".claude-plugin" in p.parts or p.name.lower() == "skill.md"


# Shell constructs that write to a file whose path is visible in the command:
# redirects, tee, cp/mv destinations, sed -i targets, dd of=, install -m.
# Regex-level extraction cannot fully parse shell semantics (quoting, var
# expansion, exotic generators) — that's exactly WHY matches are blocked
# outright rather than content-scanned; see the bash branch below.
_WRITE_TARGET_PATTERNS = [
    re.compile(r"(?<!<)(?<!\d)>{1,2}\s*([^\s;|&<>()]+)"),          # > file, >> file (not <<EOF, not 2>&1)
    re.compile(r"\btee\s+(?:-[a-zA-Z]+\s+)*([^\s;|&]+)"),
    re.compile(r"\b(?:cp|mv)\s+(?:-\S+\s+)*\S+\s+([^\s;|&]+)"),
    re.compile(r"\bof=([^\s;|&]+)"),                               # dd of=
    re.compile(r"\binstall\s+(?:-\S+\s+)*\S+\s+([^\s;|&]+)"),
    re.compile(r"\s(?:-o|--output|-O)\s+([^\s;|&]+)"),             # curl -o / wget -O download targets
]

# In-place editors take the target file positionally with flag/script args in
# between that vary by platform (macOS `sed -i "" ...` vs GNU `sed -i...`) —
# too shapeshifting for one capture group. When one appears, EVERY token in
# the command becomes a candidate target; the skill-path filter does the rest.
_INPLACE_EDIT_RE = re.compile(r"\b(?:sed|perl|gawk|ex)\s[^;|&]*-\S*i|\bpatch\b|\btruncate\b")


def _extract_write_targets(cmd: str):
    cmd = cmd or ""
    targets = []
    for pattern in _WRITE_TARGET_PATTERNS:
        targets.extend(m.group(1) for m in pattern.finditer(cmd))
    if _INPLACE_EDIT_RE.search(cmd):
        targets.extend(cmd.split())
    return targets


def run_gate(tool_name: str, tool_input: dict):
    """Returns (allowed: bool, layer: str, reason: str)."""
    tool_name = (tool_name or "").lower()

    if tool_name in ("write", "edit"):
        path = tool_input.get("file_path") or tool_input.get("path") or ""
        # Resolve BEFORE the denylist. file_safety matches on path shape, so it
        # saw "../../../../../../etc/hosts" as a literal and missed it — the
        # denylist only ever fired on absolute paths. Resolving first means a
        # target is judged by where it actually lands, however it was spelled.
        blocked, reason = file_safety.is_write_blocked(_resolve_write_path(path))
        if blocked:
            return False, "file_safety", reason
        # Base is the CWD, not HERMES_ROOT. A relative path in a tool call is
        # resolved by the tool against the CWD, so that is the only base with
        # real meaning here; HERMES_ROOT was left over from when HERMES was a
        # single-project tool rather than a globally-installed plugin, and the
        # check was effectively measuring against an unrelated directory.
        #
        # Effect is unchanged and deliberately conservative: ANY relative path
        # escaping upward is refused, including a legitimate "../shared/x.py"
        # in a monorepo. That false positive is kept on purpose — Write/Edit
        # take absolute paths in practice, so this fires almost never, and the
        # alternative (guessing a project root) invents a boundary nobody
        # declared. Pass an absolute path for a sibling directory.
        safe, reason = path_security.check_traversal(str(Path.cwd()), path)
        if not safe and path:
            # Only enforce traversal when a relative path was given; absolute
            # paths outside the CWD are legitimate (the user's own files), and
            # the resolved denylist check above is what guards those.
            if not Path(path).is_absolute():
                return False, "path_security", reason
        # Layer 4 fires HERE — on content being written into a skill file —
        # because "skillinstall" is not a real tool name and the old dispatch
        # on it never ran through the hook (audited 2026-07-02, C1). A full
        # directory sweep also runs at session start (hooks/skills_scan.sh).
        if _is_skill_path(path):
            content = tool_input.get("content") or tool_input.get("new_string") or ""
            if content:
                findings = skills_guard.scan_skill_text(content)
                if findings:
                    return False, "skills_guard", f"skill content quarantined: {findings}"

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
            # D1 closed 2026-07-03 (Option B, docs/DECISIONS.md): the hook is
            # still non-interactive and still fails closed BY DEFAULT — but
            # Apollo can now ask the human via AskUserQuestion BEFORE the
            # Bash call and, on an explicit yes, grant a single-use,
            # command-bound, 300s token (approval_token.grant). That token is
            # the only path through this branch, and checking it consumes it.
            approved, token_reason = approval_token.check_and_consume(cmd)
            if approved:
                return True, "approval", f"{reason} — ALLOWED once: {token_reason}"
            return False, "approval", (f"{reason} — BLOCKED ({token_reason}). "
                                       f"Interactive path: Apollo asks the human, then "
                                       f"approval_token.py grant — see docs/DECISIONS.md D1")
        # Layer 4, bash leg (verified bypass, 2026-07-03): heredoc / tee /
        # cp / sed -i / redirects can write skill files without ever touching
        # the Write/Edit tools, and their true content is NOT derivable from
        # the command string (variable expansion, command substitution, remote
        # fetches) — so content-scanning the command would be false
        # confidence. Fail closed instead: bash may not write to skill paths
        # at all. Skill edits go through Write/Edit, where the exact content
        # is visible and scanned.
        for target in _extract_write_targets(cmd):
            if _is_skill_path(target):
                return False, "skills_guard", (
                    f"bash write to skill path '{target}' blocked — skill file "
                    f"content can't be verified from a shell command. Use the "
                    f"Write/Edit tools, which are content-scanned.")
        # Layer 6 fires HERE — on files the command would execute — because
        # "exec" is not a real tool name and the old dispatch on it never ran
        # through the hook (audited 2026-07-02, C1). Only existing files are
        # scanned: a path that doesn't exist yet can't carry a payload.
        # Honesty note: this checks STRUCTURE (magic bytes vs extension,
        # setuid/setgid), not script logic — a plain #! script with hostile
        # commands inside scans clean. Content protection for commands is
        # approval.py's job, above.
        for exec_path in _extract_exec_paths(cmd):
            p = Path(exec_path).expanduser()
            if p.is_file():
                safe, findings = tirith_security.scan_binary(str(p))
                if not safe:
                    return False, "tirith_security", f"pre-exec scan flagged '{exec_path}': {findings}"

    # "skillinstall" / "exec" are NOT real Claude Code tool names — these two
    # branches only run on manual/scripted invocation. The hook-path wiring
    # for layers 4 and 6 is above (write/edit skill content, bash exec paths).
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


def check(request: dict) -> SecurityDecision:
    """Public contract (V1_CHECKLIST §2): gate.check(request) -> SecurityDecision.

    `request` is the same JSON the hook feeds on stdin:
    {"tool_name": str, "tool_input": dict}. This is a thin, pinned wrapper over
    run_gate() — internals (the 7 layers, their order, the tuple they pass
    around) can be refactored freely as long as this shape holds. run_gate()
    stays for the hook's tuple-unpacking call sites and existing tests.
    """
    verdict = run_gate(request.get("tool_name"), request.get("tool_input", {}) or {})
    return SecurityDecision.from_tuple(verdict)


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
