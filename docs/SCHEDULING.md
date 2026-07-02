# HERMES — Scheduling Dream until real Cron lands (Phase 3C)

Dream (`mnemos/dream.py`) is lock-protected and consolidate-only — it never
approves or applies proposals, so scheduling it unattended violates no
human-gate constraint. What's missing pre-3C is only the *trigger*. This is
the launchd bridge (gap analysis 2026-07-02, B3).

## Install (macOS launchd)

From the repo root:

```bash
# 1. Render the template with this machine's absolute path
sed "s|__HERMES_ROOT__|$(pwd)|g" hooks/com.hermes.dream.plist.template \
    > ~/Library/LaunchAgents/com.hermes.dream.plist

# 2. Load it (runs daily at 03:30)
launchctl load ~/Library/LaunchAgents/com.hermes.dream.plist

# 3. Verify
launchctl list | grep com.hermes.dream
```

Output lands in `logs/dream_launchd.log` (gitignored). Dream's own
`.dream.lock` + `interval_hours` config (`mnemos/dream/dream_config.json`)
still apply — if something else already consolidated within the interval,
the scheduled run exits as a no-op rather than double-running.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.hermes.dream.plist
rm ~/Library/LaunchAgents/com.hermes.dream.plist
```

## What this is NOT

Not Phase 3C Cron. No retry policy, no job persistence across machines, no
Apollo-visible job state, and nothing here schedules anything other than
Dream. When 3C's durable scheduler lands, delete the LaunchAgent and let
Cron own the trigger.
