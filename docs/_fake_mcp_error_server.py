#!/usr/bin/env python3
"""Fake MCP server for failure-injection testing: reads the initialize
request and replies with a valid JSON-RPC *error* object instead of a
result. Used by docs/failure_injection_harness.py — not a real server."""
import json
import sys

line = sys.stdin.readline()
try:
    req = json.loads(line)
    rpc_id = req.get("id")
except Exception:
    rpc_id = 1

resp = {"jsonrpc": "2.0", "id": rpc_id,
        "error": {"code": -32000, "message": "simulated server-side failure"}}
print(json.dumps(resp), flush=True)
sys.stdin.readline()
