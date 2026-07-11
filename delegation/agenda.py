#!/usr/bin/env python3
"""
delegation/agenda.py — durable task agenda + auto-resume across usage-limit
resets (Stage 3C extension).

Pattern sources (reimplemented fresh, no code copied):
  - autoresearch (Karpathy): a durable agenda file drives repeated unattended
    runs until done-criteria are met — the program.md loop, generalized.
  - claw-code RecoveryLedger: retry up to N genuine failures, then STOP and
    surface to the human. Never a silent infinite spiral.
  - claude-skills-main C-level handoff: every resume prompt carries
    CONTEXT / CONSTRAINT / CRITERIA / CONTINUE.

What this actually does (honest scope — read before trusting it):
  The Claude usage window is a rolling limit. Nothing can detect the exact
  reset moment, so this module doesn't try: a cron tick retries the agenda
  every interval. While the limit is hit, each attempt fails in seconds with
  a rate-limit marker (`dispatch.classify_output` → 'rate_limited') and costs
  nothing; those attempts do NOT count toward the stall limit. The first tick
  after the window resets does real work again — no human "continue" needed.
  "Immediately" therefore means "within one tick interval" (default 15 min).

  This is resume-from-notes, NOT a live-session restore. Each attempt is a
  fresh `claude -p` child that receives the goal plus every accumulated
  progress note. In-context state of the session where the limit hit is gone
  (platform-owned); anything worth surviving must be in the notes — which is
  exactly what the child is instructed to emit each run.

Write policy: agenda children may Read/Grep/Glob/WebSearch and Write/Edit
INSIDE their own workspace — by default delegation/agenda/<id>.workspace/
(the child's cwd; enforcement is cwd + prompt constraint, not a filesystem
jail, and the platform's file_safety denylist still applies where hooks
fire). Bash is granted ONLY if the human passed --allow-bash at add-time:
the human gate is the add-time decision (Invariant #3 — unattended runs
never self-escalate).

External workspace (2026-07-06): --workspace <path> at add-time points the
child's cwd at any directory instead of the internal default — e.g. a
project folder that lives outside the hermes repo entirely. This exists
because the default workspace assumes the goal is about HERMES itself;
building something unrelated (a separate app/game/whatever) needs its own
project folder, not a subfolder buried inside hermes/delegation/agenda/.
Same caveat applies, more so: it is still cwd + prompt constraint, NOT a
sandbox jail — an external workspace is a real directory on disk with
whatever else lives there, so only point this at a folder you're fine
having an unattended agent (with Bash, if you granted it) write into.

CLI:
    python3 delegation/agenda.py add "<goal>" [--context "..."] [--allow-bash]
                                   [--child-timeout 1800] [--max-failures 5]
                                   [--workspace /path/to/project]
    python3 delegation/agenda.py tick [--dry-run]     # cron calls this
    python3 delegation/agenda.py list | show <id> | status
    python3 delegation/agenda.py done <id> | abandon <id> | retry <id>
    python3 delegation/agenda.py install-cron [--interval 900]
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
AGENDA_DIR = Path(__file__).resolve().parent / "agenda"

sys.path.insert(0, str(HERMES_ROOT / "meta" / "security"))
sys.path.insert(0, str(HERMES_ROOT / "delegation"))
import redact    # noqa: E402
import dispatch  # noqa: E402

AGENDA_CHILD_ALLOWED = ("Read", "Grep", "Glob", "WebSearch", "Write", "Edit")
DEFAULT_CHILD_TIMEOUT = 1800     # one attempt may work for 30 min
DEFAULT_MAX_FAILURES = 5         # consecutive GENUINE failures → stalled
MAX_TOTAL_ATTEMPTS = 200         # absolute ceiling — misclassification fuse
DONE_MARKER = "AGENDA_STATUS: DONE"
CONTINUE_MARKER = "AGENDA_STATUS: CONTINUE"
PROGRESS_NOTE_MAX = 400
PROGRESS_KEEP = 40               # most recent notes carried into the prompt


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(agenda_id: str) -> Path:
    return AGENDA_DIR / f"{agenda_id}.json"


def _workspace(agenda_id: str) -> Path:
    return AGENDA_DIR / f"{agenda_id}.workspace"


def _effective_workspace(agenda: dict) -> Path:
    """The directory a child actually runs in: the external override if one
    was set at add-time, else the default internal workspace. Centralizing
    this is what lets tick() not care which case it is."""
    external = agenda.get("external_workspace")
    return Path(external) if external else _workspace(agenda["id"])


def _load(agenda_id: str) -> dict:
    return json.loads(_path(agenda_id).read_text())


def _save(agenda: dict):
    AGENDA_DIR.mkdir(parents=True, exist_ok=True)
    _path(agenda["id"]).write_text(json.dumps(agenda, indent=2) + "\n")


def _all() -> list:
    if not AGENDA_DIR.exists():
        return []
    out = []
    for f in sorted(AGENDA_DIR.glob("ag-*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            print(f"agenda: unreadable state file skipped: {f.name}", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------

def add(goal: str, context: str = "", allow_bash: bool = False,
        child_timeout: int = DEFAULT_CHILD_TIMEOUT,
        max_failures: int = DEFAULT_MAX_FAILURES, workspace: str = None,
        model: str = None) -> dict:
    # non-security digest — agenda id only (usedforsecurity=False; audit L4)
    agenda_id = "ag-" + hashlib.md5(f"{goal}|{time.time()}".encode(), usedforsecurity=False).hexdigest()[:8]
    external_workspace = None
    if workspace:
        external_workspace = str(Path(workspace).expanduser().resolve())
    agenda = {
        "id": agenda_id,
        "goal": goal,
        "context": context,
        "status": "active",          # active | done | stalled | abandoned
        "allow_bash": bool(allow_bash),
        "child_timeout": int(child_timeout),
        "max_failures": int(max_failures),
        "external_workspace": external_workspace,  # None = default internal workspace
        # Pin the model for every child attempt (2026-07-11: agenda previously
        # had no way to specify this — every tick fell through to whatever
        # the bare `claude` CLI resolves to for the workspace cwd, which is
        # NOT necessarily what an interactive session (e.g. VS Code) has
        # configured, since each tick is a fresh headless subprocess, not a
        # continuation of any running session. None = same old bare-default
        # behavior, unchanged for existing callers.
        "model": model,
        "created_at": _now_iso(),
        "attempts": 0,
        "rate_limited_count": 0,
        "consecutive_failures": 0,
        "last_attempt_at": None,
        "last_status": None,
        "result": None,
        "progress": [],              # [{at, status, note}]
    }
    ws = _effective_workspace(agenda)
    ws.mkdir(parents=True, exist_ok=True)
    _save(agenda)
    return {"added": True, "id": agenda_id, "workspace": str(ws),
            "external_workspace": bool(external_workspace),
            "allow_bash": agenda["allow_bash"],
            "model": agenda["model"] or "(CLI default — not pinned)",
            "note": "run `install-cron` once so ticks fire unattended"}


def _set_status(agenda_id: str, status: str, note: str = None) -> dict:
    try:
        agenda = _load(agenda_id)
    except FileNotFoundError:
        return {"ok": False, "reason": f"no agenda '{agenda_id}'"}
    agenda["status"] = status
    if status == "active":
        agenda["consecutive_failures"] = 0
    if note:
        agenda["progress"].append({"at": _now_iso(), "status": status, "note": note})
    _save(agenda)
    return {"ok": True, "id": agenda_id, "status": status}


# ---------------------------------------------------------------------------
# resume prompt — C-level handoff (CONTEXT / CONSTRAINT / CRITERIA / CONTINUE)
# ---------------------------------------------------------------------------

def build_resume_prompt(agenda: dict) -> str:
    notes = agenda["progress"][-PROGRESS_KEEP:]
    notes_block = "\n".join(
        f"  {n['at']} [{n['status']}] {n['note']}" for n in notes) or "  (none yet — first attempt)"
    bash_line = ("Bash is available." if agenda["allow_bash"]
                 else "Bash is NOT available to you.")
    return (
        "You are an unattended HERMES agenda worker, resumed automatically. "
        "Nobody is watching; you cannot ask questions.\n\n"
        f"CONTEXT: Goal of this agenda: {agenda['goal']}\n"
        + (f"Extra context: {agenda['context']}\n" if agenda["context"] else "")
        + f"Progress notes from prior attempts (oldest first):\n{notes_block}\n\n"
        f"CONSTRAINT: Work only inside the current working directory (your "
        f"workspace). {bash_line} Do nothing destructive. Do not touch paths "
        f"outside the workspace.\n\n"
        f"CRITERIA: The agenda is DONE only when the goal above is fully met "
        f"with evidence in the workspace (files written, findings recorded).\n\n"
        f"CONTINUE: Do the next concrete chunk of work now — do not re-plan "
        f"from scratch; trust the notes. End your output with EXACTLY one "
        f"line, nothing after it:\n"
        f"{DONE_MARKER} <one-line result>   (only if CRITERIA fully met)\n"
        f"{CONTINUE_MARKER} <one line: what you just did + the single next step>"
    )


# ---------------------------------------------------------------------------
# tick — one attempt for the most-starved active agenda
# ---------------------------------------------------------------------------

def _default_runner(argv, cwd: str, timeout_seconds: int):
    """Returns (returncode, combined_output). Injectable for tests."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout_seconds, cwd=cwd)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, f"attempt hit the {timeout_seconds}s child timeout (interrupted)"


def _write_mnemos(agenda: dict, summary: str):
    """Same degrade contract as cron: Mnemos failure never fails the agenda."""
    try:
        sys.path.insert(0, str(HERMES_ROOT / "mnemos"))
        import store
        store.write_message(f"agenda:{agenda['id']}", "assistant",
                            redact.redact(summary), memory_type="project")
    except Exception as e:
        print(f"agenda: Mnemos write failed ({e}) — result kept in agenda file only",
              file=sys.stderr)


def _extract_note(output: str) -> tuple:
    """Returns (kind, note): kind in {'done','continue','none'}."""
    for line in reversed((output or "").strip().splitlines()):
        line = line.strip()
        if line.startswith(DONE_MARKER):
            return "done", line[len(DONE_MARKER):].strip()[:PROGRESS_NOTE_MAX]
        if line.startswith(CONTINUE_MARKER):
            return "continue", line[len(CONTINUE_MARKER):].strip()[:PROGRESS_NOTE_MAX]
    return "none", (output or "").strip()[-PROGRESS_NOTE_MAX:]


def tick(runner=None, dry_run: bool = False) -> dict:
    """One attempt on ONE active agenda per tick (oldest last_attempt first)
    so tick duration stays bounded by a single child timeout — that is what
    lets cron host this without its hard interrupt killing mid-work."""
    runner = runner or _default_runner
    active = [a for a in _all() if a["status"] == "active"]
    if not active:
        return {"ticked": True, "attempted": None, "reason": "no active agendas"}
    agenda = sorted(active, key=lambda a: a["last_attempt_at"] or "")[0]

    allowed = AGENDA_CHILD_ALLOWED + (("Bash",) if agenda["allow_bash"] else ())
    argv = dispatch.build_child_command(build_resume_prompt(agenda),
                                        allowed_tools=allowed,
                                        model=agenda.get("model"))
    ws = _effective_workspace(agenda)
    if dry_run:
        return {"ticked": True, "attempted": agenda["id"], "dry_run": True,
                "argv": argv, "cwd": str(ws)}
    if not dispatch.claude_cli_available():
        return {"ticked": False, "attempted": agenda["id"],
                "reason": "claude CLI not on PATH — agenda needs the CLI host"}

    ws.mkdir(parents=True, exist_ok=True)
    rc, output = runner(argv, str(ws), agenda["child_timeout"])
    status = dispatch.classify_output(rc, output)

    agenda["attempts"] += 1
    agenda["last_attempt_at"] = _now_iso()
    agenda["last_status"] = status

    if status == "rate_limited":
        # The whole point: not a failure. Stay active, retry next tick.
        agenda["rate_limited_count"] += 1
        agenda["progress"].append({"at": _now_iso(), "status": "rate_limited",
                                   "note": "usage window exhausted — will retry "
                                           "automatically next tick"})
    elif status == "completed":
        agenda["consecutive_failures"] = 0
        kind, note = _extract_note(output)
        if kind == "done":
            agenda["status"] = "done"
            agenda["result"] = note
            agenda["progress"].append({"at": _now_iso(), "status": "done", "note": note})
            _write_mnemos(agenda, f"agenda '{agenda['goal'][:80]}' DONE: {note}")
        else:
            agenda["progress"].append({"at": _now_iso(), "status": "continue",
                                       "note": redact.redact(note)})
    else:  # failed / interrupted — the RecoveryLedger path
        agenda["consecutive_failures"] += 1
        agenda["progress"].append({"at": _now_iso(), "status": "failed",
                                   "note": redact.redact((output or "")[-PROGRESS_NOTE_MAX:])})
        if agenda["consecutive_failures"] >= agenda["max_failures"]:
            agenda["status"] = "stalled"
            _write_mnemos(agenda, f"agenda '{agenda['goal'][:80]}' STALLED after "
                                  f"{agenda['consecutive_failures']} consecutive failures "
                                  f"— needs human review (`agenda.py retry {agenda['id']}`)")

    if agenda["attempts"] >= MAX_TOTAL_ATTEMPTS and agenda["status"] == "active":
        agenda["status"] = "stalled"
        agenda["progress"].append({"at": _now_iso(), "status": "stalled",
                                   "note": f"absolute attempt ceiling {MAX_TOTAL_ATTEMPTS} "
                                           f"reached — human review required"})
    _save(agenda)
    return {"ticked": True, "attempted": agenda["id"], "status": agenda["status"],
            "attempt_status": status, "attempts": agenda["attempts"],
            "rate_limited_count": agenda["rate_limited_count"]}


# ---------------------------------------------------------------------------
# cron wiring
# ---------------------------------------------------------------------------

def install_cron(interval_seconds: int = 900) -> dict:
    sys.path.insert(0, str(HERMES_ROOT / "cron"))
    import scheduler
    # Tick timeout must outlive one child attempt (tick = at most one child).
    timeout = max(DEFAULT_CHILD_TIMEOUT, *(a["child_timeout"] for a in _all())) + 120 \
        if _all() else DEFAULT_CHILD_TIMEOUT + 120
    return scheduler.add_job("agenda-tick",
                             "python3 delegation/agenda.py tick",
                             "interval", interval_seconds=interval_seconds,
                             timeout_seconds=timeout)


def status() -> dict:
    agendas = _all()
    return {"agenda_dir": str(AGENDA_DIR),
            "total": len(agendas),
            "active": [a["id"] for a in agendas if a["status"] == "active"],
            "stalled": [a["id"] for a in agendas if a["status"] == "stalled"],
            "done": [a["id"] for a in agendas if a["status"] == "done"],
            "tick_hosted_by": "cron job 'agenda-tick' (install-cron) under launchd — "
                              "Cowork cannot host this (Invariant #7)"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="delegation/agenda.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("goal")
    p_add.add_argument("--context", default="")
    p_add.add_argument("--allow-bash", action="store_true",
                       help="grant Bash to this agenda's children (human add-time decision)")
    p_add.add_argument("--child-timeout", type=int, default=DEFAULT_CHILD_TIMEOUT)
    p_add.add_argument("--max-failures", type=int, default=DEFAULT_MAX_FAILURES)
    p_add.add_argument("--workspace", default=None,
                       help="point the child's cwd at an external project folder "
                            "instead of the default internal delegation/agenda/<id>.workspace/")
    p_add.add_argument("--model", default=None,
                       help="pin every child attempt to this model (e.g. claude-sonnet-5, "
                            "claude-opus-4-8). Default: unset — falls through to whatever "
                            "the bare `claude` CLI resolves to for the workspace, which is "
                            "NOT the same as an interactive session's configured model.")

    p_tick = sub.add_parser("tick")
    p_tick.add_argument("--dry-run", action="store_true")

    for name in ("show", "done", "abandon", "retry"):
        p = sub.add_parser(name)
        p.add_argument("id")

    sub.add_parser("list")
    sub.add_parser("status")
    p_ic = sub.add_parser("install-cron")
    p_ic.add_argument("--interval", type=int, default=900)

    args = parser.parse_args()
    if args.command == "add":
        out = add(args.goal, context=args.context, allow_bash=args.allow_bash,
                  child_timeout=args.child_timeout, max_failures=args.max_failures,
                  workspace=args.workspace, model=args.model)
    elif args.command == "tick":
        out = tick(dry_run=args.dry_run)
    elif args.command == "list":
        out = [{k: a[k] for k in ("id", "status", "goal", "attempts",
                                  "rate_limited_count", "last_attempt_at")}
               for a in _all()]
    elif args.command == "show":
        out = _load(args.id)
    elif args.command == "done":
        out = _set_status(args.id, "done", "manually marked done")
    elif args.command == "abandon":
        out = _set_status(args.id, "abandoned", "manually abandoned")
    elif args.command == "retry":
        out = _set_status(args.id, "active", "manually reactivated after stall")
    elif args.command == "install-cron":
        out = install_cron(args.interval)
    elif args.command == "status":
        out = status()
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
