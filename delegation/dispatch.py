#!/usr/bin/env python3
"""
delegation/dispatch.py — Delegation (Phase 3C): sub-agent dispatch.

Pattern sources (reimplemented fresh, no code copied): claude-code-main
Agent/Task tool fan-out + claw-code-ultraworkers worker-pool cap + SuperClaude
sub-agent tool masking. Per HERMES_GOAL_Start_to_End.md Stage 3 item 2 and
SKILL.md §6, two constraints are LOCKED IN and not configurable:

  1. ≤ 3 concurrent children. A queue drains in waves; there is no flag to
     raise the cap. (Blueprint: "≤3 concurrent children".)
  2. Sub-agents NEVER receive `TaskStop`, `AskUserQuestion`, or
     `EnterPlanMode`, and `ExitPlanMode` is never granted downstream. These
     are appended as --disallowedTools on every child, unconditionally —
     a caller-supplied allow-list cannot re-grant them.

Async/overnight children (spawned from a Cron job, nobody watching) get a
further-restricted set: read/search tools only by default, because an
unattended child that can Write/Bash is an unattended mutation.

Children are `claude -p` (headless print-mode) subprocesses. If the `claude`
CLI is not on PATH, dispatch degrades to reporting exactly that (Invariant
#5) — it does not fake results. `--dry-run` builds and returns the exact
child argv without spawning anything, which is also what the test suite
exercises (tests must not burn API tokens).

CLI:
    python3 delegation/dispatch.py run "prompt one" "prompt two" [--async-profile]
                                       [--timeout 300] [--dry-run] [--model NAME]
    python3 delegation/dispatch.py status
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT / "meta" / "security"))
import redact  # noqa: E402

MAX_CHILDREN = 3  # locked in — see module docstring; do not parameterize

# Never granted to any child, regardless of caller wishes (SKILL.md §6).
FORBIDDEN_CHILD_TOOLS = ("TaskStop", "AskUserQuestion", "EnterPlanMode", "ExitPlanMode")

# Interactive children: working tool set minus the forbidden four.
DEFAULT_CHILD_ALLOWED = ("Read", "Grep", "Glob", "Bash", "Write", "Edit", "WebSearch")

# Async/overnight children (Cron-spawned): observation only. An unattended
# child that can mutate state answers to nobody — results come back as text
# and a HUMAN decides what to apply (Invariant #3).
ASYNC_CHILD_ALLOWED = ("Read", "Grep", "Glob", "WebSearch")

DEFAULT_TIMEOUT_SECONDS = 300


def claude_cli_available() -> bool:
    return shutil.which("claude") is not None


def build_child_command(prompt: str, allowed_tools=None, async_profile: bool = False,
                        model: str = None):
    """Returns the exact argv for one child. Pure function — the tests and
    --dry-run both lean on this being spawn-free."""
    allowed = tuple(allowed_tools) if allowed_tools else (
        ASYNC_CHILD_ALLOWED if async_profile else DEFAULT_CHILD_ALLOWED)
    # Strip forbidden tools even if the caller explicitly asked for them —
    # the restriction is architectural, not advisory.
    allowed = tuple(t for t in allowed if t not in FORBIDDEN_CHILD_TOOLS)
    argv = ["claude", "-p", prompt,
            "--allowedTools", ",".join(allowed),
            "--disallowedTools", ",".join(FORBIDDEN_CHILD_TOOLS)]
    if model:
        argv += ["--model", model]
    return argv


def _run_child(argv, timeout_seconds):
    started = time.time()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout_seconds, cwd=str(HERMES_ROOT))
        status = "completed" if proc.returncode == 0 else f"failed(rc={proc.returncode})"
        output = (proc.stdout or proc.stderr or "").strip()
    except subprocess.TimeoutExpired:
        status = "interrupted"
        output = f"child killed at {timeout_seconds}s timeout"
    except OSError as e:
        status = "failed(spawn)"
        output = str(e)
    return {"status": status,
            "output": redact.redact(output[:2000]),
            "elapsed_ms": int((time.time() - started) * 1000)}


def dispatch(prompts, async_profile: bool = False, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
             dry_run: bool = False, model: str = None):
    """Fan prompts out to child agents, at most MAX_CHILDREN in flight.
    More prompts than the cap queue and drain — they are not rejected,
    they wait. Returns one record per prompt, in input order."""
    commands = [build_child_command(p, async_profile=async_profile, model=model)
                for p in prompts]
    if dry_run:
        return {"dispatched": False, "dry_run": True,
                "max_concurrent": MAX_CHILDREN,
                "commands": commands}
    if not claude_cli_available():
        return {"dispatched": False,
                "reason": "claude CLI not on PATH — Delegation needs the CLI host "
                          "(Cowork cannot spawn children); no results were faked"}
    # ThreadPoolExecutor with max_workers=MAX_CHILDREN IS the concurrency cap:
    # each worker thread hosts exactly one child subprocess at a time.
    with ThreadPoolExecutor(max_workers=MAX_CHILDREN) as pool:
        results = list(pool.map(lambda argv: _run_child(argv, timeout_seconds), commands))
    return {"dispatched": True,
            "children": len(results),
            "max_concurrent": MAX_CHILDREN,
            "results": [{"prompt": p[:120], **r} for p, r in zip(prompts, results)]}


def status():
    return {
        "claude_cli": claude_cli_available(),
        "max_concurrent_children": MAX_CHILDREN,
        "forbidden_child_tools": list(FORBIDDEN_CHILD_TOOLS),
        "default_child_tools": list(DEFAULT_CHILD_ALLOWED),
        "async_child_tools": list(ASYNC_CHILD_ALLOWED),
        "default_timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
    }


def main():
    parser = argparse.ArgumentParser(prog="delegation/dispatch.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("prompts", nargs="+")
    p_run.add_argument("--async-profile", action="store_true",
                       help="overnight/unattended profile: observation-only tools")
    p_run.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--model", default=None)

    sub.add_parser("status")

    args = parser.parse_args()
    if args.command == "run":
        out = dispatch(args.prompts, async_profile=args.async_profile,
                       timeout_seconds=args.timeout, dry_run=args.dry_run,
                       model=args.model)
        print(json.dumps(out, indent=2))
        sys.exit(0 if out.get("dispatched") or out.get("dry_run") else 1)
    elif args.command == "status":
        print(json.dumps(status(), indent=2))


if __name__ == "__main__":
    main()
