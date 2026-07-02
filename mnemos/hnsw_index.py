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
import time
from pathlib import Path

import hnswlib
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from embedder import embed, DIM

M = 16
EF_CONSTRUCTION = 200
EF_SEARCH = 50  # query-time recall/speed tradeoff, independent of build params
SPACE = "cosine"


class MnemosHNSW:
    def __init__(self, index_dir: Path, max_elements: int = 10_000):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.bin_path = self.index_dir / "hnsw.bin"
        self.meta_path = self.index_dir / "hnsw_meta.json"
        self.max_elements = max_elements

        self.index = hnswlib.Index(space=SPACE, dim=DIM)
        self.records = {}  # str(label) -> {text, metadata, created_at}
        self.next_label = 0

        if self.bin_path.exists() and self.meta_path.exists():
            self._load()
        else:
            self.index.init_index(max_elements=max_elements, M=M, ef_construction=EF_CONSTRUCTION)
            self.index.set_ef(EF_SEARCH)

    def _load(self):
        self.index.load_index(str(self.bin_path), max_elements=self.max_elements)
        self.index.set_ef(EF_SEARCH)
        meta = json.loads(self.meta_path.read_text())
        self.records = meta["records"]
        self.next_label = meta["next_label"]

    def save(self):
        self.index.save_index(str(self.bin_path))
        self.meta_path.write_text(json.dumps({
            "records": self.records,
            "next_label": self.next_label,
            "params": {"M": M, "efConstruction": EF_CONSTRUCTION, "space": SPACE, "dim": DIM},
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
