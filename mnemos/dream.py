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
"""
import json
import os
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "curator"))
import consolidate as curator_consolidate

HERMES_ROOT = Path(__file__).resolve().parent.parent
DREAM_DIR = Path(__file__).resolve().parent / "dream"
LOCK_PATH = DREAM_DIR / ".dream.lock"
DREAM_LOG = DREAM_DIR / "dream_log.jsonl"
CONFIG_PATH = DREAM_DIR / "dream_config.json"
POINTER_PATH = DREAM_DIR / ".last_consolidated_line"

DEFAULT_CONFIG = {
    "interval_hours": 24,
    "stale_lock_minutes": 30,
    "min_reward_for_injection": 0.8,
}


def _ensure_dirs():
    DREAM_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))


def acquire_lock():
    """Returns True if lock acquired, False if another run is genuinely
    in-flight. Stale locks (older than stale_lock_minutes) are reclaimed —
    this is what prevents a crashed prior run from permanently wedging
    consolidation."""
    _ensure_dirs()
    config = json.loads(CONFIG_PATH.read_text())
    if LOCK_PATH.exists():
        lock_data = json.loads(LOCK_PATH.read_text())
        age_minutes = (time.time() - lock_data["acquired_at"]) / 60.0
        if age_minutes < config["stale_lock_minutes"]:
            return False  # genuinely locked, another run is active
        # stale — reclaim
    LOCK_PATH.write_text(json.dumps({"pid": os.getpid(), "acquired_at": time.time()}))
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


def run_consolidation():
    _ensure_dirs()
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
    print(json.dumps(run_consolidation(), indent=2))
