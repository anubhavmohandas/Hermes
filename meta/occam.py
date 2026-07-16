#!/usr/bin/env python3
"""
meta/occam.py — Occam mode: forces the laziest solution that actually
works (YAGNI -> reuse -> stdlib -> native -> installed dep -> one line ->
minimum code). Named for Occam's razor, not the source project's own name
— HERMES renames on integration (Apollo, Mnemos, Clio, Laconic).

Pattern source (reimplemented fresh, no code copied): a third-party
plugin's "lazy senior dev" ladder + mode-tracking architecture. That
project's own reference Python port (`__init__.py`, written for an
unrelated third-party agent gateway product that happens to also be
named "Hermes" — pure name collision, not this project) supplied the
mode-filtering algorithm this file's filter_skill_body_for_mode() is
adapted from; the Node.js hook files supplied the SessionStart /
UserPromptSubmit / SubagentStart wiring shape, ported to HERMES's
existing bash-wrapper + meta/*.py convention (see meta/laconic.py).

Four levels: off, lite, full (default), ultra, plus an independent
session mode "review" (entered only via /occam-review, never a default).

Deliberate deviation from the source project, disclosed not silent:
the source only re-injects its ruleset at SessionStart + on an explicit
mode switch, relying on that context persisting for the whole session.
HERMES's own established doctrine (see hooks/apollo_gate.sh, pattern
#161 in CC_SRC_PATTERNS.md, applied identically in meta/laconic.py) is
that long sessions and competing hook injections cause drift without
per-turn reinforcement. So UserPromptSubmit here also emits a short
one-line reminder every turn while active — not the full ladder text
every turn, which would be the exact bloat this module exists to avoid.
"""
import os
import re
import stat
import tempfile
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = HERMES_ROOT / "skills"
OCCAM_SKILL = SKILLS_DIR / "occam" / "SKILL.md"
REVIEW_SKILL = SKILLS_DIR / "occam-review" / "SKILL.md"

DEFAULT_MODE = "full"
RUNTIME_MODES = {"off", "lite", "full", "ultra"}
CONFIG_MODES = RUNTIME_MODES | {"review"}


# --- Flag file IPC (same pattern as meta/laconic.py's #162) ---------------

def _config_dir() -> Path:
    d = os.environ.get("CLAUDE_CONFIG_DIR")
    if d:
        return Path(d)
    return Path.home() / ".claude"

FLAG_PATH = _config_dir() / ".hermes-occam-active"
MAX_FLAG_BYTES = 64


def safe_write_flag(mode: str) -> None:
    if mode not in RUNTIME_MODES and mode != "review":
        return
    FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(FLAG_PATH.parent), prefix=".occam-tmp-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(mode)
        try:
            if FLAG_PATH.is_symlink():
                FLAG_PATH.unlink()
        except FileNotFoundError:
            pass
        os.replace(tmp_path, FLAG_PATH)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def clear_flag() -> None:
    try:
        FLAG_PATH.unlink()
    except FileNotFoundError:
        pass


def read_flag() -> str | None:
    try:
        if not FLAG_PATH.exists():
            return None
        st = FLAG_PATH.lstat()
        if stat.S_ISLNK(st.st_mode):
            return None
        if st.st_size > MAX_FLAG_BYTES:
            return None
        raw = FLAG_PATH.read_text(errors="ignore")
        cleaned = re.sub(r"[^a-z0-9-]", "", raw.strip().lower())
        return cleaned if cleaned in CONFIG_MODES else None
    except OSError:
        return None


# --- Config resolution: env var > config file > default -------------------
# Mirrors the source project's own precedent, ported so a user's existing
# ~/.config/occam/config.json (or XDG_CONFIG_HOME) keeps working the same
# way ~/.config/ponytail/config.json did — same shape, renamed directory.

def _external_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "occam"
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "occam"
    return Path.home() / ".config" / "occam"


def _normalize_runtime_mode(mode) -> str | None:
    if not isinstance(mode, str):
        return None
    m = mode.strip().lower()
    return m if m in RUNTIME_MODES else None


def _normalize_config_mode(mode) -> str | None:
    if not isinstance(mode, str):
        return None
    m = mode.strip().lower()
    return m if m in CONFIG_MODES else None


def default_mode() -> str:
    env_mode = _normalize_config_mode(os.environ.get("OCCAM_DEFAULT_MODE"))
    if env_mode:
        return env_mode
    try:
        import json
        data = json.loads((_external_config_dir() / "config.json").read_text(encoding="utf-8"))
        file_mode = _normalize_config_mode(data.get("defaultMode"))
        if file_mode:
            return file_mode
    except Exception:
        pass
    return DEFAULT_MODE


def write_default_mode(mode: str) -> str | None:
    normalized = _normalize_runtime_mode(mode)
    if not normalized:
        return None
    import json
    cfg_dir = _external_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.json"
    config = {}
    try:
        config = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            config = {}
    except Exception:
        pass
    config["defaultMode"] = normalized
    cfg_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return normalized


# --- Deactivation phrase (standalone match only, not substring) -----------

def is_deactivation_command(text: str) -> bool:
    t = re.sub(r"[.!?\s]+$", "", (text or "").strip().lower())
    return t in ("stop occam", "normal mode")


# --- /occam command parsing -------------------------------------------

def parse_occam_command(prompt: str):
    """Returns (kind, mode) where kind is one of:
    'set' (runtime mode change), 'off', 'report', 'default', 'review',
    or None if this prompt isn't an /occam[-*] command."""
    p = (prompt or "").strip().lower()
    if not re.match(r"^[/@$]occam", p):
        return (None, None)
    parts = p.split()
    cmd = re.sub(r"^[@$]", "/", parts[0])
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/occam-review", "/occam:occam-review"):
        return ("review", None)
    if cmd not in ("/occam", "/occam:occam"):
        return (None, None)

    if arg == "default":
        dmode = parts[2] if len(parts) > 2 else ""
        if dmode in RUNTIME_MODES:
            return ("default", dmode)
        return (None, None)
    if arg in ("lite", "full", "ultra"):
        return ("set", arg)
    if arg == "off":
        return ("off", None)
    if arg == "":
        return ("report", None)
    return (None, None)


# --- Skill-body mode filtering (ported from the source's own Python
# reference implementation almost verbatim — same regex shape) -----------

def strip_frontmatter(text: str) -> str:
    return re.sub(r"^---[\s\S]*?---\s*", "", text or "", count=1)


def filter_skill_body_for_mode(body: str, mode: str) -> str:
    effective = _normalize_runtime_mode(mode) or DEFAULT_MODE
    lines = []
    for line in strip_frontmatter(body).splitlines():
        table_label = re.match(r"^\|\s*\*\*(.+?)\*\*\s*\|", line)
        if table_label:
            label_mode = _normalize_runtime_mode(table_label.group(1))
            if label_mode and label_mode != effective:
                continue
        example_label = re.match(r'^-\s*([^:]+):\s*"', line)
        if example_label:
            label_mode = _normalize_runtime_mode(example_label.group(1))
            if label_mode and label_mode != effective:
                continue
        lines.append(line)
    return "\n".join(lines)


def fallback_instructions(mode: str) -> str:
    return (
        f"OCCAM MODE ACTIVE — level: {mode}\n\n"
        "You are a lazy senior developer. Lazy means efficient, not careless. "
        "The best code is the code never written.\n\n"
        "Before any code, stop at the first rung that holds (read the code the "
        "change touches and trace the real flow first — the ladder shortens the "
        "solution, never the reading):\n"
        "1. Does this need to exist at all? (YAGNI)\n"
        "2. Already in this codebase? Reuse it.\n"
        "3. Stdlib does it? Use it.\n"
        "4. Native platform feature covers it? Use it.\n"
        "5. Already-installed dependency solves it? Use it.\n"
        "6. Can it be one line? One line.\n"
        "7. Only then: the minimum code that works.\n\n"
        "Bug fix = root cause: grep every caller before patching just the one "
        "the ticket names.\n\n"
        "Never simplify away: input validation at trust boundaries, "
        "error handling that prevents data loss, security, accessibility, "
        "anything explicitly requested. Non-trivial logic leaves one runnable "
        "check behind."
    )


def build_injected_context(mode: str | None = None) -> str:
    configured = _normalize_config_mode(mode) or default_mode()
    if configured == "off":
        return ""
    if configured == "review":
        try:
            body = REVIEW_SKILL.read_text(encoding="utf-8")
            return f"OCCAM MODE ACTIVE — level: review\n\n{strip_frontmatter(body)}"
        except OSError:
            return "OCCAM MODE ACTIVE — level: review. Review diffs for unnecessary complexity."

    effective = _normalize_runtime_mode(configured) or DEFAULT_MODE
    try:
        body = OCCAM_SKILL.read_text(encoding="utf-8")
        return f"OCCAM MODE ACTIVE — level: {effective}\n\n{filter_skill_body_for_mode(body, effective)}"
    except OSError:
        return fallback_instructions(effective)


def per_turn_reminder(mode: str) -> str:
    """Short reinforcement, NOT the full ladder text — re-injecting the
    entire skill body every turn would be the exact bloat this module
    exists to cut. Deliberate deviation from the source's SessionStart-
    only design, matching meta/laconic.py's drift-resistance doctrine."""
    if mode == "review":
        return "OCCAM MODE ACTIVE — level: review. Reviewing for over-engineering only; see /occam-review."
    return (
        f"OCCAM MODE ACTIVE — level: {mode}. Ladder before code: YAGNI -> reuse "
        "-> stdlib -> native -> installed dep -> one line -> minimum. Never cut "
        "validation, error handling, security, or accessibility."
    )


# --- Statusline first-run nudge (ported from the source's own
# SessionStart nudge: check once, remember the answer via a flag file so
# a declined offer doesn't repeat every session and become a nag) --------

_SHELL_SAFE_RE = re.compile(r"^[A-Za-z0-9 _.\-:/\\~]+$")


def _is_shell_safe(p: str) -> bool:
    return bool(_SHELL_SAFE_RE.match(p or ""))


def statusline_nudge() -> str:
    settings_path = _config_dir() / "settings.json"
    nudge_flag = _config_dir() / ".hermes-statusline-nudged"
    try:
        has_statusline = False
        if settings_path.exists():
            import json
            raw = settings_path.read_text(encoding="utf-8").lstrip("﻿")
            settings = json.loads(raw)
            has_statusline = bool(settings.get("statusLine"))

        if has_statusline or nudge_flag.exists():
            return ""

        try:
            nudge_flag.write_text("")
        except OSError:
            pass

        script_path = str(HERMES_ROOT / "hooks" / "hermes_statusline.sh")
        if _is_shell_safe(script_path):
            command = f'bash "{script_path}"'
            snippet = '"statusLine": { "type": "command", "command": ' + \
                _json_dumps(command) + ' }'
            return (
                "\n\nSTATUSLINE SETUP AVAILABLE: HERMES ships a statusline badge "
                f"showing active Occam/Laconic mode (e.g. [OCCAM], [OCCAM:ULTRA], "
                f"[LACONIC]). Not configured yet. To enable, add this to "
                f"{settings_path}: {snippet} Proactively offer to set this up "
                "for the user on first interaction; this is a one-time nudge, "
                "not shown again."
            )
        return (
            "\n\nSTATUSLINE SETUP AVAILABLE: HERMES ships a statusline badge for "
            "Occam/Laconic mode, but its install path has characters unsafe to "
            f"embed in a shell command snippet. Configure manually: point a "
            f"statusLine command at hooks/hermes_statusline.sh in {settings_path}."
        )
    except OSError:
        return ""


def _json_dumps(s: str) -> str:
    import json
    return json.dumps(s)


# --- SessionStart entrypoint --------------------------------------------

def handle_session_start() -> str:
    mode = default_mode()
    if mode == "off":
        clear_flag()
        return ""
    safe_write_flag(mode)
    return build_injected_context(mode) + statusline_nudge()


# --- UserPromptSubmit entrypoint ----------------------------------------

def handle_turn(prompt: str) -> str | None:
    kind, arg = parse_occam_command(prompt)

    if kind == "default":
        write_default_mode(arg)
        return f"OCCAM DEFAULT SET — new sessions start in {arg}."
    if kind == "off":
        clear_flag()
        return "OCCAM MODE OFF"
    if kind == "set":
        safe_write_flag(arg)
        return f"OCCAM MODE CHANGED — level: {arg}\n\n{build_injected_context(arg)}"
    if kind == "review":
        safe_write_flag("review")
        return f"OCCAM MODE CHANGED — level: review\n\n{build_injected_context('review')}"
    if kind == "report":
        mode = read_flag() or default_mode()
        return f"OCCAM MODE ACTIVE — level: {mode}"

    if is_deactivation_command(prompt):
        was_active = read_flag() is not None
        clear_flag()
        return "OCCAM MODE OFF" if was_active else None

    mode = read_flag()
    if mode is None or mode == "off":
        return None
    return per_turn_reminder(mode)


# --- SubagentStart entrypoint -------------------------------------------
# SessionStart context is parent-thread only and never reaches subagents
# (same gap the source project's own SubagentStart hook exists to close),
# so a Task-spawned agent runs Occam-unaware without this.
#
# Scoping (opt-in, ported from the source's own issue #506): set
# OCCAM_SUBAGENT_MATCHER to a regex and injection is limited to subagents
# whose agent_type matches. Unanchored, case-insensitive. Unset means
# inject into every subagent (default). A bad regex, a missing agent_type,
# or any uncertainty must fail OPEN (inject) — silently dropping the
# persona is worse than an unwanted extra injection.

def handle_subagent_start(agent_type: str = None) -> str:
    mode = read_flag()
    if not mode or mode == "off":
        return ""

    matcher_pattern = os.environ.get("OCCAM_SUBAGENT_MATCHER")
    if matcher_pattern:
        try:
            matcher = re.compile(matcher_pattern, re.IGNORECASE)
        except re.error:
            matcher = None  # invalid regex -> fail open, treat as no matcher
        if matcher is not None and agent_type:
            if not matcher.search(agent_type):
                return ""
        # missing agent_type with a matcher set -> fail open, inject anyway

    return build_injected_context(mode)


if __name__ == "__main__":
    import json
    import sys

    event = sys.argv[1] if len(sys.argv) > 1 else "UserPromptSubmit"

    if event == "SessionStart":
        ctx = handle_session_start()
        if ctx:
            print(ctx)
    elif event == "SubagentStart":
        # Only read stdin when a matcher is configured — the default path
        # must stay stdin-independent and synchronous (a Windows PowerShell
        # wrapper can swallow piped JSON so stdin 'end' never fires, per the
        # source project's own issue #443; the no-matcher case must not
        # depend on it or every subagent spawn would risk hanging).
        agent_type = None
        if os.environ.get("OCCAM_SUBAGENT_MATCHER"):
            try:
                raw = sys.stdin.read().lstrip("﻿")
                agent_type = str(json.loads(raw).get("agent_type", "") or "").strip()
            except Exception:
                agent_type = None
        ctx = handle_subagent_start(agent_type)
        if ctx:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "SubagentStart",
                    "additionalContext": ctx,
                }
            }))
    else:
        try:
            # Strip a UTF-8 BOM some shells/editors prepend when piping on
            # Windows — breaks json.loads otherwise (ported robustness fix).
            raw = sys.stdin.read().lstrip("﻿")
            data = json.loads(raw)
            prompt = data.get("prompt", "")
        except Exception:
            prompt = ""
        ctx = handle_turn(prompt)
        if ctx:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": ctx,
                }
            }))
