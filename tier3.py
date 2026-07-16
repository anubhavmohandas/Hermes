#!/usr/bin/env python3
"""
tier3.py — Tier 3 (NYX fallback) routing guard (Phase 3D).

Pattern source (reimplemented fresh, no code copied): ruflo SPARC fallback
chain + brain.py's own tier discipline. Per HERMES_GOAL_Start_to_End.md
Stage 4 item 4: fallback chain Mistral → Gemini → GPT-4o, EU/US jurisdiction
check, and a SECOND sensitivity check before any Tier 3 route.

Tier 3 exists for exactly one situation: Tier 1 (Claude API) and Tier 2
(NVIDIA API) are BOTH unavailable and the task is NOT sensitive. It is an
availability fallback, never a preference, never a cost optimization.

Defense in depth, in order, all mandatory:
  1. SECOND sensitivity check — brain.check_sensitivity is re-run here even
     though Apollo already ran it at intake. Two independent call sites must
     both be wrong for sensitive data to reach a Tier 3 model. Sensitive =>
     refuse, with no override parameter in the signature (an override that
     exists will eventually be used).
  2. Chinese-API exclusion — brain.check_model_allowed runs against every
     candidate; the fallback chain is also statically free of excluded
     models, so this is belt over braces.
  3. Jurisdiction check — only models operated under EU/US jurisdiction are
     eligible. Unknown jurisdiction = ineligible (fail closed), not "assume
     fine".

This module SELECTS; it does not dispatch. The caller gets back which model
to use (or a refusal) — actually invoking it is Apollo's job, and the
selection JSON is written into the debug log for audit.

CLI:
    python3 tier3.py route --task "<description>"
    python3 tier3.py chain
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brain  # noqa: E402

# Fallback chain in preference order. Jurisdiction is the OPERATOR's, per the
# blueprint's EU/US constraint. Adding a model here requires a jurisdiction
# entry — route() fails closed on models it can't place.
TIER3_CHAIN = [
    {"model": "mistral-large", "operator": "Mistral AI", "jurisdiction": "EU"},
    {"model": "gemini-2.5-pro", "operator": "Google", "jurisdiction": "US"},
    {"model": "gpt-4o", "operator": "OpenAI", "jurisdiction": "US"},
]

ALLOWED_JURISDICTIONS = ("EU", "US")


def route(task_description: str, available=None):
    """Returns a dict: either {"routed": True, "model": ...} or
    {"routed": False, "reason": ...}. `available` optionally narrows the
    chain to models the caller can actually reach (None = assume all)."""
    # 1. SECOND sensitivity check — independent of Apollo's intake check.
    if brain.check_sensitivity(task_description):
        result = {"routed": False,
                  "reason": "REFUSED: task matched sensitivity rules on the second "
                            "(pre-Tier-3) check — sensitive data never routes to "
                            "Tier 3, regardless of Tier 1/2 availability"}
        brain.debug_log(f"tier3 route REFUSED (sensitive): {task_description[:120]}")
        return result

    for candidate in TIER3_CHAIN:
        model = candidate["model"]
        if available is not None and model not in available:
            continue
        # 2. Chinese-API exclusion, same enforcement path as every tier.
        allowed, reason = brain.check_model_allowed(3, model)
        if not allowed:
            continue
        # 3. Jurisdiction — fail closed on anything not explicitly EU/US.
        if candidate.get("jurisdiction") not in ALLOWED_JURISDICTIONS:
            continue
        result = {"routed": True, "model": model,
                  "operator": candidate["operator"],
                  "jurisdiction": candidate["jurisdiction"],
                  "note": "Tier 3 is an availability fallback — log tokens to "
                          "brain.py as tier 3 so Clio attributes the cost"}
        brain.debug_log(f"tier3 route -> {model} ({candidate['jurisdiction']}) "
                        f"for: {task_description[:120]}")
        return result

    result = {"routed": False,
              "reason": "no Tier 3 candidate passed exclusion + jurisdiction checks"}
    brain.debug_log(f"tier3 route EXHAUSTED for: {task_description[:120]}")
    return result


def main():
    parser = argparse.ArgumentParser(prog="tier3.py")
    sub = parser.add_subparsers(dest="command", required=True)
    p_route = sub.add_parser("route")
    p_route.add_argument("--task", required=True)
    sub.add_parser("chain")
    args = parser.parse_args()
    if args.command == "route":
        result = route(args.task)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["routed"] else 1)
    elif args.command == "chain":
        print(json.dumps({"chain": TIER3_CHAIN,
                          "allowed_jurisdictions": list(ALLOWED_JURISDICTIONS)}, indent=2))


if __name__ == "__main__":
    main()
