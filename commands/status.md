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
5. **Inactive modules:** from `HERMES.local.md` `INACTIVE_MODULES` line,
   each tagged with its phase.
6. **Log paths + last entry:** tail the last line of
   `logs/reasoning_seed.jsonl` and `logs/reflexion_seed.json` if they exist,
   show the most recent timestamp from each. If a log file doesn't exist
   yet, say so — don't imply activity that hasn't happened.
7. **Mnemos:** row count in `mnemos/vault/mnemos.db` (`SELECT COUNT(*) FROM
   messages`) — proves whether it's actually storing anything, not just
   whether the file exists.

Report what's actually true right now, including failures. A `/status` that
always reports green regardless of real state is worse than no status
command at all.
