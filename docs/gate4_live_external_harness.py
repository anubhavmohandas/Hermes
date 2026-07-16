#!/usr/bin/env python3
"""
gate4_live_external_harness.py — Gate 4 closure: REAL proof that the three
external-integration paths built in Stage 3 (Cron/Delegation/Fetcher/Connect)
actually work against live infrastructure, not just unit-tested against
mocks or "file exists" checks.

Why this exists (read before running): test_hermes.py exercises
nvidia_client.py, fetcher/fetch.py, and connect/mcp_client.py with no
network calls — status()/dry-run paths, argument parsing, brain.py's
allow/deny logic. None of that proves the real NVIDIA API answers a real
chat request, a real search API returns real results, or a real MCP server
completes capability negotiation over stdio. This script makes those three
live calls and refuses to report a pass unless it got a genuine external
response. It will NOT fabricate a result if a leg is unconfigured — it
reports SKIPPED with the reason, same as fetch.py's own "results are never
faked" rule.

This is deliberately NOT part of test_hermes.py: it needs a real
NVIDIA_API_KEY, a real TAVILY_API_KEY or FIRECRAWL_API_KEY, and a real MCP server
binary on PATH — none of which belong in an offline unit suite, and none of
which exist in a sandboxed CI/Cowork environment. Run this on the machine
that actually has that infrastructure (mirrors Gate 0: FUSE-mounted sandbox
!= real disk; this is the same shape of gap for network services).

Three legs, each independently pass/fail/skip:
  1. nvidia   — nvidia_client.py status, then a real chat() call
  2. fetcher  — fetcher/fetch.py status, then a real search() call
                (Tavily first, Firecrawl fallback — whichever key is set)
  3. connect  — connect/mcp_client.py status, then tools-list against a
                real MCP server you provide via --mcp-server

Run:
    python3 docs/gate4_live_external_harness.py
    python3 docs/gate4_live_external_harness.py --nvidia-model meta/llama-3.3-70b-instruct
    python3 docs/gate4_live_external_harness.py --mcp-server "npx -y @modelcontextprotocol/server-filesystem /tmp"
    python3 docs/gate4_live_external_harness.py --skip-nvidia --skip-connect   # e.g. search-only pass

Exit code: 0 only if every non-skipped leg passed. SKIPPED legs do not fail
the run (they're infra gaps, not code bugs) but ARE printed loudly and MUST
be listed as still-open in the gate log — a green exit code here is not the
same as "Gate 4 closed for all three legs."
"""
import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_cli(args, timeout):
    """Run one of HERMES's own CLI entry points as a subprocess (same
    boundary a real caller uses — no importing internals, no mocking)."""
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable] + args, cwd=ROOT,
            capture_output=True, text=True, timeout=timeout,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        return proc.returncode, proc.stdout, proc.stderr, latency_ms
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s", int(timeout * 1000)


def leg_nvidia(model, timeout):
    name = "nvidia"
    rc, out, err, _ = run_cli(["nvidia_client.py", "status"], timeout=10)
    if rc != 0:
        return name, "FAIL", f"status check failed: {err.strip()}", None
    try:
        status = json.loads(out)
    except json.JSONDecodeError:
        return name, "FAIL", f"status returned non-JSON: {out[:200]}", None

    if not model and not status.get("configured", True) and not status.get("model"):
        pass  # keep going — chat() will produce the authoritative error either way

    prompt = "Reply with exactly the single word: PONG"
    args = ["nvidia_client.py", "chat", prompt]
    if model:
        args += ["--model", model]
    rc, out, err, latency_ms = run_cli(args, timeout=timeout)
    if rc != 0:
        low = err.lower()
        if "unreachable" in low or "no model given" in low or "nvidia_api_key" in low:
            return name, "SKIPPED", err.strip(), None
        return name, "FAIL", err.strip(), latency_ms
    try:
        result = json.loads(out)
    except json.JSONDecodeError:
        return name, "FAIL", f"chat returned non-JSON: {out[:200]}", latency_ms
    content = result.get("content", "")
    if not content.strip():
        return name, "FAIL", "chat returned empty content — server up but model produced nothing", latency_ms
    return name, "PASS", f"model={result.get('model')} tokens={result.get('tokens')} " \
                          f"latency_ms={result.get('latency_ms', latency_ms)} reply={content[:80]!r}", latency_ms


def leg_fetcher(query, timeout):
    name = "fetcher/search"
    rc, out, err, _ = run_cli(["fetcher/fetch.py", "status"], timeout=10)
    if rc != 0:
        return name, "FAIL", f"status check failed: {err.strip()}", None
    try:
        status = json.loads(out)
    except json.JSONDecodeError:
        return name, "FAIL", f"status returned non-JSON: {out[:200]}", None
    backends = status.get("backends", {})
    if not backends.get("tavily") and not backends.get("firecrawl"):
        return name, "SKIPPED", "no TAVILY_API_KEY or FIRECRAWL_API_KEY set", None

    start = time.monotonic()
    rc, out, err, latency_ms = run_cli(["fetcher/fetch.py", "search", query], timeout=timeout)
    if rc != 0:
        return name, "FAIL", err.strip() or out.strip(), latency_ms
    try:
        result = json.loads(out)
    except json.JSONDecodeError:
        return name, "FAIL", f"search returned non-JSON: {out[:200]}", latency_ms
    if result.get("reason", "").startswith("no search backend"):
        return name, "SKIPPED", result["reason"], latency_ms
    results = result.get("results") or result.get("data") or []
    if not results:
        return name, "FAIL", f"backend responded but returned zero results: {json.dumps(result)[:200]}", latency_ms
    return name, "PASS", f"backend={'tavily' if backends.get('tavily') else 'firecrawl'} " \
                          f"n_results={len(results)} latency_ms={latency_ms}", latency_ms


def leg_connect(server_cmd, timeout):
    name = "connect/mcp"
    if not server_cmd:
        return name, "SKIPPED", "no --mcp-server provided — nothing to negotiate against", None
    rc, out, err, _ = run_cli(["connect/mcp_client.py", "status"], timeout=10)
    if rc != 0:
        return name, "FAIL", f"status check failed: {err.strip()}", None

    args = ["connect/mcp_client.py", "tools", "--"] + shlex.split(server_cmd)
    start = time.monotonic()
    rc, out, err, latency_ms = run_cli(args, timeout=timeout)
    if rc != 0:
        return name, "FAIL", err.strip() or out.strip(), latency_ms
    try:
        result = json.loads(out)
    except json.JSONDecodeError:
        return name, "FAIL", f"tools returned non-JSON: {out[:200]}", latency_ms
    tools = result.get("tools", [])
    session = result.get("session", {})
    if not session:
        return name, "FAIL", "no session/capability-negotiation info in response", latency_ms
    return name, "PASS", f"session={json.dumps(session)[:120]} n_tools={len(tools)} latency_ms={latency_ms}", latency_ms


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--nvidia-model", default=None)
    p.add_argument("--search-query", default="what is the capital of France")
    p.add_argument("--mcp-server", default=None,
                   help='e.g. "npx -y @modelcontextprotocol/server-filesystem /tmp"')
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--skip-nvidia", action="store_true")
    p.add_argument("--skip-fetcher", action="store_true")
    p.add_argument("--skip-connect", action="store_true")
    args = p.parse_args()

    legs = []
    if not args.skip_nvidia:
        legs.append(leg_nvidia(args.nvidia_model, args.timeout))
    if not args.skip_fetcher:
        legs.append(leg_fetcher(args.search_query, args.timeout))
    if not args.skip_connect:
        legs.append(leg_connect(args.mcp_server, args.timeout))

    print("\n=== Gate 4 live external-path harness ===")
    any_fail = False
    for name, status, detail, latency_ms in legs:
        marker = {"PASS": "PASS", "FAIL": "FAIL", "SKIPPED": "SKIP"}[status]
        print(f"[{marker}] {name}: {detail}")
        if status == "FAIL":
            any_fail = True

    skipped = [l for l in legs if l[1] == "SKIPPED"]
    if skipped:
        print(f"\n{len(skipped)} leg(s) SKIPPED — infra not present on this machine. "
              "A green exit code does NOT mean Gate 4 is closed for those legs; "
              "list them explicitly as still-open in the gate log.")

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
