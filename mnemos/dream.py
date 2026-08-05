#!/usr/bin/env python3
"""
mnemos/dream.py — Dream consolidation (Phase 3B).

Pattern source (reimplemented fresh, no code copied): claude-code-main
autoDream + letta sleeptime AgentLoop V4 — background memory consolidation
without blocking inference. Four components per the blueprint: consolidator
(this file), .dream.lock (prevents dual-run corruption), prompt (extension
point for an LLM-driven synthesis pass), config.

In Phase 3B, without Cron (Phase 3C) actually scheduling anything yet, this
runs on demand — invoke it manually, or wire it to a Cowork scheduled task
as a bridge until real Cron lands. What it does NOT do yet: LLM-driven
synthesis/summarization of the day's findings (dream_prompt.md is the
extension point for that — an actual model call, which this deterministic
script can't make on its own).

Timing gate (pattern #1426, claude-code-main autoDream): once Cron fires
this daily, an unconditional run would re-consolidate identical data every
night. autoDream's answer is an ordered, cheapest-first gate that must pass
BEFORE the expensive work: enough time elapsed (min_hours) AND enough new
activity accumulated (min_new_entries — our stand-in for autoDream's
min_sessions, since a consolidation over zero new failures is pure waste).
`should_run()` is that gate; `--force` (manual invocation) bypasses it, a
scheduled tick never does.
"""
import calendar
import json
import os
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "curator"))
import consolidate as curator_consolidate

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT))
from meta.paths import state_dir, state_file  # noqa: E402

# Runtime state under ~/.claude/hermes/ (meta/paths.py). The lock lives with
# the rest of the dream state on purpose — a lock left in the old location
# after a plugin update would guard nothing.
DREAM_DIR = state_dir("mnemos", "dream")
LOCK_PATH = DREAM_DIR / ".dream.lock"
DREAM_LOG = DREAM_DIR / "dream_log.jsonl"
CONFIG_PATH = DREAM_DIR / "dream_config.json"
POINTER_PATH = DREAM_DIR / ".last_consolidated_line"
RAW_REFLEXION_LOG = state_file("logs", "reflexion_seed.json")

DEFAULT_CONFIG = {
    "interval_hours": 24,
    "stale_lock_minutes": 30,
    "min_reward_for_injection": 0.8,
    "min_new_entries": 1,     # #1426: don't consolidate if nothing new accrued
}


def _ensure_dirs():
    DREAM_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))


def acquire_lock():
    """Returns True if lock acquired, False if another run is genuinely
    in-flight. Stale locks (older than stale_lock_minutes) are reclaimed —
    this is what prevents a crashed prior run from permanently wedging
    consolidation.

    Hardened 2026-07-05 (audit M2) to the same shape as cron's
    acquire_tick_lock(): O_CREAT|O_EXCL is the atomicity primitive (two racing
    consolidations cannot both create the file), and staleness is judged by the
    lock file's MTIME, never by parsing its JSON body. The old version did
    exists()+write_text (non-atomic — both runners could pass the check and
    double-run) and json.loads(LOCK_PATH.read_text()) (which CRASHED on an
    empty/half-written lock file, reproduced live in the audit). The JSON body
    is observability only (whose pid holds it)."""
    _ensure_dirs()
    config = {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text())}
    if LOCK_PATH.exists():
        try:
            age_minutes = (time.time() - LOCK_PATH.stat().st_mtime) / 60.0
        except OSError:
            return False  # vanished/unreadable mid-check — treat as active
        if age_minutes < config["stale_lock_minutes"]:
            return False  # genuinely locked, another run is active
        try:
            LOCK_PATH.unlink()  # stale — two reclaimers race here; unlink wins once
        except OSError:
            return False
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False  # lost the create race to another consolidation
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"pid": os.getpid(), "acquired_at": time.time()}))
    return True


def release_lock():
    if not LOCK_PATH.exists():
        return
    try:
        LOCK_PATH.unlink()
    except OSError as e:
        # Some filesystems (FUSE mounts, certain network drives) block unlink
        # even though the file was writable. Don't let cleanup failure mask
        # a successful consolidation run as a crash — the staleness check in
        # acquire_lock() already recovers from a lock that never got cleared.
        import sys as _sys
        print(f"dream: could not release lock ({e}) — relying on staleness timeout ({DEFAULT_CONFIG['stale_lock_minutes']}min) to recover", file=_sys.stderr)


def _last_run():
    """(epoch_seconds, raw_entries_read) of the last completed run, or
    (None, 0) if never run. Reads the tail of dream_log.jsonl — the same
    authoritative record run_consolidation() appends to."""
    if not DREAM_LOG.exists():
        return None, 0
    last = None
    for line in DREAM_LOG.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                last = json.loads(line)
            except json.JSONDecodeError:
                continue
    if not last:
        return None, 0
    ts = last.get("timestamp")
    epoch = None
    if ts:
        try:
            # timegm treats the parsed struct_time as UTC (the 'Z' says it is).
            # time.mktime would treat it as LOCAL time and skew every interval
            # gate by the machine's UTC offset (audit L1, e.g. -5.5h on IST).
            epoch = calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
        except (ValueError, OverflowError):
            epoch = None
    prev_entries = (last.get("curator_consolidation") or {}).get("raw_entries_read", 0)
    return epoch, prev_entries


def _raw_entry_count():
    if not RAW_REFLEXION_LOG.exists():
        return 0
    return sum(1 for ln in RAW_REFLEXION_LOG.read_text().splitlines() if ln.strip())


def should_run():
    """#1426 cheapest-first gate. Returns (ok: bool, reason: str). Ordered so
    the cheapest check fails fast. Only consulted by scheduled runs; --force
    skips it entirely."""
    _ensure_dirs()
    config = {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text())}
    last_epoch, prev_entries = _last_run()
    # Gate 1 (cheapest): never run before → always allowed.
    if last_epoch is None:
        return True, "first run — no prior consolidation on record"
    # Gate 2: enough wall-clock time elapsed?
    hours_since = (time.time() - last_epoch) / 3600.0
    if hours_since < config["interval_hours"]:
        return False, (f"only {hours_since:.1f}h since last consolidation "
                       f"(interval_hours={config['interval_hours']}) — skipping")
    # Gate 3: enough NEW activity to be worth a pass?
    new_entries = _raw_entry_count() - prev_entries
    if new_entries < config["min_new_entries"]:
        return False, (f"{new_entries} new reflexion entries since last run "
                       f"(min_new_entries={config['min_new_entries']}) — nothing to consolidate")
    return True, f"{hours_since:.1f}h elapsed, {new_entries} new entries — consolidating"


def run_consolidation(force: bool = False):
    _ensure_dirs()
    if not force:
        ok, reason = should_run()
        if not ok:
            return {"status": "skipped", "reason": reason, "gate": "timing"}
    if not acquire_lock():
        return {"status": "skipped", "reason": "another consolidation run is already in flight"}

    try:
        curator_result = curator_consolidate.run()

        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "curator_consolidation": curator_result,
        }
        with open(DREAM_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return {"status": "completed", **entry}
    finally:
        release_lock()


if __name__ == "__main__":
    force = "--force" in sys.argv
    print(json.dumps(run_consolidation(force=force), indent=2))
