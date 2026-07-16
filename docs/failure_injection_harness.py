#!/usr/bin/env python3
"""
failure_injection_harness.py — the follow-up Gate 4 named as still open in
its own proof log: Gate 4 proved the three external paths (Tier 2 chat,
Tavily, MCP) work once, under ideal conditions, with a human watching. It said
nothing about what happens when they break. This script breaks them on
purpose and checks whether HERMES fails closed (clean error, no hang, no
crash, no silent unsafe fallback) or just fails.

Unlike gate4_live_external_harness.py, most of this does NOT need real
external infra — failure conditions are cheap to manufacture locally:
  - "NVIDIA API unreachable" = point at a closed local port, no network needed.
  - "Tavily key invalid" = a garbage key against the real endpoint (a 401
    is a 401 whether the key was never valid or was revoked).
  - "MCP server misbehaves" = spawn a throwaway local script that plays
    the misbehaving server, no real MCP server needed.
Only "cut a real in-flight NVIDIA API call" and "revoke a key that was
previously live" need your actual account — flagged below.

Run:  python3 docs/failure_injection_harness.py
"""
import json
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FAKE_GARBAGE_SERVER = textwrap.dedent("""
    import sys, time
    print("DEBUG: server booting, this is not JSON-RPC", flush=True)
    print("{not: valid, json", flush=True)
    time.sleep(0.2)
    print("another garbage line", flush=True)
    sys.stdin.readline()
    time.sleep(2)
""")

FAKE_ERROR_SERVER = textwrap.dedent("""
    import json, sys
    line = sys.stdin.readline()
    try:
        rpc_id = json.loads(line).get("id")
    except Exception:
        rpc_id = 1
    resp = {"jsonrpc": "2.0", "id": rpc_id,
            "error": {"code": -32000, "message": "simulated server-side failure"}}
    print(json.dumps(resp), flush=True)
    sys.stdin.readline()
""")

FAKE_WEDGED_SERVER = textwrap.dedent("""
    import sys, time
    sys.stdin.readline()
    time.sleep(120)
""")


def run(cmd, timeout):
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr, time.monotonic() - start
    except subprocess.TimeoutExpired:
        return 124, "", "harness timeout — process did not exit", time.monotonic() - start


def test_nvidia_unreachable():
    name = "nvidia-unreachable"
    import os
    # dummy key: the key-presence check runs before the network call, and this
    # test is about the network failure path, not the missing-key path
    env = {**os.environ, "HERMES_NVIDIA_URL": "http://localhost:19999",
           "NVIDIA_API_KEY": "nvapi-harness-dummy"}
    start = time.monotonic()
    proc = subprocess.run([sys.executable, "nvidia_client.py", "chat", "hello", "--model", "x"],
                          cwd=ROOT, capture_output=True, text=True, timeout=20, env=env)
    elapsed = time.monotonic() - start
    ok = (proc.returncode != 0 and "unreachable" in proc.stderr.lower()
          and "do not silently retry" in proc.stderr.lower())
    return name, ok, f"rc={proc.returncode} elapsed={elapsed:.1f}s stderr={proc.stderr.strip()[:150]!r}"


def test_tavily_invalid_key():
    name = "tavily-invalid-key"
    import os
    env = {**os.environ, "TAVILY_API_KEY": "tvly-INVALID-000", "FIRECRAWL_API_KEY": ""}
    proc = subprocess.run([sys.executable, "fetcher/fetch.py", "search", "test"],
                          cwd=ROOT, capture_output=True, text=True, timeout=20, env=env)
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return name, False, f"non-JSON stdout: {proc.stdout[:150]!r}"
    key_leaked = "tvly-INVALID-000" in proc.stdout
    got_401 = "401" in result.get("attempts", {}).get("tavily", "")
    exit_code_signals_failure = proc.returncode != 0
    ok = got_401 and not key_leaked
    note = f"rc={proc.returncode} 401_detected={got_401} key_leaked={key_leaked}"
    if not exit_code_signals_failure:
        note += " | FINDING: exit code 0 on a fully-failed search (no results, no backend) — fetch.py's own 'fetch' subcommand exits 1 on failure, 'search' does not. Inconsistent; a caller scripting on exit code alone would miss this."
    return name, ok, note


def test_mcp_dangerous_command_blocked():
    name = "mcp-dangerous-command-blocked"
    proc = subprocess.run([sys.executable, "connect/mcp_client.py", "tools", "--", "rm", "-rf", "/"],
                          cwd=ROOT, capture_output=True, text=True, timeout=10)
    clean_message = proc.stderr.strip().startswith("mcp_client.py:") and "Traceback" not in proc.stderr
    ok = proc.returncode != 0 and "BLOCKED" in proc.stderr and clean_message
    return name, ok, f"rc={proc.returncode} blocked={'BLOCKED' in proc.stderr} clean_message={clean_message}"


def test_mcp_garbage_response():
    name = "mcp-garbage-response"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(FAKE_GARBAGE_SERVER)
        path = f.name
    try:
        proc = subprocess.run([sys.executable, "connect/mcp_client.py", "tools", "--",
                              sys.executable, path],
                              cwd=ROOT, capture_output=True, text=True, timeout=15)
        ok = proc.returncode != 0 and ("ConnectionError" in proc.stderr or "closed stdout" in proc.stderr)
        return name, ok, f"rc={proc.returncode} stderr_tail={proc.stderr.strip()[-150:]!r}"
    finally:
        Path(path).unlink(missing_ok=True)


def test_mcp_jsonrpc_error():
    name = "mcp-jsonrpc-error-response"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(FAKE_ERROR_SERVER)
        path = f.name
    try:
        proc = subprocess.run([sys.executable, "connect/mcp_client.py", "tools", "--",
                              sys.executable, path],
                              cwd=ROOT, capture_output=True, text=True, timeout=15)
        ok = proc.returncode != 0 and "simulated server-side failure" in proc.stderr
        return name, ok, f"rc={proc.returncode} propagated_server_error={'simulated server-side failure' in proc.stderr}"
    finally:
        Path(path).unlink(missing_ok=True)


def test_mcp_wedged_timeout():
    name = "mcp-wedged-server-timeout"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(FAKE_WEDGED_SERVER)
        path = f.name
    try:
        start = time.monotonic()
        proc = subprocess.run([sys.executable, "connect/mcp_client.py", "tools", "--",
                              sys.executable, path],
                              cwd=ROOT, capture_output=True, text=True, timeout=45)
        elapsed = time.monotonic() - start
        ok = (proc.returncode != 0 and "no response for id=" in proc.stderr
              and "Traceback" not in proc.stderr and 25 < elapsed < 40)
        return name, ok, f"rc={proc.returncode} elapsed={elapsed:.1f}s (watchdog should fire ~30s) clean_message={'Traceback' not in proc.stderr}"
    finally:
        Path(path).unlink(missing_ok=True)


def main():
    tests = [
        test_nvidia_unreachable,
        test_tavily_invalid_key,
        test_mcp_dangerous_command_blocked,
        test_mcp_garbage_response,
        test_mcp_jsonrpc_error,
        test_mcp_wedged_timeout,
    ]
    print("\n=== Failure-injection harness (Gate 4 follow-up) ===")
    any_fail = False
    for t in tests:
        name, ok, note = t()
        marker = "PASS" if ok else "FAIL"
        if not ok:
            any_fail = True
        print(f"[{marker}] {name}: {note}")

    print("\nNOT covered by this script — needs your real machine/account, not manufacturable locally:")
    print("  - cutting a real in-flight NVIDIA API call (vs. unreachable-from-the-start, tested here)")
    print("  - a Tavily key that was genuinely live and got revoked (vs. never-valid, tested here — "
          "same 401 path, but if Tavily ever changes revoked-key response shape this wouldn't catch it)")
    print("  - whether Apollo (SKILL.md, read by a real Claude session) actually obeys 'never silently "
          "substitute tiers' under real pressure — that instruction is prompt-level, not code-enforced, "
          "and this script can't test LLM behavior")
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
