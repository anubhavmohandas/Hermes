# HERMES — Scheduling

Two eras, one file. Phase 3C Cron is now built (`cron/scheduler.py`), so the
durable scheduler owns all unattended work. The old Dream-only launchd bridge
is kept below for uninstall reference.

## Current: the Cron loop (Phase 3C)

`cron/scheduler.py` is the durable scheduler: jobs live in `cron/cron.db`
(SQLite, machine-local, gitignored), every tick is `.tick.lock`-protected,
every job has a hard interrupt (default 180s), and every completed run is
written into Mnemos so the result is retrievable next session. Commands are
classified by `meta/security/approval.py` at add-time AND run-time —
approval-tier commands (sudo, force-push, DROP TABLE…) are refused outright:
unattended means nobody is there to approve.

### Add jobs

```bash
python3 cron/scheduler.py add dream "python3 mnemos/dream.py" --daily 03:30
python3 cron/scheduler.py add nightly-note "python3 brain.py log --task-type heartbeat --tier 1" --interval 86400
python3 cron/scheduler.py list      # inspect
python3 cron/scheduler.py tick      # run due jobs once, by hand
```

### Install the loop (macOS launchd — the production host)

From the repo root:

```bash
# 1. Render the template with this machine's absolute path
sed "s|__HERMES_ROOT__|$(pwd)|g" hooks/com.hermes.cron.plist.template \
    > ~/Library/LaunchAgents/com.hermes.cron.plist

# 2. Load it (polls every 60s, restarts if it dies)
launchctl load ~/Library/LaunchAgents/com.hermes.cron.plist

# 3. Verify
launchctl list | grep com.hermes.cron
```

Loop output lands in `logs/cron_launchd.log` (gitignored). Overlapping loop
instances are harmless — `.tick.lock` guarantees one tick wins (proven under
forced concurrency 2026-07-03; the race fix is documented in
`acquire_tick_lock`).

**Invariant #7:** Cowork cannot host this loop — sessions are bound to a
human being present. launchd/CLI only.

### Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.hermes.cron.plist
rm ~/Library/LaunchAgents/com.hermes.cron.plist
```

---

## Legacy: the Dream-only bridge (Phase 3B → 3C, superseded)

Before Cron existed, launchd ran `mnemos/dream.py` directly via
`hooks/com.hermes.dream.plist.template` (daily 03:30). If that agent is still
loaded, migrate:

```bash
launchctl unload ~/Library/LaunchAgents/com.hermes.dream.plist 2>/dev/null
rm -f ~/Library/LaunchAgents/com.hermes.dream.plist
python3 cron/scheduler.py add dream "python3 mnemos/dream.py" --daily 03:30
```

Dream's own `.dream.lock` + `interval_hours` config
(`mnemos/dream/dream_config.json`) still apply on top of Cron's scheduling —
if something already consolidated within the interval, the run exits as a
no-op rather than double-running.

---

## Agenda — auto-resume across usage-limit resets

`delegation/agenda.py` is the "my 5-hour window ran out, keep going without
me typing continue" mechanism. Setup, once:

```bash
# 1. Create the agenda (the human decision point — Bash only if YOU grant it)
python3 delegation/agenda.py add "Research X, write findings to findings.md" \
    [--allow-bash] [--child-timeout 1800]

# 2. Wire the tick into cron (every 15 min by default)
python3 delegation/agenda.py install-cron

# 3. Make sure cron itself is hosted (launchd — same plist as everything else)
#    hooks/com.hermes.cron.plist.template → ~/Library/LaunchAgents/
```

How the reset is survived, mechanically: each tick runs ONE attempt for the
most-starved active agenda as a fresh `claude -p` child. While the usage
window is exhausted, the attempt fails in seconds with a rate-limit marker —
`dispatch.classify_output` labels it `rate_limited`, which does NOT count
toward the stall limit, and the agenda simply stays active. The first tick
after the window resets does real work again and appends a progress note.
Repeat until the child prints `AGENDA_STATUS: DONE …`, at which point the
result lands in Mnemos.

Honest limits (also in the module docstring): this resumes from *notes*, not
from the dead session's context; "immediately after reset" means "within one
tick interval"; genuine failures (not rate limits) stall the agenda after
`--max-failures` consecutive ones and wait for a human `retry` — never an
infinite retry spiral (RecoveryLedger pattern). Cowork cannot host any of
this (Invariant #7).
