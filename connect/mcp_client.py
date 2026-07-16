#!/usr/bin/env python3
"""
connect/mcp_client.py — Connect (Phase 3C): native MCP client.

Pattern sources (reimplemented fresh, no code copied): modelcontextprotocol
spec + python-sdk transport shape, tavily-mcp / firecrawl-mcp server
manifests. Per HERMES_GOAL_Start_to_End.md Stage 3 item 4: native MCP
client, X-Agent-Id header, capability negotiation, OAuth PKCE (see
oauth_pkce.py — composed, not embedded).

Transport: stdio (newline-delimited JSON-RPC 2.0), the MCP local-server
standard. The server subprocess command is classified through
meta/security/approval.py before spawn — a connector is a tool surface
like any other and does not bypass the gate (Stage 3 build note: "each new
connector runs through skills_guard + approval like any other surface").

Capability negotiation is enforced, not decorative: tools/list and
tools/call REFUSE to run against a server whose initialize result did not
advertise the `tools` capability, and the negotiated protocolVersion is
recorded in every session record.

Tool RESULTS are untrusted input (same rule as Fetcher): returned as data,
marked `untrusted`, secret-scrubbed before they reach a terminal or log.

CLI:
    python3 connect/mcp_client.py tools -- <server command...>
    python3 connect/mcp_client.py call <tool> '<json-args>' -- <server command...>
    python3 connect/mcp_client.py status
"""
import json
import os
import shlex
import subprocess
import sys
import threading
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT / "meta" / "security"))
import approval  # noqa: E402
import redact    # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "hermes-connect", "version": "1.0"}
AGENT_ID = os.environ.get("HERMES_AGENT_ID", "hermes")
RESPONSE_TIMEOUT_SECONDS = 30


def http_headers() -> dict:
    """Headers for HTTP-transport MCP servers (Streamable HTTP). The
    X-Agent-Id header is the blueprint's provenance marker: every remote
    call is attributable to this agent, not to an anonymous client."""
    return {"X-Agent-Id": AGENT_ID,
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            "Content-Type": "application/json"}


class MCPStdioClient:
    """Minimal, honest MCP client: initialize -> negotiated capabilities ->
    tools/list / tools/call -> close. One server process per client."""

    def __init__(self, server_command):
        if isinstance(server_command, str):
            server_command = shlex.split(server_command)
        self.server_command = server_command
        verdict, reason = approval.classify_command(" ".join(server_command))
        if verdict != "safe":
            raise PermissionError(f"server command refused ({verdict}): {reason}")
        self.proc = None
        self.capabilities = {}
        self.server_info = {}
        self.protocol_version = None
        self._id_lock = threading.Lock()
        self._next_id = 0

    # -- plumbing ----------------------------------------------------------

    def _rpc_id(self):
        with self._id_lock:
            self._next_id += 1
            return self._next_id

    def _send(self, payload: dict):
        line = json.dumps(payload) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def _read_response(self, want_id):
        """Read lines until the response with our id arrives. Server-initiated
        notifications are skipped, not errors. A watchdog kills the read after
        RESPONSE_TIMEOUT_SECONDS — an unattended client must not hang on a
        wedged server (same rule as Cron's hard interrupt)."""
        result = {}

        def reader():
            while True:
                line = self.proc.stdout.readline()
                if not line:
                    result["error"] = "server closed stdout"
                    return
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue  # not a JSON-RPC line (server debug spew) — skip
                if msg.get("id") == want_id:
                    result["msg"] = msg
                    return

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        t.join(RESPONSE_TIMEOUT_SECONDS)
        if t.is_alive():
            raise TimeoutError(f"no response for id={want_id} within "
                               f"{RESPONSE_TIMEOUT_SECONDS}s")
        if "error" in result:
            raise ConnectionError(result["error"])
        msg = result["msg"]
        if "error" in msg:
            raise RuntimeError(f"server error: {json.dumps(msg['error'])}")
        return msg.get("result", {})

    def _request(self, method: str, params: dict = None):
        rpc_id = self._rpc_id()
        payload = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)
        return self._read_response(rpc_id)

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        self.proc = subprocess.Popen(
            self.server_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
        result = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {**CLIENT_INFO, "agentId": AGENT_ID},
        })
        self.capabilities = result.get("capabilities", {})
        self.server_info = result.get("serverInfo", {})
        self.protocol_version = result.get("protocolVersion")
        # spec: client confirms readiness before using the session
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return {"server_info": self.server_info,
                "protocol_version": self.protocol_version,
                "capabilities": self.capabilities}

    def close(self):
        if self.proc:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()

    # -- negotiated surfaces -----------------------------------------------

    def _require_capability(self, cap: str):
        if cap not in self.capabilities:
            raise PermissionError(
                f"server '{self.server_info.get('name', '?')}' did not negotiate "
                f"the '{cap}' capability — refusing the call (negotiation is "
                f"enforcement, not paperwork)")

    def list_tools(self):
        self._require_capability("tools")
        result = self._request("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict):
        self._require_capability("tools")
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        # scrub text content — tool output goes to logs/terminal
        for item in result.get("content", []):
            if item.get("type") == "text":
                item["text"] = redact.redact(item["text"])
        result["untrusted"] = True
        return result


def _split_server_argv(argv):
    if "--" not in argv:
        print("server command goes after '--'", file=sys.stderr)
        sys.exit(2)
    i = argv.index("--")
    return argv[:i], argv[i + 1:]


def main():
    args = sys.argv[1:]
    if args and args[0] == "status":
        print(json.dumps({
            "protocol_version": PROTOCOL_VERSION,
            "agent_id": AGENT_ID,
            "transport": "stdio (newline-delimited JSON-RPC 2.0)",
            "http_headers": http_headers(),
            "response_timeout_seconds": RESPONSE_TIMEOUT_SECONDS,
            "oauth": "PKCE S256 via connect/oauth_pkce.py",
        }, indent=2))
        return

    head, server_cmd = _split_server_argv(args)
    if not head or not server_cmd:
        print("usage: mcp_client.py tools|call <tool> <json-args>|status -- <server cmd>",
              file=sys.stderr)
        sys.exit(2)

    client = None
    try:
        client = MCPStdioClient(server_cmd)
        session = client.start()
        if head[0] == "tools":
            print(json.dumps({"session": session, "tools": client.list_tools()},
                             indent=2))
        elif head[0] == "call":
            tool, raw_args = head[1], (head[2] if len(head) > 2 else "{}")
            result = client.call_tool(tool, json.loads(raw_args))
            print(json.dumps({"session": session, "result": result}, indent=2))
        else:
            print(f"unknown command: {head[0]}", file=sys.stderr)
            sys.exit(2)
    except (PermissionError, ConnectionError, RuntimeError, TimeoutError) as e:
        # same contract as nvidia_client.py's CLI: a clean one-line refusal,
        # not a raw traceback with internal file paths (failure-injection
        # testing, 2026-07-05, found every one of these surfacing as a full
        # traceback — functionally harmless since the exit code was already
        # non-zero and the security-relevant block already happened before
        # this point, but inconsistent UX and a minor info leak)
        print(f"mcp_client.py: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
