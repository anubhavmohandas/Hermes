---
name: status
description: /status — live state, not a static description. Environment, hooks, brain.py reachability, active/inactive modules, log paths, last logged request.
---

# /status

When the user types `/status`, Apollo runs live checks — this is not a
cached or static answer:

1. **Environment:** CLI or Cowork (from the session-start detection in
   `SKILL.md` §1).
2. **Hooks:** is `hooks/verify.sh` present and executable? (`test -x
   hooks/verify.sh`)
3. **brain.py:** run `python3 brain.py check --task "status check"` — did it
   return valid JSON?
4. **Active modules:** from `HERMES.local.md` `ACTIVE_MODULES` line.
5. **Opt-in modules:** from `HERMES.local.md` `OPT_IN_MODULES` line — note
   each is on-demand with a fallback, so "present" ≠ "online path enabled".
6. **Out of scope:** from `INACTIVE_MODULES` (NYX / Stage 6). Say it isn't
   built yet; don't tag it as merely a later phase of this goal.
7. **Autonomy hosts (Stage 3), checked live, not assumed:**
   - Cron: `python3 cron/scheduler.py status` — job count + whether the
     launchd agent is loaded (`launchctl list | grep com.hermes.cron`).
   - Delegation: is the `claude` CLI on PATH? (`python3
     delegation/dispatch.py status` reports `claude_cli`.)
   - Fetcher: `python3 fetcher/fetch.py status` — SAFE_MODE + which search
     backends have keys.
8. **Log paths + last entry:** tail the last line of
   `logs/reasoning_seed.jsonl` and `logs/reflexion_seed.json` if they exist,
   show the most recent timestamp from each. If a log file doesn't exist
   yet, say so — don't imply activity that hasn't happened.
9. **Mnemos:** row count in `mnemos/vault/mnemos.db` (`SELECT COUNT(*) FROM
   messages`) — proves whether it's actually storing anything, not just
   whether the file exists.
10. **Security audit:** `python3 meta/security/audit.py` — is the 7-layer
    audit green right now? (11 checks; a red one names the regressed layer.)

Report what's actually true right now, including failures. A `/status` that
always reports green regardless of real state is worse than no status
command at all.
