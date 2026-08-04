#!/usr/bin/env python3
"""
mnemos/benchmark.py — recall@5 benchmark for Mnemos v2 semantic retrieval.

Phase 3B exit criterion: "Retrieval recall@5 benchmarked." This builds a
small labeled corpus with known relevance judgments and reports the actual
number — including where the hashing-trick embedder (embedder.py) fails,
since that's the honest point of running this at all: know the real recall
before Curator/ReasoningBank start depending on it.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hnsw_index import MnemosHNSW, HNSW_AVAILABLE, HNSW_IMPORT_ERROR

# (doc_id, text) — a small labeled corpus across 5 topic clusters
CORPUS = [
    ("d1", "quantum computing error correction advances with Google Willow below threshold"),
    ("d2", "IBM prototypes real-time error correction decoder for fault tolerant quantum computing"),
    ("d3", "qLDPC codes are becoming the industry standard for quantum error correction in 2026"),
    ("d4", "logical qubit fault tolerance breakthroughs across five qubit technologies"),
    ("d5", "chocolate chip cookie recipe with brown butter and sea salt"),
    ("d6", "sourdough bread baking tips for a crispy crust"),
    ("d7", "best pasta carbonara recipe using guanciale and pecorino"),
    ("d8", "CVE-2025-1234 exploit details found during the pentest engagement"),
    ("d9", "recon findings tied to CVE-2025-1234 still need triage before the report"),
    ("d10", "vulnerability disclosure timeline for CVE-2025-1234 and remediation steps"),
    ("d11", "break down the HERMES browser module into three subtasks"),
    ("d12", "task decomposition for the HERMES documents module using TaskCreate"),
    ("d13", "HERMES tasks skill tracks progress with TaskCreate and TaskUpdate"),
    ("d14", "config file lives at /etc/hermes/config.yaml and needs a path traversal check"),
    ("d15", "SSRF prevention blocks cloud metadata endpoints in url_safety.py"),
]

# (query, relevant_doc_ids) — hand-labeled ground truth
QUERIES = [
    ("quantum error correction breakthroughs", {"d1", "d2", "d3", "d4"}),
    ("recipe for baking something with butter", {"d5", "d6", "d7"}),
    ("CVE-2025-1234 details", {"d8", "d9", "d10"}),
    ("decompose HERMES tasks into subtasks", {"d11", "d12", "d13"}),
    ("path traversal and SSRF security checks", {"d14", "d15"}),
]


def recall_at_k(retrieved_ids, relevant_ids, k=5):
    top_k = set(retrieved_ids[:k])
    if not relevant_ids:
        return None
    return len(top_k & relevant_ids) / len(relevant_ids)


def run_benchmark(index_dir: Path = None):
    if index_dir is None:
        index_dir = Path("/tmp/mnemos_benchmark_index")
    if index_dir.exists():
        shutil.rmtree(index_dir)

    bank = MnemosHNSW(index_dir, max_elements=1000)
    for doc_id, text in CORPUS:
        bank.insert(text, metadata={"doc_id": doc_id})
    bank.save()

    results = []
    total_recall = 0.0
    for query, relevant in QUERIES:
        hits = bank.query(query, k=5)
        retrieved_ids = [h["metadata"]["doc_id"] for h in hits]
        r = recall_at_k(retrieved_ids, relevant, k=5)
        total_recall += r
        results.append({
            "query": query,
            "relevant": sorted(relevant),
            "retrieved": retrieved_ids,
            "recall_at_5": round(r, 3),
        })

    avg_recall = round(total_recall / len(QUERIES), 3)
    shutil.rmtree(index_dir, ignore_errors=True)
    return {
        "embedder": "hashing-trick bag-of-words (embedder.py) — NOT a semantic model",
        "corpus_size": len(CORPUS),
        "num_queries": len(QUERIES),
        "per_query": results,
        "avg_recall_at_5": avg_recall,
    }


if __name__ == "__main__":
    if not HNSW_AVAILABLE:
        print(f"benchmark.py: {HNSW_IMPORT_ERROR} — pip install -r requirements.txt "
              f"(the benchmark exercises the HNSW index itself; there is no degraded mode)",
              file=sys.stderr)
        sys.exit(1)
    result = run_benchmark()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clio"))
    import tracker as clio_tracker
    clio_tracker.record_benchmark(result)
    print(json.dumps(result, indent=2))
