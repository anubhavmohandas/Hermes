#!/usr/bin/env python3
"""
cron/scheduler.py — Cron (Phase 3C keystone): durable, unattended scheduling.

Pattern sources (reimplemented fresh, no code copied): claude-code-main
background task queue + letta sleeptime scheduler loop + claude-task-master
durable job rows. Per HERMES_GOAL_Start_to_End.md Stage 3: durable SQLite
scheduler, `.tick.lock`, 3-minute hard interrupt. Without this, Dream/Curator
consolidation only ever runs when a human manually triggers it.

Design decisions, stated plainly:
  - Jobs are rows in cron/cron.db (SQLite, WAL like mnemos). A job survives
    process death, reboot, and git operations (db is gitignored — schedules
    are machine-local state, same policy as the vault).
  - One tick = "run every job whose next_run is due, once." The loop is just
    tick-forever; launchd (hooks/com.hermes.cron.plist.template) is the
    production host on macOS. Cowork CANNOT host this — Invariant #7 —
    sessions are bound to a human being present.
  - 3-minute hard interrupt (per-job override exists for tests): a job that
    exceeds its timeout is killed and recorded as 'interrupted', never left
    running. An unattended scheduler that can hang is worse than none.
  - Unattended = nobody to ask. Every command is classified by
    meta/security/approval.py at BOTH add-time and run-time; 'approval' and
    'block' verdicts refuse to run. There is deliberately no override flag:
    if a command needs a human, it does not belong in cron.
  - Every completed run writes a result summary into Mnemos (both stores,
    secret-scrubbed) so the result is retrievable next session/morning via
    hybrid_search — that IS the Stage 3 exit gate. Mnemos being unavailable
    degrades to cron.db-only recording with a stderr warning (Invariant #5).

CLI:
    python3 cron/scheduler.py add <name> "<command>" --interval 3600
    python3 cron/scheduler.py add <name> "<command>" --daily 03:30
    python3 cron/scheduler.py add <name> "<command>" --once [--timeout 180]
    python3 cron/scheduler.py list | remove <name> | enable <name> | disable <name>
    python3 cron/scheduler.py tick          # run due jobs once, then exit
    python3 cron/scheduler.py loop [--poll 60]   # tick forever (launchd/CLI only)
    python3 cron/scheduler.py status
"""
import argparse
import json
import os
import re
import shlex
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
CRON_DIR = Path(__file__).resolve().parent
DB_PATH = CRON_DIR / "cron.db"
LOCK_PATH = CRON_DIR / ".tick.lock"

sys.path.insert(0, str(HERMES_ROOT / "meta" / "security"))
import approval  # noqa: E402
import redact    # noqa: E402

DEFAULT_TIMEOUT_SECONDS = 180   # the blueprint's 3-minute hard interrupt
STALE_LOCK_MINUTES = 10         # a tick should take seconds; 10min = crashed

# --- Unattended allowlist (audit M3) --------------------------------------
# approval.classify_command is a DENYLIST — it blocks known-dangerous shapes
# but can't enumerate every destructive command (a python one-liner that
# shutil.rmtree's a tree scans "safe"). An unattended job runs with nobody to
# ask, so on top of the denylist we require a POSITIVE allowlist AND we run the
# command with shell=False (no substitution/redirection/globbing/chaining can
# fire). A cron job must therefore be a single invocation of either:
#   - a HERMES-internal python entrypoint (python3 <script-under-HERMES_ROOT>),
#     with inline code (-c / -m) refused, or
#   - one trivially-safe binary from ALLOWED_BINARIES.
# There is deliberately no override — same stance as the rest of cron.
ALLOWED_INTERPRETERS = {"python", "python3"}
ALLOWED_BINARIES = {"echo", "true", "false", "sleep", "date"}
# Shell metacharacters that only mean something under a shell. Their presence
# signals intent the shell=False runner will NOT honor, so refuse rather than
# run with surprising (and possibly unsafe) semantics.
_SHELL_META_RE = re.compile(r"[;|&<>`$()]")


def classify_unattended(command: str):
    """Positive allowlist for cron/agenda execution, layered on top of the
    denylist. Returns (ok: bool, reason: str)."""
    verdict, reason = approval.classify_command(command)
    if verdict != "safe":
        return False, f"{verdict}: {reason}"
    if not command or not command.strip():
        return False, "empty command"
    if _SHELL_META_RE.search(command):
        return False, ("shell metacharacter in command — unattended jobs run a single "
                       "command with shell=False (no pipes/redirects/substitution). "
                       "Wrap any pipeline in a HERMES script and schedule that.")
    try:
        toks = shlex.split(command)
    except ValueError as e:
        return False, f"unparseable command ({e})"
    if not toks:
        return False, "empty command"
    head = os.path.basename(toks[0])
    if head in ALLOWED_INTERPRETERS:
        script = None
        for t in toks[1:]:
            if t in ("-c", "-m"):
                return False, (f"inline execution ('{head} {t} …') is not allowed in "
                               f"unattended jobs — put the logic in a script under HERMES_ROOT")
            if t.startswith("-"):
                continue
            script = t
            break
        if script is None:
            return False, f"'{head}' invoked with no script argument"
        p = Path(script)
        resolved = p.resolve() if p.is_absolute() else (HERMES_ROOT / p).resolve()
        try:
            resolved.relative_to(HERMES_ROOT)
        except ValueError:
            return False, (f"script '{script}' resolves outside HERMES_ROOT — unattended "
                           f"jobs run only HERMES's own scripts")
        if not resolved.exists():
            return False, f"script '{script}' does not exist under HERMES_ROOT"
        return True, "allowlisted (hermes python entrypoint)"
    if head in ALLOWED_BINARIES:
        return True, "allowlisted (safe binary)"
    return False, (f"'{head}' is not on the unattended allowlist — allowed: "
                   f"{sorted(ALLOWED_INTERPRETERS)} running a script under HERMES_ROOT, "
                   f"or one of {sorted(ALLOWED_BINARIES)}")


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    CRON_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            command TEXT NOT NULL,
            schedule TEXT NOT NULL CHECK (schedule IN ('once','interval','daily')),
            interval_seconds INTEGER,
            daily_time TEXT,
            timeout_seconds INTEGER NOT NULL DEFAULT 180,
            next_run TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_run TEXT,
            last_status TEXT,
            last_output TEXT,
            runs_completed INTEGER NOT NULL DEFAULT 0
        );
    """)
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _next_daily(daily_time: str, after: datetime) -> datetime:
    hh, mm = daily_time.split(":")
    candidate = after.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    if candidate <= after:
        candidate += timedelta(days=1)
    return candidate


# ---------------------------------------------------------------------------
# lock — same shape as mnemos/dream.py: file lock + staleness reclaim
# ---------------------------------------------------------------------------

def acquire_tick_lock() -> bool:
    """True if this process may tick. O_EXCL creation is the atomicity
    primitive (two racing ticks cannot both create the file); the staleness
    check recovers from a tick that crashed without releasing.

    Staleness is judged by the lock file's mtime, NEVER by parsing its JSON
    body: mtime exists atomically from the instant O_EXCL creates the file,
    but the body is written a moment later. The first cut of this function
    parsed the body and treated 'unreadable' as 'stale' — a second tick
    racing into that create-vs-write window read an empty file, "reclaimed"
    the brand-new lock, and both ticks ran the same job (caught live by the
    forced-concurrency proof, 2026-07-03). The JSON body is observability
    only (whose pid holds it)."""
    if LOCK_PATH.exists():
        try:
            age_min = (time.time() - LOCK_PATH.stat().st_mtime) / 60.0
        except OSError:
            return False  # vanished/unreadable mid-check — someone is active
        if age_min < STALE_LOCK_MINUTES:
            return False
        try:
            LOCK_PATH.unlink()  # two reclaimers race here; unlink wins once
        except OSError:
            return False
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False  # lost the race to another tick
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"pid": os.getpid(), "acquired_at": time.time()}))
    return True


def release_tick_lock():
    try:
        LOCK_PATH.unlink()
    except OSError:
        pass  # staleness timeout recovers; see dream.py for the rationale


# ---------------------------------------------------------------------------
# Mnemos write-back — the part that makes results retrievable next morning
# ---------------------------------------------------------------------------

def _record_to_mnemos(job_name: str, status: str, output_snippet: str):
    """Write the run result into both Mnemos stores. Failure here must not
    fail the job — the run already happened; cron.db has the authoritative
    record. Degrade with a warning (Invariant #5)."""
    summary = f"cron job '{job_name}' {status}: {output_snippet}".strip()
    summary = redact.redact(summary)
    try:
        sys.path.insert(0, str(HERMES_ROOT / "mnemos"))
        import store  # deferred: vault may be refused (canary) — that's non-fatal here
        store.write_message(f"cron:{job_name}", "assistant", summary, memory_type="project")
    except Exception as e:
        print(f"cron: Mnemos store write failed ({e}) — result kept in cron.db only",
              file=sys.stderr)
        return False
    try:
        import hnsw_index
        if getattr(hnsw_index, "HNSW_AVAILABLE", False):
            idx = hnsw_index.MnemosHNSW(HERMES_ROOT / "mnemos" / "vault" / "hnsw")
            idx.insert(summary)
            idx.save()
    except Exception as e:
        print(f"cron: Tier C insert failed ({e}) — Tier A/B still have the result",
              file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# job operations
# ---------------------------------------------------------------------------

def add_job(name: str, command: str, schedule: str, interval_seconds: int = None,
            daily_time: str = None, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
    ok, reason = classify_unattended(command)
    if not ok:
        return {"added": False, "name": name,
                "reason": f"refused at add-time: {reason} — "
                          f"unattended jobs must be allowlisted (see classify_unattended)"}
    now = _now()
    if schedule == "interval":
        next_run = now + timedelta(seconds=interval_seconds)
    elif schedule == "daily":
        next_run = _next_daily(daily_time, now)
    else:
        next_run = now  # 'once' = due immediately
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO jobs (name, command, schedule, interval_seconds, daily_time,"
            " timeout_seconds, next_run, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (name, command, schedule, interval_seconds, daily_time,
             timeout_seconds, _iso(next_run), _iso(now)))
        conn.commit()
    except sqlite3.IntegrityError:
        return {"added": False, "name": name, "reason": f"job '{name}' already exists"}
    finally:
        conn.close()
    return {"added": True, "name": name, "schedule": schedule, "next_run": _iso(next_run),
            "timeout_seconds": timeout_seconds}


def list_jobs():
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT name, command, schedule, interval_seconds, daily_time, timeout_seconds,"
            " next_run, enabled, last_run, last_status, runs_completed FROM jobs"
            " ORDER BY next_run").fetchall()
    finally:
        conn.close()
    keys = ["name", "command", "schedule", "interval_seconds", "daily_time",
            "timeout_seconds", "next_run", "enabled", "last_run", "last_status",
            "runs_completed"]
    return [dict(zip(keys, r)) for r in rows]


def remove_job(name: str):
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM jobs WHERE name = ?", (name,))
        conn.commit()
    finally:
        conn.close()
    return {"removed": cur.rowcount > 0, "name": name}


def set_enabled(name: str, enabled: bool):
    conn = _connect()
    try:
        cur = conn.execute("UPDATE jobs SET enabled = ? WHERE name = ?",
                           (1 if enabled else 0, name))
        conn.commit()
    finally:
        conn.close()
    return {"name": name, "enabled": enabled, "found": cur.rowcount > 0}


def _run_job(row: dict) -> dict:
    """Execute one due job with the hard interrupt. Returns the run record."""
    # Run-time re-classification: the command may have been edited in the db
    # by something other than add_job, and rules may have tightened since add.
    ok, reason = classify_unattended(row["command"])
    if not ok:
        return {"status": "refused", "output": reason}
    started = time.time()
    try:
        # shell=False (audit M3): the command is a single allowlisted argv, so
        # there is no shell to interpret substitution/redirection/globbing.
        proc = subprocess.run(
            shlex.split(row["command"]), shell=False, capture_output=True, text=True,
            timeout=row["timeout_seconds"], cwd=str(HERMES_ROOT))
        status = "completed" if proc.returncode == 0 else f"failed(rc={proc.returncode})"
        output = (proc.stdout or proc.stderr or "").strip()
    except subprocess.TimeoutExpired:
        status = "interrupted"
        output = (f"hard interrupt after {row['timeout_seconds']}s — job killed, "
                  f"not left running")
    except OSError as e:
        status = "failed(spawn)"
        output = str(e)
    elapsed_ms = int((time.time() - started) * 1000)
    snippet = redact.redact(output[:500])
    return {"status": status, "output": snippet, "elapsed_ms": elapsed_ms}


def tick():
    """Run every enabled job whose next_run is due. Lock-protected: two
    concurrent ticks cannot double-run a job."""
    if not acquire_tick_lock():
        return {"ticked": False, "reason": "another tick holds .tick.lock"}
    ran = []
    try:
        now = _now()
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT id, name, command, schedule, interval_seconds, daily_time,"
                " timeout_seconds FROM jobs WHERE enabled = 1 AND next_run <= ?",
                (_iso(now),)).fetchall()
            keys = ["id", "name", "command", "schedule", "interval_seconds",
                    "daily_time", "timeout_seconds"]
            due = [dict(zip(keys, r)) for r in rows]
        finally:
            conn.close()

        for job in due:
            result = _run_job(job)
            _record_to_mnemos(job["name"], result["status"], result["output"])
            conn = _connect()
            try:
                if job["schedule"] == "interval":
                    next_run = _iso(_now() + timedelta(seconds=job["interval_seconds"]))
                    conn.execute(
                        "UPDATE jobs SET last_run=?, last_status=?, last_output=?,"
                        " runs_completed=runs_completed+1, next_run=? WHERE id=?",
                        (_iso(now), result["status"], result["output"], next_run, job["id"]))
                elif job["schedule"] == "daily":
                    next_run = _iso(_next_daily(job["daily_time"], _now()))
                    conn.execute(
                        "UPDATE jobs SET last_run=?, last_status=?, last_output=?,"
                        " runs_completed=runs_completed+1, next_run=? WHERE id=?",
                        (_iso(now), result["status"], result["output"], next_run, job["id"]))
                else:  # once — ran, now disable rather than delete (audit trail)
                    conn.execute(
                        "UPDATE jobs SET last_run=?, last_status=?, last_output=?,"
                        " runs_completed=runs_completed+1, enabled=0 WHERE id=?",
                        (_iso(now), result["status"], result["output"], job["id"]))
                conn.commit()
            finally:
                conn.close()
            ran.append({"name": job["name"], **result})
    finally:
        release_tick_lock()
    return {"ticked": True, "due": len(ran), "ran": ran}


def loop(poll_seconds: int = 60):
    """Tick forever. This is what launchd/CLI hosts — NEVER Cowork
    (Invariant #7: Cowork sessions cannot host the overnight loop)."""
    print(f"cron: loop started, polling every {poll_seconds}s "
          f"(host this under launchd — see hooks/com.hermes.cron.plist.template)",
          file=sys.stderr)
    while True:
        result = tick()
        if result.get("due"):
            print(json.dumps(result), flush=True)
        time.sleep(poll_seconds)


def status():
    jobs = list_jobs()
    return {
        "db": str(DB_PATH),
        "db_exists": DB_PATH.exists(),
        "lock_held": LOCK_PATH.exists(),
        "jobs_total": len(jobs),
        "jobs_enabled": sum(1 for j in jobs if j["enabled"]),
        "default_timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "jobs": jobs,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="cron/scheduler.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("name")
    p_add.add_argument("cmd")
    group = p_add.add_mutually_exclusive_group(required=True)
    group.add_argument("--interval", type=int, help="run every N seconds")
    group.add_argument("--daily", help="run daily at HH:MM (UTC)")
    group.add_argument("--once", action="store_true", help="run at next tick, then disable")
    p_add.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS,
                       help=f"hard interrupt in seconds (default {DEFAULT_TIMEOUT_SECONDS})")

    for name in ("remove", "enable", "disable"):
        p = sub.add_parser(name)
        p.add_argument("name")

    sub.add_parser("list")
    sub.add_parser("tick")
    sub.add_parser("status")
    p_loop = sub.add_parser("loop")
    p_loop.add_argument("--poll", type=int, default=60)

    args = parser.parse_args()
    if args.command == "add":
        schedule = "interval" if args.interval else ("daily" if args.daily else "once")
        out = add_job(args.name, args.cmd, schedule, args.interval, args.daily, args.timeout)
        print(json.dumps(out, indent=2))
        sys.exit(0 if out["added"] else 1)
    elif args.command == "list":
        print(json.dumps(list_jobs(), indent=2))
    elif args.command == "remove":
        print(json.dumps(remove_job(args.name), indent=2))
    elif args.command == "enable":
        print(json.dumps(set_enabled(args.name, True), indent=2))
    elif args.command == "disable":
        print(json.dumps(set_enabled(args.name, False), indent=2))
    elif args.command == "tick":
        print(json.dumps(tick(), indent=2))
    elif args.command == "status":
        print(json.dumps(status(), indent=2))
    elif args.command == "loop":
        loop(args.poll)


if __name__ == "__main__":
    main()
