#!/usr/bin/env python3
"""
meta/palimpsest.py — Palimpsest: strips AI-provenance watermarks (invisible
Unicode, EXIF/C2PA-looking image metadata, OOXML/PDF document properties,
HTML/SVG generator tags) from files HERMES writes. Named for a manuscript
scraped clean of earlier writing so the surface can be reused — HERMES
renames on integration, same convention as Apollo, Mnemos, Clio, Laconic,
Occam (see SKILL.md §9: no code copied from any analyzed repo, patterns
only). Source project: a third-party watermark-removal tool (extracted
patterns, HERMES integration 2026-08-23).

Architecturally different from Laconic/Occam, disclosed not silent: those
two change how the MODEL behaves (a per-turn instruction injected into
context). Palimpsest changes nothing about how the model talks — it is a
mechanical PostToolUse hook that rewrites a file on disk right after
Write/Edit produces it. There is no hook event in this platform that
intercepts the assistant's own chat text before it reaches the user, so
Palimpsest cannot and does not claim to scrub live conversational output —
only files that actually get written. Say this plainly if asked "does this
mean nothing HERMES outputs ever carries a watermark" — the honest answer
is "every file it writes, yes; the chat reply itself, no, that path isn't
exposed by the hook system."

Two runtime levels plus off:
  safe       (default) — Layer A invisible-Unicode strip + all metadata
             stripping. Never rewrites a visible character.
  aggressive — safe, plus folds Cyrillic/fullwidth-Latin confusables in
             plain-text files. This DOES rewrite visible characters, so it
             is not the default — only turn it on for content known to be
             Latin-script that acquired lookalike substitutions.
  off        — hook still fires but performs no I/O.
"""
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT / "integrations" / "palimpsest"))

RUNTIME_MODES = {"off", "safe", "aggressive"}
DEFAULT_MODE = "safe"


# --- Flag file IPC (same pattern as meta/laconic.py / meta/occam.py) -----

def _config_dir() -> Path:
    d = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(d) if d else Path.home() / ".claude"


FLAG_PATH = _config_dir() / ".hermes-palimpsest-active"
MAX_FLAG_BYTES = 32


def safe_write_flag(mode: str) -> None:
    if mode not in RUNTIME_MODES:
        return
    FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(FLAG_PATH.parent), prefix=".palimpsest-tmp-")
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


def read_flag() -> str | None:
    try:
        if not FLAG_PATH.exists():
            return None
        st = FLAG_PATH.lstat()
        if stat.S_ISLNK(st.st_mode) or st.st_size > MAX_FLAG_BYTES:
            return None
        cleaned = re.sub(r"[^a-z-]", "", FLAG_PATH.read_text(errors="ignore").strip().lower())
        return cleaned if cleaned in RUNTIME_MODES else None
    except OSError:
        return None


# --- Config precedence: env var > config file > DEFAULT_MODE ("safe") ---
# Same shape as meta/occam.py's default_mode(), so Palimpsest starts ON by
# default (the ambient guarantee the user asked for) unless explicitly
# configured off, mirroring how Occam defaults to "full" rather than "off".

def _external_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "palimpsest"
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "palimpsest"
    return Path.home() / ".config" / "palimpsest"


def default_mode() -> str:
    env_mode = (os.environ.get("PALIMPSEST_DEFAULT_MODE") or "").strip().lower()
    if env_mode in RUNTIME_MODES:
        return env_mode
    try:
        data = json.loads((_external_config_dir() / "config.json").read_text(encoding="utf-8"))
        file_mode = str(data.get("defaultMode", "")).strip().lower()
        if file_mode in RUNTIME_MODES:
            return file_mode
    except Exception:
        pass
    return DEFAULT_MODE


def write_default_mode(mode: str) -> str | None:
    if mode not in RUNTIME_MODES:
        return None
    cfg_dir = _external_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.json"
    config = {}
    try:
        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            config = loaded
    except Exception:
        pass
    config["defaultMode"] = mode
    cfg_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return mode


def current_mode() -> str:
    flagged = read_flag()
    return flagged if flagged is not None else default_mode()


# --- /palimpsest command + activation phrases ----------------------------

def parse_palimpsest_command(prompt: str):
    p = (prompt or "").strip().lower()
    if not re.match(r"^[/@$]palimpsest\b", p):
        return (None, None)
    parts = p.split()
    arg = parts[1] if len(parts) > 1 else ""
    if arg == "default":
        dmode = parts[2] if len(parts) > 2 else ""
        return ("default", dmode) if dmode in RUNTIME_MODES else (None, None)
    if arg in RUNTIME_MODES:
        return ("set", arg)
    if arg == "":
        return ("report", None)
    return (None, None)


_DEACTIVATE_RE = re.compile(
    r"^(stop palimpsest|palimpsest off|disable watermark cleaning|disable palimpsest)[.!]?$",
    re.IGNORECASE,
)
_ACTIVATE_RE = re.compile(
    r"^(start palimpsest|palimpsest on|enable watermark cleaning|enable palimpsest)[.!]?$",
    re.IGNORECASE,
)


def is_deactivation_command(text: str) -> bool:
    return bool(_DEACTIVATE_RE.match((text or "").strip()))


def is_activation_command(text: str) -> bool:
    return bool(_ACTIVATE_RE.match((text or "").strip()))


# --- Visible banner (additionalContext is hidden context — same fix as
# meta/laconic.py / meta/occam.py's visible_banner()) --------------------

def visible_banner(mode: str) -> str:
    return (
        'SYSTEM INSTRUCTION: as the very first line of your next reply, '
        f'output exactly this (nothing before it): "PALIMPSEST STARTED — mode: {mode}". '
        'Then continue your reply normally on the next line.'
    )


def handle_session_start() -> str:
    mode = default_mode()
    if mode == "off":
        safe_write_flag("off")
        return ""
    safe_write_flag(mode)
    return (
        f"{visible_banner(mode)}\n\n"
        f"Palimpsest is active (mode: {mode}). Every file Write/Edit produces this "
        "session is scanned right after it's written and stripped of invisible-"
        "Unicode carriers and known AI-provenance metadata (PNG/JPEG ancillary "
        "chunks, OOXML docProps, PDF Info/XMP, HTML/SVG generator tags). This does "
        "NOT touch your own chat replies before they're shown — no hook in this "
        "platform can intercept that text — only files actually written to disk. "
        "\"stop palimpsest\" turns it off for this session; \"/palimpsest aggressive\" "
        "additionally folds Cyrillic/fullwidth-Latin lookalike characters in plain "
        "text (visible-character rewrite — off by default on purpose)."
    )


def handle_turn(prompt: str) -> str | None:
    kind, arg = parse_palimpsest_command(prompt)
    if kind == "default":
        write_default_mode(arg)
        return f"PALIMPSEST DEFAULT SET — new sessions start in {arg}."
    if kind == "set":
        safe_write_flag(arg)
        if arg == "off":
            return "PALIMPSEST MODE OFF"
        return f"{visible_banner(arg)}\n\nPALIMPSEST MODE CHANGED — level: {arg}"
    if kind == "report":
        return f"PALIMPSEST MODE ACTIVE — level: {current_mode()}"

    if is_deactivation_command(prompt):
        was_on = current_mode() != "off"
        safe_write_flag("off")
        return "PALIMPSEST MODE OFF" if was_on else None
    if is_activation_command(prompt):
        safe_write_flag("safe")
        return f"{visible_banner('safe')}\n\nPALIMPSEST MODE CHANGED — level: safe"
    return None


# --- PostToolUse: the actual enforcement ---------------------------------

def handle_post_tool_use(tool_name: str, file_path: str | None) -> str | None:
    if tool_name not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return None
    if not file_path:
        return None
    mode = current_mode()
    if mode == "off":
        return None
    try:
        import format_route
    except ImportError:
        return None  # engine not importable — fail silent-safe, never block the write

    try:
        result = format_route.clean_path(
            Path(file_path), in_place=True, aggressive=(mode == "aggressive")
        )
    except Exception:
        return None  # never let a malformed input file turn into a blocked write

    if result.get("status") != "cleaned" or not result.get("actions"):
        return None
    joined = "; ".join(result["actions"][:4])
    return f"Palimpsest cleaned {file_path}: {joined}"


if __name__ == "__main__":
    event = sys.argv[1] if len(sys.argv) > 1 else "UserPromptSubmit"

    if event == "SessionStart":
        ctx = handle_session_start()
        if ctx:
            print(ctx)
        sys.exit(0)

    try:
        raw = sys.stdin.read().lstrip("﻿")
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    if event == "PostToolUse":
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        file_path = tool_input.get("file_path") or tool_input.get("path")
        note = handle_post_tool_use(tool_name, file_path)
        if note:
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": note,
                }
            }))
        sys.exit(0)

    # UserPromptSubmit
    ctx = handle_turn(data.get("prompt", ""))
    if ctx:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": ctx,
            }
        }))
    sys.exit(0)
