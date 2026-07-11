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

From the repo root, in the shell/venv you actually want the loop to run
under (so `$(which python3)` resolves to the interpreter with your real
deps installed):

```bash
# 1. Render the template with this machine's absolute path AND an EXPLICIT
#    python3 path (not /usr/bin/env — see hooks/com.hermes.cron.plist.template
#    for why: env's lookup inside launchd can silently resolve to a
#    different binary than the one you use interactively, and TCC grants
#    are tied to the exact binary, not "python3" the name).
sed -e "s|__HERMES_ROOT__|$(pwd)|g" -e "s|__PYTHON_BIN__|$(which python3)|g" \
    -e "s|__PATH__|$PATH|g" \
    hooks/com.hermes.cron.plist.template > ~/Library/LaunchAgents/com.hermes.cron.plist

# 2. Load it (polls every 60s, restarts if it dies)
launchctl load ~/Library/LaunchAgents/com.hermes.cron.plist

# 3. Verify
launchctl list | grep com.hermes.cron
```

If you already installed an OLDER template (missing `__PYTHON_BIN__` and/or
`__PATH__`), re-render it with the command above after `launchctl unload` —
this replaces ambiguous `env`/inherited-PATH lookups with the exact values
you resolved just now, so the Full Disk Access troubleshooting step below
only ever needs one, correct binary added.

Loop output lands in `logs/cron_launchd.log` (gitignored). Overlapping loop
instances are harmless — `.tick.lock` guarantees one tick wins (proven under
forced concurrency 2026-07-03; the race fix is documented in
`acquire_tick_lock`).

### Troubleshooting: `logs/cron_launchd.log` repeats "Operation not permitted"

Seen live 2026-07-10: `launchctl load` succeeds and `launchctl list` shows
the job running, but the log fills with `can't open file
'.../cron/scheduler.py': [Errno 1] Operation not permitted`, repeating every
poll. This is macOS TCC (Transparency, Consent & Control), not a HERMES bug:
the repo lives under `~/Documents`, a TCC-protected folder, and a **headless
launchd agent gets no permission prompt** the way a normal double-clicked
app would — it just fails silently with EPERM forever.

**Root cause of the confusing version of this bug:** the plist used to
invoke `/usr/bin/env python3`. `env`'s lookup runs inside launchd's own
minimal PATH — NOT your shell's — so it can silently resolve to a
*different* python3 than the one you use interactively (e.g. venv-activated
Terminal python3 vs. `/Library/Developer/CommandLineTools/usr/bin/python3`
that only `env` inside launchd ever sees). Granting Full Disk Access to
"python3.9" found via Spotlight/the FDA browse dialog can add the WRONG
binary — TCC grants are tied to the exact executable, not the name — and
the log keeps repeating EPERM with no further clue which one is missing.

**Fix, in order:**

1. Re-render the plist with an explicit, pinned python3 path instead of
   `env` (current template already does this — regenerate if you installed
   an older copy):
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.hermes.cron.plist
   sed -e "s|__HERMES_ROOT__|$(pwd)|g" -e "s|__PYTHON_BIN__|$(which python3)|g" \
       hooks/com.hermes.cron.plist.template > ~/Library/LaunchAgents/com.hermes.cron.plist
   launchctl load ~/Library/LaunchAgents/com.hermes.cron.plist
   ```
2. Grant Full Disk Access to that SAME exact path (`echo $(which python3)`
   to see it printed literally — copy it from there, don't retype it):
   ```
   System Settings → Privacy & Security → Full Disk Access → "+"
   → Cmd+Shift+G → paste the exact path → Add → toggle ON
   ```
   If Full Disk Access already has a DIFFERENT python3 entry toggled on
   (e.g. a Homebrew or framework build found separately), that entry isn't
   wrong to keep, it's just not the one this job needs — add the one from
   step 1, don't rely on renaming/reusing the existing entry.
3. Reload once more so the agent picks up both changes, then watch the log:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.hermes.cron.plist
   launchctl load ~/Library/LaunchAgents/com.hermes.cron.plist
   tail -f logs/cron_launchd.log   # should go quiet / show clean tick lines, no more EPERM
   ```

**Invariant #7:** Cowork cannot host this loop — sessions are bound to a
human being present. launchd/CLI only.

### Troubleshooting: cron shows `runs_completed` climbing but agendas never get an attempt

Seen live 2026-07-11: `launchctl list` shows the loop running,
`cron/scheduler.py list` shows `agenda-tick` with `last_status: "completed"`
and a growing `runs_completed`, but `agenda.py show <id>` stays at
`attempts: 0, last_attempt_at: null` forever, even hours after the agenda
was created. This is NOT the FUSE bug (D8) and NOT a crash — the loop
really is ticking, on schedule, successfully.

**Root cause:** `delegation/agenda.py`'s `tick()` calls
`dispatch.claude_cli_available()` (= `shutil.which("claude")`) before doing
anything else, and `dispatch.build_child_command()` spawns children via the
literal `argv[0] = "claude"` — both PATH lookups. launchd's own minimal
environment doesn't have your interactive shell's PATH, so if `claude`
lives somewhere PATH-dependent (nvm, npm global, homebrew, etc.) the check
returns `False` on every tick, `tick()` returns early *before* touching the
agenda, and — because nothing calls `sys.exit(1)` on that path — the
process still exits 0. The scheduler has no way to tell "did nothing, PATH
problem" apart from "did nothing, no active agenda," so it logs "completed"
either way, silently, forever.

**Fix:** the current plist template pins `EnvironmentVariables/PATH` via
`__PATH__` (see step 1 above) — if you installed the plist before this was
added, re-render and reload it the same way as the python3 fix:
```bash
launchctl unload ~/Library/LaunchAgents/com.hermes.cron.plist
sed -e "s|__HERMES_ROOT__|$(pwd)|g" -e "s|__PYTHON_BIN__|$(which python3)|g" \
    -e "s|__PATH__|$PATH|g" \
    hooks/com.hermes.cron.plist.template > ~/Library/LaunchAgents/com.hermes.cron.plist
launchctl load ~/Library/LaunchAgents/com.hermes.cron.plist
```
Confirm the fix by checking `agenda.py show <id>` after the next tick —
`attempts` should increment and `last_attempt_at` should stop being `null`.

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
