#!/usr/bin/env python3
"""
mnemos/hnsw_index.py — Mnemos v2 semantic index.

Pattern source (reimplemented fresh, no code copied): CC_SRC_PATTERNS.md
Pattern #81 — ruflo hnsw-index.ts definitive parameter reference:
    M=16, efConstruction=200, cosine metric, pre-normalized embeddings
    inserted at insert time (so cosine similarity reduces to inner product).

hnswlib itself only stores {int label -> vector}. It has no concept of text
or metadata, so this wraps it with a JSON sidecar mapping label -> record
{text, metadata, created_at}, persisted next to the .bin index file.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# hnswlib + numpy are Tier C's only third-party deps (see requirements.txt).
# A missing dep must degrade Tier C, not crash every importer — the same
# graceful-degradation contract store.py already honors for WAL mode.
# Importers (hybrid_search.py, reasoningbank/bank.py) check HNSW_AVAILABLE
# and fall back to Tier A/B lexical retrieval when it's False.
try:
    import hnswlib
    import numpy as np
    import embedder
    from embedder import embed  # embedder needs numpy too
    HNSW_AVAILABLE = True
    HNSW_IMPORT_ERROR = None
except ImportError as _e:
    hnswlib = None
    np = None
    embedder = None
    HNSW_AVAILABLE = False
    HNSW_IMPORT_ERROR = _e

M = 16
EF_CONSTRUCTION = 200
EF_SEARCH = 50  # query-time recall/speed tradeoff, independent of build params
SPACE = "cosine"
# Blueprint's binary quantization (32x compression) is deliberately omitted:
# at current corpus scale (<10k vectors) the full-precision index is a few MB
# and quantization would only add a recall penalty. Revisit if the vault ever
# holds >100k vectors.


class MnemosHNSW:
    def __init__(self, index_dir: Path, max_elements: int = 10_000):
        if not HNSW_AVAILABLE:
            raise RuntimeError(
                f"Tier C semantic index unavailable: {HNSW_IMPORT_ERROR}. "
                f"Install with: pip install -r requirements.txt"
            )
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.bin_path = self.index_dir / "hnsw.bin"
        self.meta_path = self.index_dir / "hnsw_meta.json"
        self.max_elements = max_elements

        # dim comes from the active embedder backend (hash=256,
        # ollama/nomic-embed-text=768) — see embedder.py.
        self.backend = embedder.backend()
        self.dim = embedder.embedding_dim()
        self.index = hnswlib.Index(space=SPACE, dim=self.dim)
        self.records = {}  # str(label) -> {text, metadata, created_at}
        self.next_label = 0

        if self.bin_path.exists() and self.meta_path.exists():
            self._load()
        else:
            self.index.init_index(max_elements=max_elements, M=M, ef_construction=EF_CONSTRUCTION)
            self.index.set_ef(EF_SEARCH)

    def _load(self):
        # Refuse to mix embedding spaces: an index built under one backend is
        # meaningless queried under another, even when the dims happen to match.
        meta = json.loads(self.meta_path.read_text())
        params = meta.get("params", {})
        saved_dim = params.get("dim")
        saved_backend = params.get("embedder")
        if (saved_dim is not None and saved_dim != self.dim) or \
           (saved_backend is not None and saved_backend != self.backend):
            raise RuntimeError(
                f"index at {self.index_dir} was built with embedder="
                f"{saved_backend or 'unknown'} dim={saved_dim}, but the active "
                f"embedder is {self.backend} dim={self.dim}. Set HERMES_EMBEDDER "
                f"to match, or rebuild the index from its source log.")
        self.index.load_index(str(self.bin_path), max_elements=self.max_elements)
        self.index.set_ef(EF_SEARCH)
        self.records = meta["records"]
        self.next_label = meta["next_label"]

    def save(self):
        self.index.save_index(str(self.bin_path))
        self.meta_path.write_text(json.dumps({
            "records": self.records,
            "next_label": self.next_label,
            "params": {"M": M, "efConstruction": EF_CONSTRUCTION, "space": SPACE,
                       "dim": self.dim, "embedder": self.backend},
        }, indent=2))

    def insert(self, text: str, metadata: dict = None):
        vec = embed(text)  # already L2-normalized by embedder.py
        label = self.next_label
        self.index.add_items(np.array([vec]), np.array([label]))
        self.records[str(label)] = {
            "text": text,
            "metadata": metadata or {},
            "created_at": time.time(),
        }
        self.next_label += 1
        return label

    def query(self, text: str, k: int = 5):
        if self.index.get_current_count() == 0:
            return []
        k = min(k, self.index.get_current_count())
        vec = embed(text)
        labels, distances = self.index.knn_query(np.array([vec]), k=k)
        results = []
        for label, dist in zip(labels[0], distances[0]):
            record = self.records.get(str(label), {})
            # hnswlib cosine space returns distance = 1 - cosine_similarity
            similarity = 1.0 - float(dist)
            results.append({
                "label": int(label),
                "similarity": round(similarity, 4),
                "text": record.get("text"),
                "metadata": record.get("metadata"),
            })
        return results


if __name__ == "__main__":
    import sys as _sys
    if not HNSW_AVAILABLE:
        print(f"hnsw_index.py: {HNSW_IMPORT_ERROR} — pip install -r requirements.txt", file=_sys.stderr)
        _sys.exit(1)
    if len(_sys.argv) < 3:
        print("usage: hnsw_index.py <index_dir> insert <text> | query <text> [k]", file=_sys.stderr)
        _sys.exit(2)
    index_dir = Path(_sys.argv[1])
    cmd = _sys.argv[2]
    bank = MnemosHNSW(index_dir)
    if cmd == "insert":
        label = bank.insert(_sys.argv[3])
        bank.save()
        print(json.dumps({"label": label}))
    elif cmd == "query":
        k = int(_sys.argv[4]) if len(_sys.argv) > 4 else 5
        results = bank.query(_sys.argv[3], k=k)
        print(json.dumps(results, indent=2))
    else:
        print(f"unknown command: {cmd}", file=_sys.stderr)
        _sys.exit(2)
