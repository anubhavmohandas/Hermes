#!/usr/bin/env python3
"""
delegation/start_loop.py — friendly front door onto Cron + Delegation/Agenda.

Pattern source: none — this is a thin UX wrapper, not a new subsystem. It
adds zero new execution capability: every path here ends by calling the
same `agenda.add()` / `cron_scheduler.add_job()` / `agenda.install_cron()`
functions that already exist and are already gated by `classify_unattended`
(Gate 3) and Invariant #3 (human decides `--allow-bash` at add-time, never
after). Lives inside `delegation/` — a new FILE in an already-frozen module,
not a new module (see docs/DECISIONS.md, architecture freeze: "new files
within a frozen module are fine; new modules are not").

Why this exists: setting up a recurring/overnight job today means knowing
in advance whether you want `agenda.py add` (a goal, retried until done)
or `cron/scheduler.py add` (a fixed command on a schedule), plus the right
flags. Most people don't carry that distinction around. This asks three or
four plain questions and calls the right thing.

Invariant #7, stated honestly up front and again at the end: Cowork cannot
host the actual unattended loop — a session needs a human present. This
script can create the agenda/cron row from ANYWHERE (Cowork included; it's
just a SQLite insert), but the row only actually fires once launchd is
ticking `cron/scheduler.py` on the real machine (see docs/SCHEDULING.md).
Creating the row is not the same as it running unattended yet.

Usage (interactive — run this yourself, in a real terminal, CLI or Cowork):
    python3 delegation/start_loop.py

Usage (non-interactive, for scripting/testing — no prompts, no side effects
unless --commit is passed):
    python3 delegation/start_loop.py --non-interactive --kind agenda \\
        --goal "keep drafting the Q3 report" --dry-run
"""
import argparse
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT))
sys.path.insert(0, str(HERMES_ROOT / "delegation"))
sys.path.insert(0, str(HERMES_ROOT / "cron"))


def _on_fuse_mount() -> bool:
    """D8 (docs/DECISIONS.md): cron.db (SQLite) writes fail with 'disk I/O
    error' on Cowork's FUSE-mounted view of this repo. Detect it up front
    so the failure is a clear one-line warning, not a raw traceback."""
    try:
        with open("/proc/mounts") as f:
            mounts = f.read()
    except OSError:
        return False  # not Linux / no /proc — assume fine, don't guess wrong
    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "fuse" and str(HERMES_ROOT).startswith(parts[1]):
            return True
    return False
import agenda            # noqa: E402
import scheduler as cron_scheduler  # noqa: E402


def _ask(prompt: str, default: str = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else (default or "")


def _ask_yn(prompt: str, default_no: bool = True) -> bool:
    d = "y/N" if default_no else "Y/n"
    val = input(f"{prompt} ({d}): ").strip().lower()
    if not val:
        return not default_no
    return val.startswith("y")


def run_interactive():
    print("HERMES loop setup — three questions, then it's live.\n")
    print("Kya kaam hai jo repeat/loop mein chalana hai? (ek line mein)")
    goal = _ask("Goal")
    if not goal:
        print("Koi goal nahi diya — ruk raha hoon.", file=sys.stderr)
        return 2

    print(
        "\nYeh kaam kis type ka hai?\n"
        "  (1) Ek poora kaam jab tak DONE na ho jaaye — retries automatically,\n"
        "      stops after real failures or when it reports done. (agenda)\n"
        "  (2) Ek fixed command jo baar-baar / schedule pe chalna hai\n"
        "      (e.g. 'roz raat 3 baje yeh script chalao'). (cron)\n"
    )
    kind = _ask("Kaunsa (1/2)", default="1")

    if kind.strip() == "2":
        return _setup_cron_interactive()
    return _setup_agenda_interactive(goal)


def _setup_agenda_interactive(goal: str):
    context = _ask("Koi extra context/constraint? (khaali chhod sakte ho)", default="")
    allow_bash = _ask_yn(
        "Bash chahiye is kaam ke bachchon (children) ko? Yeh ek human decision hai, "
        "baad mein badal nahi sakte — 'no' safe default hai jab tak file-editing se\n"
        "zyada kuch nahi chahiye",
        default_no=True,
    )
    workspace = _ask(
        "Kis folder mein kaam ho? (khaali = HERMES ke andar apna default workspace)",
        default="",
    ) or None

    out = agenda.add(goal, context=context, allow_bash=allow_bash, workspace=workspace)
    if not out.get("added"):
        print(f"\nAgenda create nahi hui: {out}", file=sys.stderr)
        return 1

    print(f"\nAgenda '{out['id']}' ban gayi. Workspace: {out['workspace']}")
    if _on_fuse_mount():
        print("\nSKIP: cron wiring ('agenda-tick') yahan nahi kar raha — is session ka "
              "repo-view FUSE-mounted hai aur cron.db (SQLite) writes yahan reliably fail "
              "hote hain (D8, docs/DECISIONS.md). Agenda ban chuki hai (safe, JSON-based) — "
              "bas 'install-cron' ka step CLI host se karna hoga:\n"
              "  python3 delegation/agenda.py install-cron")
    else:
        install_out = agenda.install_cron()
        if install_out.get("added") or "already exists" in str(install_out.get("reason", "")):
            print("Cron job 'agenda-tick' wired — jab bhi launchd tick karega, yeh agenda "
                  "automatically retry hogi jab tak done na ho.")
        else:
            print(f"NOTE: cron wiring on 'agenda-tick' returned: {install_out}")
    _print_invariant7_reminder()
    print(f"\nStatus check karne ke liye: python3 delegation/agenda.py show {out['id']}")
    return 0


def _setup_cron_interactive():
    print(
        "\nCommand kya hai? Sirf yeh chal sakta hai (Gate 3 allowlist):\n"
        "  - 'python3 <script-under-HERMES-repo>' (inline -c/-m allowed nahi)\n"
        "  - ya ek trivially-safe binary: echo, true, false, sleep, date\n"
    )
    if _on_fuse_mount():
        print("\nRuk jao — is session ka repo-view FUSE-mounted hai, aur cron.db (SQLite) "
              "writes yahan reliably fail hote hain 'disk I/O error' ke saath (D8, "
              "docs/DECISIONS.md). Yeh CLI host (real Mac) se karo:\n"
              "  python3 delegation/start_loop.py\n"
              "ya seedha: python3 cron/scheduler.py add ...", file=sys.stderr)
        return 1

    command = _ask("Command")
    ok, reason = cron_scheduler.classify_unattended(command)
    if not ok:
        print(f"\nYeh command allowlist mein nahi hai: {reason}\n"
              f"(security reason — dekho docs/DECISIONS.md, Gate 3 threat model)",
              file=sys.stderr)
        return 1

    name = _ask("Is job ka naam (koi bhi unique naam)")
    print("\nSchedule kaisa chahiye?\n  (1) Har X second baad\n  (2) Roz ek fixed time pe\n  (3) Ek hi baar")
    sched_choice = _ask("Kaunsa (1/2/3)", default="1")

    schedule, interval_seconds, daily_time = "interval", 3600, None
    if sched_choice.strip() == "2":
        schedule = "daily"
        daily_time = _ask("Kis time pe (HH:MM, 24hr)", default="03:00")
    elif sched_choice.strip() == "3":
        schedule = "once"
    else:
        interval_seconds = int(_ask("Kitne seconds baad", default="3600") or 3600)

    out = cron_scheduler.add_job(name, command, schedule,
                                  interval_seconds=interval_seconds if schedule == "interval" else None,
                                  daily_time=daily_time if schedule == "daily" else None)
    if not out.get("added"):
        print(f"\nJob create nahi hua: {out}", file=sys.stderr)
        return 1
    print(f"\nCron job '{name}' ban gaya. Next run: {out['next_run']}")
    _print_invariant7_reminder()
    print(f"\nStatus check karne ke liye: python3 cron/scheduler.py list")
    return 0


def _print_invariant7_reminder():
    print(
        "\nEk cheez samajh lo: yeh row database mein ban gayi hai, lekin isse "
        "GENUINELY unattended chalane ke liye launchd ko real Mac pe wire karna "
        "padega ek baar (Cowork ek session ko host nahi kar sakta — Invariant #7). "
        "Agar pehle se launchd setup hai, toh bas ho gaya. Agar nahi, dekho "
        "docs/SCHEDULING.md."
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--non-interactive", action="store_true",
                     help="skip prompts, use flags below (for scripting/testing)")
    ap.add_argument("--kind", choices=("agenda", "cron"), default="agenda")
    ap.add_argument("--goal", default=None, help="agenda goal (--kind agenda)")
    ap.add_argument("--command", default=None, help="cron command (--kind cron)")
    ap.add_argument("--name", default=None, help="cron job name (--kind cron)")
    ap.add_argument("--schedule", choices=("interval", "daily", "once"), default="interval")
    ap.add_argument("--interval-seconds", type=int, default=3600)
    ap.add_argument("--daily-time", default="03:00")
    ap.add_argument("--allow-bash", action="store_true")
    ap.add_argument("--workspace", default=None)
    ap.add_argument("--dry-run", action="store_true",
                     help="validate only — classify_unattended for cron, or just echo "
                          "what would be created for agenda; writes nothing")
    args = ap.parse_args()

    if not args.non_interactive:
        return run_interactive()

    if args.kind == "cron":
        if not args.command or not args.name:
            print("--non-interactive --kind cron needs --command and --name", file=sys.stderr)
            return 2
        ok, reason = cron_scheduler.classify_unattended(args.command)
        if not ok:
            print(f"REFUSED: {reason}")
            return 1
        if args.dry_run:
            print(f"DRY RUN — would create cron job {args.name!r}: {args.command!r} "
                  f"({args.schedule})")
            return 0
        if _on_fuse_mount():
            print("REFUSED: FUSE-mounted repo view (D8, docs/DECISIONS.md) — cron.db "
                  "writes fail here. Run this from the CLI host instead.", file=sys.stderr)
            return 1
        out = cron_scheduler.add_job(
            args.name, args.command, args.schedule,
            interval_seconds=args.interval_seconds if args.schedule == "interval" else None,
            daily_time=args.daily_time if args.schedule == "daily" else None)
        print(out)
        return 0 if out.get("added") else 1

    # kind == agenda
    if not args.goal:
        print("--non-interactive --kind agenda needs --goal", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"DRY RUN — would create agenda: goal={args.goal!r} "
              f"allow_bash={args.allow_bash} workspace={args.workspace}")
        return 0
    out = agenda.add(args.goal, allow_bash=args.allow_bash, workspace=args.workspace)
    print(out)
    if out.get("added"):
        if _on_fuse_mount():
            print("SKIP install-cron: FUSE-mounted repo view (D8, docs/DECISIONS.md) — "
                  "run `python3 delegation/agenda.py install-cron` from the CLI host.")
        else:
            print(agenda.install_cron())
    return 0 if out.get("added") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nCancelled — nothing was saved.", file=sys.stderr)
        sys.exit(130)
