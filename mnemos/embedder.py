#!/usr/bin/env python3
"""
mnemos/embedder.py — Mnemos v2 embedder, two backends behind one seam.

Backend selection: HERMES_EMBEDDER env var — "hash" (default) or "nvidia".
Callers only depend on `embed(text) -> np.ndarray` (L2-normalized float32)
and `embedding_dim() -> int`; hnsw_index.py stores the dim + backend in its
meta sidecar and refuses to load an index built under a different one, so
the two embedding spaces can never silently mix.

Backend "hash" (default, offline, zero deps beyond numpy):
    HONEST LABEL: NOT a semantic model. Deterministic feature-hashing
    bag-of-words/char-n-gram vectorizer ("hashing trick") — captures
    lexical/substring overlap, not meaning. Two sentences that say the same
    thing in different words will NOT score similar. Proven: paraphrase
    similarity 0.0 in the 2026-07-02 audit.

Backend "nvidia" (real semantic embeddings via the NVIDIA API, needs
NVIDIA_API_KEY):
    POST {HERMES_NVIDIA_URL:-https://integrate.api.nvidia.com}/v1/embeddings
    with HERMES_EMBED_MODEL (default nvidia/nv-embedqa-e5-v5, 1024-dim).
    Fails LOUDLY if the key is missing or the API is unreachable — silently
    falling back to the hash backend would write 256-dim lexical vectors
    into a 1024-dim semantic index.
"""
import hashlib
import json
import os
import re
import urllib.error
import urllib.request

import numpy as np

DIM = 256  # hash backend's fixed output dimensionality

NVIDIA_URL = os.environ.get("HERMES_NVIDIA_URL", "https://integrate.api.nvidia.com")
NVIDIA_EMBED_MODEL = os.environ.get("HERMES_EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")

_nvidia_dim_cache = {}


def backend() -> str:
    b = os.environ.get("HERMES_EMBEDDER", "hash")
    if b not in ("hash", "nvidia"):
        raise ValueError(f"HERMES_EMBEDDER must be 'hash' or 'nvidia', got {b!r}")
    return b


def embedding_dim() -> int:
    if backend() == "hash":
        return DIM
    key = (NVIDIA_URL, NVIDIA_EMBED_MODEL)
    if key not in _nvidia_dim_cache:
        _nvidia_dim_cache[key] = len(_nvidia_embed_raw("dimension probe"))
    return _nvidia_dim_cache[key]


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


# --------------------------------------------------------------------------
# hash backend
# --------------------------------------------------------------------------

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


def _hash_embed(text: str) -> np.ndarray:
    vec = np.zeros(DIM, dtype=np.float32)
    for tok in _tokenize(text):
        # feature-hashing bucket function, NOT security — and the digest value
        # MUST stay stable or every existing HNSW index becomes inconsistent,
        # so this stays md5 with usedforsecurity=False (never swap the algo; L4)
        h = int(hashlib.md5(tok.encode(), usedforsecurity=False).hexdigest(), 16)
        idx = h % DIM
        sign = 1.0 if (h // DIM) % 2 == 0 else -1.0
        vec[idx] += sign
    return _normalize(vec)


# --------------------------------------------------------------------------
# nvidia backend
# --------------------------------------------------------------------------

def _nvidia_embed_raw(text: str) -> list:
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "HERMES_EMBEDDER=nvidia but NVIDIA_API_KEY is not set. NOT falling "
            "back to the hash backend — that would mix embedding spaces in the "
            "index. Set the key or unset HERMES_EMBEDDER.")
    # occam: one fixed input_type for both queries and passages — asymmetric
    # query/passage embedding modes if recall on real data warrants it
    payload = json.dumps({"model": NVIDIA_EMBED_MODEL, "input": [text],
                          "input_type": "query", "encoding_format": "float"}).encode()
    req = urllib.request.Request(
        f"{NVIDIA_URL}/v1/embeddings", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"HERMES_EMBEDDER=nvidia but {NVIDIA_URL} is unreachable or gave a bad "
            f"response ({e}). NOT falling back to the hash backend — that would mix "
            f"embedding spaces in the index. Check NVIDIA_API_KEY / network, or "
            f"unset HERMES_EMBEDDER.")
    items = data.get("data") or []
    embedding = items[0].get("embedding") if items else None
    if not embedding:
        raise RuntimeError(
            f"NVIDIA API returned no embedding for model '{NVIDIA_EMBED_MODEL}' — "
            f"is it a valid embeddings model id on integrate.api.nvidia.com?")
    return embedding


def _nvidia_embed(text: str) -> np.ndarray:
    return _normalize(np.asarray(_nvidia_embed_raw(text), dtype=np.float32))


# --------------------------------------------------------------------------
# the seam
# --------------------------------------------------------------------------

def embed(text: str) -> np.ndarray:
    """Returns an L2-normalized float32 vector of length embedding_dim()."""
    if not text:
        return np.zeros(embedding_dim(), dtype=np.float32)
    return _nvidia_embed(text) if backend() == "nvidia" else _hash_embed(text)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: embedder.py <text> [<text2> for cosine sim]", file=sys.stderr)
        sys.exit(2)
    v1 = embed(sys.argv[1])
    print(f"backend={backend()} dim={len(v1)} norm={np.linalg.norm(v1):.4f}")
    if len(sys.argv) > 2:
        v2 = embed(sys.argv[2])
        sim = float(np.dot(v1, v2))
        print(f"cosine_similarity={sim:.4f}")
