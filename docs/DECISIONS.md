# HERMES — Deferred architecture decisions

Things flagged during builds/audits that need a real decision, not a quick
patch. Each entry: what was found, what the options are, what's live today.

---

## D1 — Interactive human approval for `approval`-tier Bash commands

**Found:** 2026-07-02 code audit (M1). `approval.py` classifies commands
like `sudo`, `git push --force`, `DROP TABLE` as `approval` (distinct from
`block`) — the intent, per the original design note, was "not auto-denied,
but not auto-allowed either." In practice, `gate.py` returns `deny` for
`approval` exactly like it does for `block`, and `verify.sh` maps any deny
to a hard `exit 1`. There is no third state at the hook layer. The comment
claiming otherwise was misleading and has been corrected (see
`meta/security/gate.py`).

**Why it's hard-blocked today, and why that's the correct default:**
`PreToolUse` hooks are synchronous, non-interactive gates — stdin in, exit
code out. There is no mechanism for a hook to pause mid-call, surface a
prompt to a human, and wait for a response. Given that constraint,
fail-closed (deny anything not explicitly safe) is the only sound default.
Silently "allowing" approval-tier commands would defeat the point of
flagging them at all.

**Option A — accept the hard block as final, permanently.** Simplest. Cost:
`sudo`, force-push, etc. become unusable through HERMES at all, even when
the human genuinely wants to run them. Over time this pushes real work
outside HERMES entirely, which defeats "one skill that combines
everything."

**Option B — move the ask upstream, into Apollo.** Before Apollo ever
invokes the Bash tool for a command that `approval.classify_command()`
would flag, it calls `AskUserQuestion` directly and gets an explicit yes/no
from the human. If yes, Apollo writes a short-lived approval token (e.g.
`hermes/logs/.approved/<md5-of-command>-<timestamp>`, expiring after a few
minutes) before calling Bash. `gate.py`'s approval branch checks for a
matching, unexpired token before falling back to deny. This keeps the hook
fail-closed by default while giving a real, audited path for the human to
say yes to a specific command, once.

**Status: not implemented.** Option B is the direction, but it adds a new
token-handshake surface between Apollo (prompt-level) and the hook
(platform-level) that deserves its own build-and-test pass, not a
same-session patch bolted onto an audit fix. Until built, Option A's
behavior (hard block, correctly labeled now) is what's live.

---

*Add new entries above this line as they come up. Don't resolve a D-item by
editing this file alone — the code has to change too, and the entry should
note the commit/date it was closed.*
