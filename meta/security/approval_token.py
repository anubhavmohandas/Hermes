#!/usr/bin/env python3
"""
approval_token.py — D1 resolution: interactive approval for approval-tier
Bash commands (docs/DECISIONS.md Option B, built 2026-07-03).

The problem (D1): PreToolUse hooks are synchronous — stdin in, exit code
out. A hook cannot pause and ask a human, so `approval`-tier commands
(sudo, force-push, DROP TABLE…) were hard-blocked with no path to "yes".

The shape (Option B, from DECISIONS.md): move the ask UPSTREAM. Apollo asks
the human via AskUserQuestion BEFORE invoking Bash. On an explicit yes,
Apollo calls `grant <command>` here, which writes a short-lived token file.
When the Bash call then hits the hook, gate.py's approval branch calls
`check_and_consume <command>`; a valid token allows THAT command, once.

Token properties — each one is load-bearing:
  - Bound to the exact command string (md5) — approving `sudo ls` does not
    approve `sudo rm`.
  - Single-use — consumed (deleted) on first check, so a second identical
    command needs a fresh human yes.
  - Short-lived — TTL_SECONDS default 300; a stale yes is not a yes.
  - On-disk under logs/.approved/ (gitignored) — survives the process
    boundary between Apollo's grant and the hook's check, which run in
    different processes by design.

The human-gate invariant is intact: nothing here decides. It only carries
an explicit human "yes" across a process boundary, once, briefly.

CLI:
    python3 approval_token.py grant "<command>"      # Apollo, after human yes
    python3 approval_token.py check "<command>"      # gate.py (consumes)
    python3 approval_token.py list                   # audit: live tokens
"""
import hashlib
import json
import sys
import time
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(HERMES_ROOT))
from meta.paths import state_dir  # noqa: E402

# Approval tokens are short-lived (TTL below) but must live where the rest of
# the runtime state does — a token directory inside the plugin install would
# vanish mid-approval on an update. See meta/paths.py.
TOKEN_DIR = state_dir("logs", ".approved")
TTL_SECONDS = 300


def _token_path(command: str) -> Path:
    # non-security digest — filename derived from the command string, not an
    # integrity check (usedforsecurity=False; audit L4)
    digest = hashlib.md5(command.encode(), usedforsecurity=False).hexdigest()
    return TOKEN_DIR / f"{digest}.json"


def grant(command: str) -> dict:
    """Write a single-use token for exactly this command. Caller (Apollo)
    must have an explicit human yes in hand — this function trusts its
    caller because the alternative (this function asking) is impossible at
    hook depth, which is the whole reason D1 exists."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    path = _token_path(command)
    path.write_text(json.dumps({
        "command": command,
        "granted_at": time.time(),
        "ttl_seconds": TTL_SECONDS,
    }))
    return {"granted": True, "expires_in_seconds": TTL_SECONDS,
            "token": path.name}


def check_and_consume(command: str) -> tuple:
    """Returns (approved: bool, reason: str). Consumes the token if valid —
    and ALSO consumes it if expired (either way it's spent)."""
    path = _token_path(command)
    if not path.exists():
        return False, "no approval token for this command"
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        path.unlink(missing_ok=True)
        return False, "approval token unreadable — consumed, not honored"
    path.unlink(missing_ok=True)  # single-use, spent on inspection
    age = time.time() - data.get("granted_at", 0)
    ttl = data.get("ttl_seconds", TTL_SECONDS)
    if age > ttl:
        return False, f"approval token expired ({int(age)}s old, ttl {ttl}s)"
    if data.get("command") != command:
        return False, "approval token command mismatch"
    return True, f"human-approved via token ({int(age)}s ago, single-use, consumed)"


def list_tokens() -> list:
    if not TOKEN_DIR.exists():
        return []
    out = []
    for p in sorted(TOKEN_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text())
            age = int(time.time() - data.get("granted_at", 0))
            out.append({"token": p.name, "command": data.get("command", "?"),
                        "age_seconds": age,
                        "expired": age > data.get("ttl_seconds", TTL_SECONDS)})
        except (json.JSONDecodeError, OSError):
            out.append({"token": p.name, "command": "?", "unreadable": True})
    return out


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "grant":
        print(json.dumps(grant(sys.argv[2]), indent=2))
    elif len(sys.argv) >= 3 and sys.argv[1] == "check":
        ok, reason = check_and_consume(sys.argv[2])
        print(json.dumps({"approved": ok, "reason": reason}, indent=2))
        sys.exit(0 if ok else 1)
    elif len(sys.argv) >= 2 and sys.argv[1] == "list":
        print(json.dumps(list_tokens(), indent=2))
    else:
        print("usage: approval_token.py grant|check \"<command>\" | list", file=sys.stderr)
        sys.exit(2)
