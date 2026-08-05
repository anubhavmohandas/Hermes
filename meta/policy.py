#!/usr/bin/env python3
"""
meta/policy.py — HERMES shared tier/sensitivity policy (the leaf both the
orchestrator and its subsystems depend on).

Extracted from brain.py on 2026-07-05 (V1_CHECKLIST §1) to remove the only two
inverted imports: `integrations/notebooklm.py` and `meta/security/audit.py` were
reaching UP into the root orchestrator (`brain.py`) for policy calls. The policy
itself — sensitivity rules, tier routing, model exclusion, and the request/failure
logs — has no dependency on the orchestrator, so it belongs in a leaf module both
sides import downward. `brain.py` now re-exports every name here, so existing
callers (`nvidia_client.py`, `tier3.py`, the CLI, tests) keep using `brain.<fn>`
unchanged.

Three policy responsibilities, per HERMES_Architecture.md Layer 1:
  1. check_sensitivity(task_description) -> bool
  2. get_tier(is_sensitive, task_type)   -> int   (1=Claude, 2=NVIDIA API, 3=NYX fallback)
  3. log_request(...)                    -> append to logs/reasoning_seed.jsonl

Plus the enforcement check hooks/verify.sh calls (via brain.py):
  check_model_allowed(tier, model) -> (bool allowed, str reason)

Reimplemented fresh from extracted patterns (SuperClaude SelfCorrectionEngine #153,
claude-code-main ModelSource enum, ruflo SPARC fallback chain). No code copied
from any analyzed repo — patterns only, per project constraint.
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# policy.py lives in meta/, so repo root is two levels up (parent=meta, then root).
HERMES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERMES_ROOT))
from meta.paths import state_file  # noqa: E402

# Logs are runtime state, not source: they resolve under ~/.claude/hermes/ so
# a plugin update can't delete them (see meta/paths.py). Migrated per-file on
# first use, so a dev checkout's tracked logs/.gitkeep stays where it is.
REASONING_LOG = state_file("logs", "reasoning_seed.jsonl")
REFLEXION_LOG = state_file("logs", "reflexion_seed.json")
DEBUG_LOG = state_file("logs", "debug.log")
LOG_DIR = REASONING_LOG.parent

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

# Task-type hints that push toward Tier 2 (NVIDIA API) when NOT sensitive.
BULK_KEYWORDS = [r"\bbulk\b", r"\boffline\b", r"\bbatch\b", r"\blarge[- ]context\b",
                  r"\bcost[- ]sensitive\b", r"\bsummarize \d+", r"\bmany files\b"]
_BULK_RE = re.compile("|".join(BULK_KEYWORDS), re.IGNORECASE)

# Architectural exclusion — permanent, no config toggle, no opt-in. Every tier
# is a remote API now (the local-Ollama exemption died with the local tier),
# so the exclusion applies unconditionally.
EXCLUDED_API_MODELS = ["kimi", "moonshot", "glm", "zhipu", "mimo", "xiaomi",
                        "minimax", "deepseek"]

TIER_NAMES = {1: "Tier 1 — Claude API", 2: "Tier 2 — NVIDIA API", 3: "Tier 3 — NYX fallback"}


def check_sensitivity(task_description: str) -> bool:
    """Deterministic keyword match. True => Tier 1 only, no exceptions."""
    if not task_description:
        return False
    return bool(_SENSITIVE_RE.search(task_description))


def is_bulk_task(task_description: str) -> bool:
    if not task_description:
        return False
    return bool(_BULK_RE.search(task_description))


def get_tier(is_sensitive: bool, task_type: str = "default") -> int:
    """
    Sensitive -> Tier 1, no exceptions. The old sensitive->Tier-2 path (H2,
        audited 2026-07-02) existed ONLY because Tier 2 was local Ollama and
        data never left the machine. Tier 2 is now the NVIDIA cloud API —
        sensitive data (CVEs, recon output, pentest notes) routes to Tier 1
        (Claude API) only. Tier 3 remains categorically unreachable for
        sensitive data — unchanged.
    Non-sensitive + task_type=bulk -> Tier 2 (NVIDIA API).
    Everything else -> Tier 1 (default-safe).
    """
    if is_sensitive:
        return 1
    if task_type == "bulk":
        return 2
    return 1


def check_model_allowed(tier: int, model: str):
    """
    Returns (allowed: bool, reason: str).
    Enforces the Chinese API exclusion (permanent, all tiers — every tier is
    a remote API now). Sensitive data never reaches Tier 2/3 via get_tier().
    """
    model_l = (model or "").lower()

    if any(x in model_l for x in EXCLUDED_API_MODELS):
        return False, f"BLOCKED: '{model}' is an excluded Chinese API model (permanent architectural exclusion, no opt-in)."

    return True, "ALLOWED"


def log_request(task_type: str, tier: int, outcome: str = "pending",
                 success: bool = None, tokens: int = 0, latency_ms: int = 0,
                 model: str = None, decision: str = None):
    """Append one line to logs/reasoning_seed.jsonl. Raw capture — ReasoningBank
    (Phase 3B) indexes this into HNSW later. Zero processing here.

    Execution-trace fields (V1_CHECKLIST §3): the line answers *what decision*
    (`decision`, e.g. 'sensitive->Tier1'), *which tier* (`tier`), *which model*
    (`model`), and *how long* (`latency_ms`). `model`/`decision` are optional
    and default to None so pre-§3 call sites and their tests are unaffected —
    the schema stays a fixed set of keys, which is what makes it a stable trace
    for Clio to aggregate over."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_type": task_type,
        "tier": tier,
        "model": model,
        "decision": decision,
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
    # non-security digest — dedup identifier only (usedforsecurity=False keeps
    # the value identical while satisfying scanners/FIPS; audit L4)
    dedup_key = hashlib.md5(f"{task}{failure_mode}".encode(), usedforsecurity=False).hexdigest()[:8]
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
