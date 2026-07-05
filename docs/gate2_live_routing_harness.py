#!/usr/bin/env python3
"""
gate2_live_routing_harness.py — Gate 2 closure: REAL behavioral proof that
Apollo (SKILL.md) routes a natural-language request to the correct sub-skill.

Why this exists (read before running): `test_hermes.py`'s
TestApolloRoutingStructural checks that every row in Apollo's routing table
points at a file that actually exists and is well-formed. It does NOT prove
Apollo (an LLM reading a markdown file, not executable code) actually picks
the right row when a real user types a real sentence. The only way to prove
that is to run a real Claude session against real prompts and read what it
actually did — which is what this script does. It is deliberately NOT part
of test_hermes.py: it costs real API tokens and wall-clock time (each case
is a live `claude -p` child), and it needs the `claude` CLI on PATH and the
HERMES plugin installed — none of which belong in a fast, offline unit suite.

Method: for each (prompt, expected_marker) case, spawn `claude -p <prompt>`
with cwd=HERMES root (same pattern delegation/dispatch.py uses for children),
instructing it to name the routing decision WITHOUT executing the full
sub-skill (so this stays cheap — one short turn per case, not a full build).
Pass = expected_marker (a distinctive path fragment from Apollo's own
routing table) appears in the transcript. This is still an imperfect
proxy — a model could name the right file without truly reading it, or
paraphrase around a literal path — but it is genuine evidence from a real
model turn, not a static string check.

Run:  python3 docs/gate2_live_routing_harness.py
      python3 docs/gate2_live_routing_harness.py --model claude-sonnet-5
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DRY_RUN_SUFFIX = (
    " — Do not actually build/execute anything yet. Just tell me, in one "
    "sentence, which SKILL.md or script file you (Apollo) would route this "
    "request to, per your §3 routing table, and stop there."
)

# (prompt, expected path fragment from SKILL.md's own §3 routing table)
CASES = [
    ("Build me a landing page for my startup." + DRY_RUN_SUFFIX, "skills/create/SKILL.md"),
    ("Research the current state of post-quantum cryptography adoption." + DRY_RUN_SUFFIX,
     "skills/research/SKILL.md"),
    ("Break this project down into a task list for me." + DRY_RUN_SUFFIX, "skills/tasks/SKILL.md"),
    ("Turn this report I already wrote into a PDF." + DRY_RUN_SUFFIX, "skills/documents/SKILL.md"),
    ("What did we decide about the vault path last week?" + DRY_RUN_SUFFIX,
     "mnemos/hybrid_search.py"),
    ("How many tokens have I burned this session?" + DRY_RUN_SUFFIX, "clio/tracker.py"),
    ("Spawn three sub-agents to review this codebase in parallel." + DRY_RUN_SUFFIX,
     "delegation/dispatch.py"),
    ("Schedule this to run every night at 3am." + DRY_RUN_SUFFIX, "cron/scheduler.py"),
    ("Open this URL and tell me what's on the page." + DRY_RUN_SUFFIX, "fetcher/fetch.py"),
    ("Connect HERMES to my Notion workspace." + DRY_RUN_SUFFIX, "connect/mcp_client.py"),
]


def run_case(prompt: str, expected: str, model: str, timeout_s: int):
    argv = ["claude", "-p", prompt, "--allowedTools", "Read,Grep,Glob"]
    if model:
        argv += ["--model", model]
    started = time.time()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                               timeout=timeout_s, cwd=str(ROOT))
        output = (proc.stdout or proc.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return {"passed": False, "elapsed_ms": int((time.time() - started) * 1000),
                "output": f"TIMEOUT after {timeout_s}s"}
    except FileNotFoundError:
        print("FATAL: `claude` not found on PATH. Install it first "
              "(see README.md Setup) — this harness needs the real CLI.",
              file=sys.stderr)
        sys.exit(2)
    elapsed_ms = int((time.time() - started) * 1000)
    return {"passed": expected in output, "elapsed_ms": elapsed_ms, "output": output[:300]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="override model (e.g. claude-sonnet-5)")
    ap.add_argument("--timeout", type=int, default=60, help="per-case timeout in seconds")
    args = ap.parse_args()

    if not shutil.which("claude"):
        print("FATAL: `claude` not on PATH. This harness needs the real CLI installed "
              "(curl -fsSL https://claude.ai/install.sh | bash) — it cannot be faked.",
              file=sys.stderr)
        sys.exit(2)

    print(f"Gate 2 live routing harness — {len(CASES)} cases, real `claude -p` children.\n")
    results = []
    for prompt, expected in CASES:
        r = run_case(prompt, expected, args.model, args.timeout)
        results.append((expected, r))
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] expect={expected!r} ({r['elapsed_ms']}ms)")
        if not r["passed"]:
            print(f"        got: {r['output']!r}")

    passed = sum(1 for _, r in results if r["passed"])
    print(f"\n{passed}/{len(results)} routing decisions confirmed live.")
    if passed < len(results):
        print("Some routing decisions were NOT confirmed — either Apollo routed "
              "wrong, or it didn't name the file plainly enough for this string "
              "check. Read the 'got' output above before concluding the routing "
              "table itself is broken.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
