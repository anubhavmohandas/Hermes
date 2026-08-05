#!/usr/bin/env python3
"""
integrations/composio.py — Composio connectors (Stage 5, opt-in, sandboxed).

Pattern source (reimplemented fresh, no code copied): the v1 blueprint's
"Composio connectors (sandboxed, permission-per-connector)". Note the
reconciliation (HERMES_GOAL_Start_to_End.md §1): Phase 3 supersedes v1 here —
native MCP (Connect) is the primary connector path; Composio is DEFERRED
breadth. So this module is a thin, honest registry + permission gate, not a
re-implementation of Composio's 500+ integrations.

The load-bearing part is the permission model, per the blueprint's
"permission-per-connector": every connector is DENY by default. Enabling one
is an explicit, recorded human action (`enable`), and each enabled connector
still routes its actual calls through Connect's MCP client + the security
gate — Composio here only tracks *which* connectors the human has allowed,
never bypasses approval, never stores a live credential.

Fallback (Invariant #5): with no Composio API key, this is a local registry
only — it plans and gates, it does not reach Composio's cloud. That's the
whole point: the permission ledger works offline; the network integration is
the opt-in part.

CLI:
    python3 integrations/composio.py list
    python3 integrations/composio.py enable <connector>
    python3 integrations/composio.py disable <connector>
    python3 integrations/composio.py status
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meta.paths import state_file  # noqa: E402

# Connected-account registry is per-user runtime state (meta/paths.py).
REGISTRY_PATH = state_file("integrations", "composio_registry.json")

# Connector catalog is illustrative — the shape (deny-by-default, per-connector
# scopes) is the pattern, not an exhaustive Composio mirror.
KNOWN_CONNECTORS = {
    "github": ["repo:read", "issues:write"],
    "slack": ["chat:write"],
    "notion": ["pages:read", "pages:write"],
    "gmail": ["mail:read"],
    "linear": ["issues:read", "issues:write"],
}


def _load():
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {"enabled": {}}


def _save(reg):
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")


def enable(connector: str):
    if connector not in KNOWN_CONNECTORS:
        return {"enabled": False, "reason": f"unknown connector '{connector}'",
                "known": sorted(KNOWN_CONNECTORS)}
    reg = _load()
    reg["enabled"][connector] = {
        "scopes": KNOWN_CONNECTORS[connector],
        "enabled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "transport": "via Connect MCP client + security gate (never bypassed)",
    }
    _save(reg)
    return {"enabled": True, "connector": connector,
            "scopes": KNOWN_CONNECTORS[connector],
            "note": "human-enabled; calls still route through approval + Connect"}


def disable(connector: str):
    reg = _load()
    existed = reg["enabled"].pop(connector, None) is not None
    _save(reg)
    return {"disabled": existed, "connector": connector}


def list_connectors():
    reg = _load()
    return {name: {"enabled": name in reg["enabled"], "scopes": scopes}
            for name, scopes in sorted(KNOWN_CONNECTORS.items())}


def status():
    reg = _load()
    return {
        "default_policy": "deny — every connector off until explicitly enabled",
        "cloud_available": bool(os.environ.get("COMPOSIO_API_KEY")),
        "enabled_count": len(reg["enabled"]),
        "enabled": sorted(reg["enabled"]),
        "note": "offline permission ledger; cloud integration is the opt-in part; "
                "Connect (native MCP) is the primary connector path per Phase 3",
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "list":
        print(json.dumps(list_connectors(), indent=2))
    elif len(args) >= 2 and args[0] == "enable":
        print(json.dumps(enable(args[1]), indent=2))
    elif len(args) >= 2 and args[0] == "disable":
        print(json.dumps(disable(args[1]), indent=2))
    elif args and args[0] == "status":
        print(json.dumps(status(), indent=2))
    else:
        print("usage: composio.py list | enable <c> | disable <c> | status", file=sys.stderr)
        sys.exit(2)
