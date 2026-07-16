#!/usr/bin/env python3
"""
mnemos/hybrid_search.py — Mnemos v2: 3-tier hybrid retrieval.

Pattern source (reimplemented fresh, no code copied): codebase-memory-mcp
RAM-first pipeline — three confidence tiers, confidence-stratified resolution.

  Tier A — BM25 lexical: reuses Mnemos v1's FTS5 trigram index (store.py),
           which already ranks by SQLite's built-in bm25(). Fast, high
           precision for exact keyword/substring matches.
  Tier B — Regex fallback: structured patterns (CVE IDs, file paths,
           function-like identifiers) — scans raw message content directly,
           independent of FTS5 tokenization quirks.
  Tier C — Semantic HNSW: mnemos/hnsw_index.py. Backend depends on
           HERMES_EMBEDDER (see embedder.py): "hash" (default) is the
           hashing-trick vectorizer — treat those hits as "lexical-overlap
           adjacent," NOT "conceptually similar"; "nvidia" is a real
           embedding model (nv-embedqa-e5-v5 via the NVIDIA API). Tier C
           confidence stays LOW under both until the nvidia backend has
           earned trust on real recall data.

Confidence-stratified resolution: a concrete, inspectable rule set — not a
vibe. See `resolve_confidence()`.
"""
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store
from hnsw_index import MnemosHNSW, HNSW_AVAILABLE, HNSW_IMPORT_ERROR


def hnsw_backend() -> str:
    """Active embedder backend name, without importing embedder when its
    numpy dep is missing (embedder is None inside hnsw_index's guard then)."""
    import hnsw_index as _hi
    return _hi.embedder.backend() if _hi.embedder is not None else "hash"

STRUCTURED_PATTERNS = [
    ("cve_id", re.compile(r"CVE-\d{4}-\d+", re.IGNORECASE)),
    ("file_path", re.compile(r"(?:[\w\-./]+/)+[\w\-.]+\.\w{1,6}")),
    ("function_name", re.compile(r"\b[a-z_][a-z0-9_]{2,}\(\)")),
    ("hex_hash", re.compile(r"\b[0-9a-f]{8,64}\b", re.IGNORECASE)),
]


def extract_structured_patterns(query: str):
    found = []
    for kind, pattern in STRUCTURED_PATTERNS:
        for m in pattern.finditer(query):
            found.append((kind, m.group(0)))
    return found


def regex_scan_messages(patterns, db_path: Path = store.DEFAULT_DB_PATH, limit: int = 10):
    if not patterns or not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT id, session_id, role, content, created_at FROM messages").fetchall()
    except sqlite3.OperationalError as e:
        import sys as _sys
        print(f"regex_scan_messages: SQLite unavailable ({e}) — returning no Tier B hits", file=_sys.stderr)
        return []
    finally:
        conn.close()
    hits = []
    for kind, needle in patterns:
        for r in rows:
            if needle.lower() in r[3].lower():
                hits.append({
                    "id": r[0], "session_id": r[1], "role": r[2], "content": r[3],
                    "created_at": r[4], "matched_pattern": kind, "matched_value": needle,
                })
    # de-dupe by message id, cap
    seen = set()
    deduped = []
    for h in hits:
        if h["id"] not in seen:
            seen.add(h["id"])
            deduped.append(h)
    return deduped[:limit]


def _distinct_query_words_in(content: str, query: str) -> int:
    """How many distinct query words (len >= 3) appear in content. This is
    the 'is the TOP hit clearly about the query' proxy — sqlite's bm25 rank
    isn't exposed as a raw score through this driver."""
    content_l = (content or "").lower()
    words = {w for w in re.findall(r"[a-z0-9]{3,}", query.lower())}
    return sum(1 for w in words if w in content_l)


def resolve_confidence(query, tier_a, tier_b, tier_c):
    """
    Concrete rules, in priority order:
      1. Tier B (exact structured match) present -> HIGH, return Tier B first.
      2. Tier A present AND the TOP FTS5 hit's content contains >=2 distinct
         query words -> HIGH. Measured on the top hit's quality, NOT on how
         many rows came back — two weak rows are not more trustworthy than
         one strong one (audited 2026-07-02, C3: the old len(tier_a) >= 2
         check measured the wrong thing).
      3. Tier A present but top hit shares <2 distinct query words -> MEDIUM.
      4. Only Tier C hits, best similarity >= 0.45 -> LOW
         (flag explicitly: lexical-overlap embedder, not true semantic).
      5. Nothing above threshold -> NONE, say so, don't fabricate a hit.
    """
    if tier_b:
        return "HIGH", "tier_b_regex", "exact structured pattern match (CVE id / path / hash)"
    if tier_a:
        strong = _distinct_query_words_in(tier_a[0].get("content", ""), query) >= 2
        return ("HIGH" if strong else "MEDIUM"), "tier_a_bm25", "FTS5 lexical match"
    if tier_c and tier_c[0]["similarity"] >= 0.45:
        if HNSW_AVAILABLE and hnsw_backend() == "nvidia":
            reason_c = "semantic embedding match (nvidia backend) — conceptually similar, still verify before relying on it"
        else:
            reason_c = "hashing-trick lexical-overlap embedder — not true semantic similarity, verify before relying on it"
        return "LOW", "tier_c_semantic", reason_c
    return "NONE", None, "no hit cleared the confidence threshold in any tier"


def hybrid_search(query: str, db_path: Path = store.DEFAULT_DB_PATH,
                   hnsw_dir: Path = None, k: int = 5):
    if hnsw_dir is None:
        hnsw_dir = Path(db_path).parent / "hnsw"

    tier_a = []
    if Path(db_path).exists():
        try:
            tier_a = store.search_messages(query, limit=k, db_path=db_path)
        except Exception as e:
            # SQLite can fail here on constrained filesystems (network mounts,
            # some sandboxed containers) even when the DB file exists — WAL
            # writes are the specific failure mode documented in store.py.
            # Degrade to Tier B/C rather than crashing the whole search.
            import sys as _sys
            print(f"hybrid_search: Tier A (BM25/FTS5) unavailable ({e}) — degrading to Tier B/C", file=_sys.stderr)
            tier_a = []

    patterns = extract_structured_patterns(query)
    tier_b = regex_scan_messages(patterns, db_path=db_path, limit=k)

    tier_c = []
    if not HNSW_AVAILABLE:
        print(f"hybrid_search: Tier C (semantic HNSW) unavailable ({HNSW_IMPORT_ERROR}) "
              f"— degrading to Tier A/B; pip install -r requirements.txt to restore",
              file=sys.stderr)
    elif Path(hnsw_dir / "hnsw.bin").exists():
        bank = MnemosHNSW(hnsw_dir)
        tier_c = bank.query(query, k=k)

    confidence, resolved_tier, reason = resolve_confidence(query, tier_a, tier_b, tier_c)

    return {
        "query": query,
        "confidence": confidence,
        "resolved_tier": resolved_tier,
        "reason": reason,
        "tier_a_bm25": tier_a,
        "tier_b_regex": tier_b,
        "tier_c_semantic": tier_c,
    }


if __name__ == "__main__":
    import json
    if len(sys.argv) < 2:
        print("usage: hybrid_search.py \"<query>\" [k]", file=sys.stderr)
        sys.exit(2)
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    result = hybrid_search(sys.argv[1], k=k)
    print(json.dumps(result, indent=2))
