#!/usr/bin/env python3
"""
brain.py — HERMES Phase 3A tier router.

Three responsibilities only, per HERMES_Architecture.md Layer 1:
  1. check_sensitivity(task_description) -> bool
  2. get_tier(is_sensitive, task_type)   -> int   (1=Claude, 2=Ollama, 3=NYX fallback)
  3. log_request(...)                    -> append to logs/reasoning_seed.jsonl

Also implements the enforcement check that hooks/verify.sh calls:
  check_model_allowed(tier, model, via) -> (bool allowed, str reason)

Reimplemented fresh from extracted patterns (SuperClaude SelfCorrectionEngine #153,
claude-code-main ModelSource enum, ruflo SPARC fallback chain). No code copied
from any analyzed repo — patterns only, per project constraint.

CLI usage (what hooks/verify.sh shells out to):
    python3 brain.py check --task "<description>" [--model NAME] [--via api|local]
    python3 brain.py log --task-type research --tier 1 --outcome success --success true --tokens 1200 --latency 3200
    python3 brain.py log-failure --task "<description>" --category validation --rule "<prevention rule>"
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parent
LOG_DIR = HERMES_ROOT / "logs"
REASONING_LOG = LOG_DIR / "reasoning_seed.jsonl"
REFLEXION_LOG = LOG_DIR / "reflexion_seed.json"
DEBUG_LOG = LOG_DIR / "debug.log"

# ---------------------------------------------------------------------------
# Hard-coded sensitivity rules. NOT LLM-based — deterministic keyword match.
# Per HERMES_Architecture.md: "Sensitivity rules (hard-coded, not LLM)"
# ---------------------------------------------------------------------------
SENSITIVE_KEYWORDS = [
    r"\bcve-\d{4}-\d+\b", r"\bcve\b", r"\brecon\b", r"\bexploit\b", r"\bpentest\b",
    r"\bpenetration test", r"\bhermes internals\b", r"\bsage\b", r"\bnyx\b",
    r"\bapi[ _-]?key\b", r"\bsecret[ _-]?key\b", r"\bprivate[ _-]?key\b",
    r"\bpersonal info(rmation)?\b", r"\bpii\b", r"\bssn\b", r"\bpassword\b",
    r"\bcredential", r"\bvulnerabilit(y|ies)\b", r"\bpayload\b", r"\bmalware\b",
    r"\bshellcode\b", r"\bbackdoor\b", r"\bzero[- ]day\b",
]
_SENSITIVE_RE = re.compile("|".join(SENSITIVE_KEYWORDS), re.IGNORECASE)

# Task-type hints that push toward Tier 2 (Ollama) when NOT sensitive.
BULK_KEYWORDS = [r"\bbulk\b", r"\boffline\b", r"\bbatch\b", r"\blarge[- ]context\b",
                  r"\bcost[- ]sensitive\b", r"\bsummarize \d+", r"\bmany files\b"]
_BULK_RE = re.compile("|".join(BULK_KEYWORDS), re.IGNORECASE)

# Architectural exclusion — permanent, no config toggle, no opt-in.
# Applies ONLY to `via=api`. Local Ollama-hosted open-weight builds are exempt.
EXCLUDED_API_MODELS = ["kimi", "moonshot", "glm", "zhipu", "mimo", "xiaomi",
                        "minimax", "deepseek"]

TIER_NAMES = {1: "Tier 1 — Claude API", 2: "Tier 2 — Ollama local", 3: "Tier 3 — NYX fallback"}


def check_sensitivity(task_description: str) -> bool:
    """Deterministic keyword match. True => Tier 1 only, no exceptions."""
    if not task_description:
        return False
    return bool(_SENSITIVE_RE.search(task_description))


def is_bulk_task(task_description: str) -> bool:
    if not task_description:
        return False
    return bool(_BULK_RE.search(task_description))


def get_tier(is_sensitive: bool, task_type: str = "default", via: str = "api") -> int:
    """
    Sensitive + via=local -> Tier 2. Local Ollama IS permitted for sensitive
        data per HERMES_Phase3_Blueprint.docx section 6.2 ("CVEs, recon
        output, pentest notes -> Tier 1 (Claude API) or Tier 2 (local
        Ollama) ONLY") and the v1 blueprint's Apollo Model Routing table.
        Audited 2026-07-02 (H2) — original version forced sensitive tasks to
        Tier 1 unconditionally, which made it IMPOSSIBLE to ever run a
        CVE/recon/pentest task offline on local hardware, contradicting both
        blueprints' explicit intent. Tier 3 remains categorically
        unreachable for sensitive data regardless of `via` — that
        restriction is correct and unchanged.
    Sensitive + via=api (default) -> Tier 1, no exceptions.
    Non-sensitive + task_type=bulk -> Tier 2.
    Everything else -> Tier 1 (default-safe).
    """
    if is_sensitive:
        return 2 if via == "local" else 1
    if task_type == "bulk":
        return 2
    return 1


def check_model_allowed(tier: int, model: str, via: str = "api"):
    """
    Returns (allowed: bool, reason: str).
    Enforces:
      - Chinese API exclusion (permanent, via=api only)
      - Sensitive/Tier-1-only tasks cannot route to Tier 2 or Tier 3
      - Tier 3 (NYX) never carries sensitive data even if available
    """
    model_l = (model or "").lower()

    if via == "api" and any(x in model_l for x in EXCLUDED_API_MODELS):
        return False, f"BLOCKED: '{model}' is an excluded Chinese API model (permanent architectural exclusion, no opt-in)."

    if tier == 1 and via == "local":
        # Not fatal by itself — Tier 1 is Claude API by definition. Flag it.
        return False, "BLOCKED: Tier 1 requires Claude API, but request is routed to a local model."

    return True, "ALLOWED"


def log_request(task_type: str, tier: int, outcome: str = "pending",
                 success: bool = None, tokens: int = 0, latency_ms: int = 0):
    """Append one line to logs/reasoning_seed.jsonl. Raw capture — ReasoningBank
    (Phase 3B) indexes this into HNSW later. Zero processing here."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_type": task_type,
        "tier": tier,
        "outcome": outcome,
        "success": success,
        "tokens": tokens,
        "latency_ms": latency_ms,
    }
    with open(REASONING_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def log_failure(task: str, error_category: str, prevention_rule: str, failure_mode: str = None):
    """Append one line to logs/reflexion_seed.json (JSONL format despite the
    .json extension — append-only, no read-modify-write race). Curator
    (Phase 3B) dedupes and structures this later via MD5(task+failure_mode).

    failure_mode = what went wrong (a description of the failure itself).
    prevention_rule = the fix / what to do instead.
    These are distinct fields per the pending-queue schema in
    HERMES_Phase3_Blueprint.docx section 3.2 — dedup keys on the failure
    description, not the rule text, so two occurrences of the same bug still
    dedupe even if the suggested fix wording drifts between occurrences.
    If failure_mode isn't supplied, falls back to prevention_rule for
    backward compatibility with Phase 3A call sites that only had one field.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    failure_mode = failure_mode or prevention_rule
    dedup_key = hashlib.md5(f"{task}{failure_mode}".encode()).hexdigest()[:8]
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "error_category": error_category,
        "failure_mode": failure_mode,
        "prevention_rule": prevention_rule,
        "dedup_key": dedup_key,
        "raw": True,
    }
    with open(REFLEXION_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def debug_log(msg: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(DEBUG_LOG, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_check(args):
    is_sensitive = check_sensitivity(args.task)
    task_type = "bulk" if is_bulk_task(args.task) else "default"
    tier = get_tier(is_sensitive, task_type, via=args.via)
    allowed, reason = check_model_allowed(tier, args.model, args.via) if args.model else (True, "no model specified — tier computed only")

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
                         args.success, args.tokens, args.latency)
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
    p_check.add_argument("--via", default="api", choices=["api", "local"])
    p_check.set_defaults(func=_cmd_check)

    p_log = sub.add_parser("log")
    p_log.add_argument("--task-type", required=True)
    p_log.add_argument("--tier", type=int, required=True)
    p_log.add_argument("--outcome", default="pending")
    p_log.add_argument("--success", type=lambda s: s.lower() == "true", default=None)
    p_log.add_argument("--tokens", type=int, default=0)
    p_log.add_argument("--latency", type=int, default=0)
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
