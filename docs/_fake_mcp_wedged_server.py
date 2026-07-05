#!/usr/bin/env python3
"""Fake MCP server for failure-injection testing: accepts the connection,
reads the initialize request, and then never responds at all — simulates a
wedged/hung server. Used by docs/failure_injection_harness.py to prove the
30s response watchdog in connect/mcp_client.py actually fires."""
import sys
import time

sys.stdin.readline()  # read initialize, say nothing back
time.sleep(120)
