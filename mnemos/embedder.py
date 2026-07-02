#!/usr/bin/env python3
"""
mnemos/embedder.py — Mnemos v2 default embedder.

HONEST LABEL: this is NOT a semantic embedding model. It's a deterministic
feature-hashing bag-of-words/char-n-gram vectorizer (the "hashing trick") —
zero dependencies, zero network calls, always available offline. It captures
lexical/substring overlap, not meaning. Two sentences that say the same
thing in different words will NOT score highly similar under this embedder.

This exists so Mnemos v2's HNSW index has SOMETHING to index today, with a
clean seam to swap in a real embedding model without touching hnsw_index.py
or hybrid_search.py — both only depend on `embed(text) -> np.ndarray`.

EXTENSION POINT (do this before trusting recall@5 numbers for anything real):
    Replace `embed()` with a call to a real local embedding model, e.g.
    Ollama's `nomic-embed-text` via `POST /api/embeddings`, or any
    sentence-transformer run locally. Keep the L2-normalization step —
    hnsw_index.py assumes pre-normalized vectors (cosine via inner product).
"""
import hashlib
import re
import numpy as np

DIM = 256  # fixed output dimensionality


def _tokenize(text: str):
    text = text.lower()
    words = re.findall(r"[a-z0-9]+", text)
    tokens = list(words)
    # add char-trigrams too — helps partial/substring matches (e.g. CVE IDs)
    for w in words:
        padded = f"#{w}#"
        for i in range(len(padded) - 2):
            tokens.append(padded[i:i + 3])
    return tokens


def embed(text: str) -> np.ndarray:
    """Returns an L2-normalized float32 vector of length DIM."""
    vec = np.zeros(DIM, dtype=np.float32)
    if not text:
        return vec
    for tok in _tokenize(text):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % DIM
        sign = 1.0 if (h // DIM) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: embedder.py <text> [<text2> for cosine sim]", file=sys.stderr)
        sys.exit(2)
    v1 = embed(sys.argv[1])
    print(f"dim={len(v1)} norm={np.linalg.norm(v1):.4f}")
    if len(sys.argv) > 2:
        v2 = embed(sys.argv[2])
        sim = float(np.dot(v1, v2))
        print(f"cosine_similarity={sim:.4f}")
