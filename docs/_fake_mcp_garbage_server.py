#!/usr/bin/env python3
"""Fake MCP server for failure-injection testing: spews non-JSON garbage
then a garbled line, never sends a valid JSON-RPC initialize response.
Used by docs/failure_injection_harness.py — not a real server, temp fixture."""
import sys
import time

print("DEBUG: server booting, this is not JSON-RPC", flush=True)
print("{not: valid, json", flush=True)
time.sleep(0.2)
print("another garbage line", flush=True)
sys.stdin.readline()  # consume the client's initialize request without answering it
time.sleep(2)
