#!/usr/bin/env python3
"""
brain.py — HERMES Phase 3A tier router (CLI entry + policy facade).

The routing *policy* itself — sensitivity rules, tier selection, model
exclusion, and the request/failure logs — lives in `meta/policy.py`, a leaf
module with no dependency on this orchestrator. It was extracted there on
2026-07-05 (V1_CHECKLIST §1) so that subsystems needing a policy call
(`integrations/notebooklm.py`, `meta/security/audit.py`) import *downward*
from the leaf instead of reaching *up* into this orchestrator.

brain.py keeps two jobs:
  1. Re-export every policy name (below), so existing callers keep using
     `brain.check_sensitivity`, `brain.get_tier`, `brain.log_request`, etc.
     unchanged — the extraction is invisible to them.
  2. Provide the CLI that hooks/verify.sh shells out to.

Three policy responsibilities, per HERMES_Architecture.md Layer 1 (defined in
meta/policy.py):
  1. check_sensitivity(task_description) -> bool
  2. get_tier(is_sensitive, task_type)   -> int   (1=Claude, 2=NVIDIA API, 3=NYX fallback)
  3. log_request(...)                    -> append to logs/reasoning_seed.jsonl

Also the enforcement check hooks/verify.sh calls:
  check_model_allowed(tier, model) -> (bool allowed, str reason)

Reimplemented fresh from extracted patterns (SuperClaude SelfCorrectionEngine #153,
claude-code-main ModelSource enum, ruflo SPARC fallback chain). No code copied
from any analyzed repo — patterns only, per project constraint.

CLI usage (what hooks/verify.sh shells out to):
    python3 brain.py check --task "<description>" [--model NAME]
    python3 brain.py log --task-type research --tier 1 --outcome success --success true --tokens 1200 --latency 3200
    python3 brain.py log-failure --task "<description>" --category validation --rule "<prevention rule>"
"""

import argparse
import json
import sys
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(HERMES_ROOT))

# Policy core lives in the leaf module; re-exported here so callers that import
# `brain` (nvidia_client.py, tier3.py, the CLI below, tests) don't churn.
from meta.policy import (  # noqa: E402
    HERMES_ROOT as POLICY_ROOT,  # noqa: F401  (same value; kept for parity)
    LOG_DIR,  # noqa: F401
    REASONING_LOG,  # noqa: F401
    REFLEXION_LOG,  # noqa: F401
    DEBUG_LOG,  # noqa: F401
    SENSITIVE_KEYWORDS,  # noqa: F401
    BULK_KEYWORDS,  # noqa: F401
    EXCLUDED_API_MODELS,  # noqa: F401
    TIER_NAMES,
    check_sensitivity,
    is_bulk_task,
    get_tier,
    check_model_allowed,
    log_request,
    log_failure,
    debug_log,
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_check(args):
    is_sensitive = check_sensitivity(args.task)
    task_type = "bulk" if is_bulk_task(args.task) else "default"
    tier = get_tier(is_sensitive, task_type)
    allowed, reason = check_model_allowed(tier, args.model) if args.model else (True, "no model specified — tier computed only")

    result = {
        "sensitive": is_sensitive,
        "task_type": task_type,
        "tier": tier,
        "tier_name": TIER_NAMES[tier],
        "model": args.model,
        "allowed": allowed,
        "reason": reason,
    }
    print(json.dumps(result))
    debug_log(f"check task_type={task_type} sensitive={is_sensitive} tier={tier} model={args.model} allowed={allowed}")
    if not allowed:
        log_failure(args.task or "", "validation", reason)
        sys.exit(1)
    sys.exit(0)


def _cmd_log(args):
    entry = log_request(args.task_type, args.tier, args.outcome,
                         args.success, args.tokens, args.latency,
                         model=args.model, decision=args.decision)
    print(json.dumps(entry))
    sys.exit(0)


def _cmd_log_failure(args):
    entry = log_failure(args.task, args.category, args.rule, args.failure_mode)
    print(json.dumps(entry))
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(prog="brain.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check")
    p_check.add_argument("--task", required=True)
    p_check.add_argument("--model", default=None)
    p_check.set_defaults(func=_cmd_check)

    p_log = sub.add_parser("log")
    p_log.add_argument("--task-type", required=True)
    p_log.add_argument("--tier", type=int, required=True)
    p_log.add_argument("--outcome", default="pending")
    p_log.add_argument("--success", type=lambda s: s.lower() == "true", default=None)
    p_log.add_argument("--tokens", type=int, default=0)
    p_log.add_argument("--latency", type=int, default=0)
    p_log.add_argument("--model", default=None, help="model that served the request (trace field)")
    p_log.add_argument("--decision", default=None,
                       help="one-line routing decision, e.g. 'sensitive->Tier1' (trace field)")
    p_log.set_defaults(func=_cmd_log)

    p_fail = sub.add_parser("log-failure")
    p_fail.add_argument("--task", required=True)
    p_fail.add_argument("--category", required=True,
                         choices=["validation", "dependency", "logic", "assumption", "type", "unknown"])
    p_fail.add_argument("--rule", required=True)
    p_fail.add_argument("--failure-mode", default=None,
                         help="description of what went wrong, distinct from the prevention rule. Defaults to --rule if omitted.")
    p_fail.set_defaults(func=_cmd_log_failure)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
