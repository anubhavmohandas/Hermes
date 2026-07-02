#!/usr/bin/env python3
"""
reasoningbank/bank.py — ReasoningBank: reward-scored task memory.

Pattern source (reimplemented fresh, no code copied): ruflo SPARC
ReasoningBank (Pattern #80) + HNSW params (Pattern #81, M=16,
efConstruction=200, cosine, pre-normalized — same params as Mnemos v2,
reuses mnemos/hnsw_index.py's MnemosHNSW wrapper rather than duplicating it).

Deliberately separate from brain.py's log_request(). brain.py's job (Phase
3A) is the raw {task_type, tier, tokens, latency} capture used for Clio's
token accounting — it stays minimal by design. ReasoningBank's job (Phase
3B) is the richer {approach, reward, critique} schema used for retrieval-
augmented context injection before a NEW task starts. Different consumers,
different lifecycles — conflating them would make brain.py's "three
responsibilities only" scope claim false.

Before each new task: retrieve_top_k() returns the best-scoring past
approaches for a similar task, meant to be injected as context BEFORE
execution — not after-the-fact analysis like Curator's mistake capture.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mnemos"))
from hnsw_index import MnemosHNSW

BANK_DIR = Path(__file__).resolve().parent
RAW_LOG = BANK_DIR / "task_log.jsonl"
INDEX_DIR = BANK_DIR / "hnsw"

REWARD_INJECTION_THRESHOLD = 0.8


def log_task(task_description: str, approach: str, outcome: str, reward: float,
             success: bool, critique: str = "", tokens_used: int = 0, latency_ms: int = 0):
    """Appends raw record + inserts into the HNSW index in one call. Both are
    durable — the JSONL is the audit trail, the HNSW index is the retrieval
    structure (rebuildable FROM the JSONL if the index ever needs a redo)."""
    if not (0.0 <= reward <= 1.0):
        raise ValueError(f"reward must be in [0.0, 1.0], got {reward}")

    BANK_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task_description": task_description,
        "approach": approach,
        "outcome": outcome,
        "reward": reward,
        "success": success,
        "critique": critique,
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
    }
    with open(RAW_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

    bank = MnemosHNSW(INDEX_DIR)
    label = bank.insert(task_description, metadata=entry)
    bank.save()
    entry["hnsw_label"] = label
    return entry


def retrieve_top_k(task_description: str, k: int = 5, min_reward: float = REWARD_INJECTION_THRESHOLD):
    """Retrieve the best-scoring past approaches for a task similar to
    task_description. Only returns entries with reward > min_reward — this
    is the 'don't inject mediocre past attempts as if they were good
    examples' guardrail from the pattern spec."""
    if not (INDEX_DIR / "hnsw.bin").exists():
        return []
    bank = MnemosHNSW(INDEX_DIR)
    # over-fetch then filter by reward, since HNSW ranks by similarity only
    candidates = bank.query(task_description, k=max(k * 3, k))
    filtered = [c for c in candidates if c["metadata"].get("reward", 0) > min_reward]
    filtered.sort(key=lambda c: (c["metadata"]["reward"], c["similarity"]), reverse=True)
    return filtered[:k]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: bank.py log <task> <approach> <outcome> <reward> <success:true|false> [critique] [tokens] [latency]", file=sys.stderr)
        print("       bank.py retrieve <task> [k] [min_reward]", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "log":
        entry = log_task(
            task_description=sys.argv[2], approach=sys.argv[3], outcome=sys.argv[4],
            reward=float(sys.argv[5]), success=(sys.argv[6].lower() == "true"),
            critique=sys.argv[7] if len(sys.argv) > 7 else "",
            tokens_used=int(sys.argv[8]) if len(sys.argv) > 8 else 0,
            latency_ms=int(sys.argv[9]) if len(sys.argv) > 9 else 0,
        )
        print(json.dumps(entry))
    elif cmd == "retrieve":
        k = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        min_reward = float(sys.argv[4]) if len(sys.argv) > 4 else REWARD_INJECTION_THRESHOLD
        results = retrieve_top_k(sys.argv[2], k=k, min_reward=min_reward)
        print(json.dumps(results, indent=2))
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)
