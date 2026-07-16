#!/usr/bin/env python3
"""
meta/laconic.py — Laconic mode: opt-in token-reduction behavioral state.
Named for Laconia/Sparta, historically associated with extreme brevity of
speech ("laconic phrase") — not the source project's own name, by design
(HERMES modules are renamed on integration: Apollo, Mnemos, Clio, Curator
follow the same convention).

Pattern source (reimplemented fresh, no code copied): a third-party
plugin's token-reduction mode, extracted patterns #161-166 in
CC_SRC_PATTERNS.md (Task #29).

Three pieces, each independently testable:
  1. Flag-file IPC   — cross-process mode state (#162)
  2. Activation/deactivation phrase detection + reminder text (#161, #164)
  3. Sensitive-path denylist + structural validator for file compression
     (#163, #165) — used by the laconic-compress skill capability, not
     by the per-turn hook.

Caller contract for the hook: call `handle_turn(prompt) -> str | None`.
Returns the additionalContext string to inject, or None if laconic is
inactive and the prompt isn't an activation phrase.
"""
import os
import re
import stat
import tempfile
from pathlib import Path

# --- Flag file IPC (#162) -------------------------------------------------

def _config_dir() -> Path:
    d = os.environ.get("CLAUDE_CONFIG_DIR")
    if d:
        return Path(d)
    return Path.home() / ".claude"

FLAG_PATH = _config_dir() / ".hermes-laconic-active"
VALID_MODES = {"lite", "full", "ultra"}
MAX_FLAG_BYTES = 64


def safe_write_flag(mode: str = "full") -> None:
    """Atomic write via temp file + rename. O_NOFOLLOW guards against a
    symlink swapped in at FLAG_PATH between check and write."""
    if mode not in VALID_MODES:
        mode = "full"
    FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(FLAG_PATH.parent), prefix=".laconic-tmp-"
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(mode)
        # Refuse to replace a symlink at the destination.
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
    """Returns the active mode string, or None if inactive/invalid.
    64-byte size cap, alnum+hyphen only, whitelist-checked."""
    try:
        if not FLAG_PATH.exists():
            return None
        st = FLAG_PATH.lstat()
        if stat.S_ISLNK(st.st_mode):
            return None  # never follow a symlink here
        if st.st_size > MAX_FLAG_BYTES:
            return None
        raw = FLAG_PATH.read_text(errors="ignore")
        cleaned = re.sub(r"[^a-z0-9-]", "", raw.strip().lower())
        return cleaned if cleaned in VALID_MODES else None
    except OSError:
        return None


# --- Activation / deactivation phrase detection (#161) ---------------------

ACTIVATE_RE = re.compile(
    r"\b(go laconic|laconic mode|talk laconic|be (brief|terse)|less tokens|"
    r"fewer tokens|stop wasting tokens)\b",
    re.IGNORECASE,
)
DEACTIVATE_RE = re.compile(
    r"\b(stop laconic|laconic off|normal mode|talk normal(ly)?|be verbose again)\b",
    re.IGNORECASE,
)


def detect_activation(prompt: str) -> bool:
    return bool(ACTIVATE_RE.search(prompt or ""))


def detect_deactivation(prompt: str) -> bool:
    return bool(DEACTIVATE_RE.search(prompt or ""))


# --- Auto-clarity suspension (#164) ----------------------------------------
# Content classification of the CURRENT prompt, not a user command. If any
# of these fire, the injected reminder tells the model to suspend
# compression for this turn only — compression resumes next turn.

CLARITY_OVERRIDE_RE = re.compile(
    r"\b(rm -rf|irreversible|delete (everything|all)|drop table|force push|"
    r"i('m| am) confused|i don't understand|what does that mean|"
    r"security (warning|risk|vulnerability)|are you sure|destructive)\b",
    re.IGNORECASE,
)


def needs_clarity_override(prompt: str) -> bool:
    return bool(CLARITY_OVERRIDE_RE.search(prompt or ""))


# --- Reminder text -----------------------------------------------------

def compression_reminder(mode: str) -> str:
    base = (
        "HERMES laconic mode is ACTIVE (mode: {mode}). Compress every response: "
        "no preamble, no postamble, no restating the question, code/diff first "
        "over narration, one sentence for factual answers unless real complexity "
        "demands more. This reminder re-fires every turn by design (per-turn hook "
        "reinforcement, pattern #161) because long sessions and competing hook "
        "injections cause drift back to verbose output without it."
    ).format(mode=mode)
    return base


def clarity_override_note() -> str:
    return (
        "NOTE: this turn's content matches a safety-critical pattern (destructive "
        "operation, security warning, or user confusion). Laconic compression is "
        "SUSPENDED for this response only — give the full, clear explanation. "
        "Compression resumes automatically next turn (pattern #164)."
    )


def activation_ack(mode: str) -> str:
    return f"Laconic mode activated ({mode}). Flag written to {FLAG_PATH}."


def deactivation_ack() -> str:
    return f"Laconic mode deactivated. Flag removed from {FLAG_PATH}."


# --- Per-turn entrypoint ----------------------------------------------

def handle_turn(prompt: str) -> str | None:
    """Returns additionalContext to inject, or None."""
    if detect_deactivation(prompt):
        was_active = read_flag() is not None
        clear_flag()
        return deactivation_ack() if was_active else None

    if detect_activation(prompt):
        safe_write_flag("full")
        return activation_ack("full")

    mode = read_flag()
    if mode is None:
        return None

    if needs_clarity_override(prompt):
        return clarity_override_note()

    return compression_reminder(mode)


# --- Sensitive-path denylist (#163) — used by laconic-compress -------------

DENYLIST_PATTERNS = [
    r"\.env(\..*)?$", r"\.ssh", r"\.aws", r"\.kube", r"\.gnupg",
    r"credentials.*", r"secrets.*", r"id_rsa.*", r".*\.pem$", r".*\.key$",
]
DENYLIST_RE = [re.compile(p, re.IGNORECASE) for p in DENYLIST_PATTERNS]
MAX_COMPRESS_BYTES = 500 * 1024


def is_denylisted(path: str) -> bool:
    name = Path(path).name
    return any(p.search(name) or p.search(path) for p in DENYLIST_RE)


def can_compress(path: str) -> tuple[bool, str]:
    """Returns (ok, reason). Never reads the file if not ok."""
    p = Path(path)
    if is_denylisted(str(p)):
        return False, f"refused: '{p.name}' matches sensitive-path denylist"
    if p.name.endswith(".original.md"):
        return False, "refused: already a compression backup"
    if p.exists() and p.stat().st_size > MAX_COMPRESS_BYTES:
        return False, f"refused: {p.stat().st_size} bytes exceeds {MAX_COMPRESS_BYTES} cap"
    return True, "ok"


# --- Post-compression structural validation (#165) --------------------

CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
URL_RE = re.compile(r"https?://\S+")
HEADING_RE = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)
BULLET_RE = re.compile(r"^\s*[-*]\s+.*$", re.MULTILINE)


def validate_compression(original: str, compressed: str) -> dict:
    errors = []
    warnings = []

    orig_headings = HEADING_RE.findall(original)
    comp_headings = HEADING_RE.findall(compressed)
    if orig_headings != comp_headings:
        errors.append("heading count/order changed")

    orig_blocks = CODE_FENCE_RE.findall(original)
    comp_blocks = CODE_FENCE_RE.findall(compressed)
    if orig_blocks != comp_blocks:
        errors.append("code block content changed")

    orig_urls = set(URL_RE.findall(original))
    comp_urls = set(URL_RE.findall(compressed))
    if orig_urls != comp_urls:
        errors.append(
            f"URL set changed: added={comp_urls - orig_urls}, removed={orig_urls - comp_urls}"
        )

    orig_bullets = len(BULLET_RE.findall(original))
    comp_bullets = len(BULLET_RE.findall(compressed))
    if orig_bullets and abs(orig_bullets - comp_bullets) / orig_bullets > 0.15:
        warnings.append(f"bullet count changed >15%: {orig_bullets} -> {comp_bullets}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


if __name__ == "__main__":
    import json
    import sys

    try:
        # Strip a UTF-8 BOM some shells/editors prepend when piping on
        # Windows — breaks json.loads otherwise (same fix ported for occam.py).
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
