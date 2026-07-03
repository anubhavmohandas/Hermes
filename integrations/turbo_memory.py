#!/usr/bin/env python3
"""
integrations/turbo_memory.py — C++ turbo memory shim (Stage 5, opt-in).

Pattern source (reimplemented fresh, no code copied): the v1 blueprint's
"C++ turbo memory (opt-in compile, Python fallback)". Per
HERMES_GOAL_Start_to_End.md Stage 5 AND Invariant #5 ("C++ → Python"), the
POINT of this module is the fallback: a fast top-k cosine search that uses a
compiled extension IF one was built, and a pure-NumPy (or pure-Python)
implementation otherwise — same API, same results, only speed differs.

There is no bundled C++ source here (patterns-not-code, Invariant #4, and a
compiler is not assumable). `backend()` reports what's actually active so no
one mistakes the Python fallback for the turbo path. If someone later drops
in a `_turbo` compiled module exposing `topk(query, matrix, k)`, this picks
it up automatically — that's the whole opt-in contract.

CLI:
    python3 integrations/turbo_memory.py status
    python3 integrations/turbo_memory.py selftest
"""
import json
import sys


def _has_turbo():
    try:
        import _turbo  # noqa: F401  — a compiled extension, only if built
        return True
    except ImportError:
        return False


def _has_numpy():
    try:
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def backend() -> str:
    if _has_turbo():
        return "cpp"
    if _has_numpy():
        return "numpy"
    return "python"


def topk(query, matrix, k=5):
    """Top-k by cosine similarity. query: list[float]; matrix: list[list[float]].
    Returns [(index, score), ...] highest first. Identical results across all
    three backends — only the compute path differs."""
    b = backend()
    if b == "cpp":
        import _turbo
        return _turbo.topk(query, matrix, k)
    if b == "numpy":
        import numpy as np
        q = np.asarray(query, dtype=float)
        m = np.asarray(matrix, dtype=float)
        qn = q / (np.linalg.norm(q) or 1.0)
        mn = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-12)
        scores = mn @ qn
        idx = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in idx]
    # pure python fallback — no deps at all
    def dot(a, c): return sum(x * y for x, y in zip(a, c))
    def norm(a): return (sum(x * x for x in a) ** 0.5) or 1.0
    qn = norm(query)
    scored = [(i, dot(query, row) / (qn * norm(row))) for i, row in enumerate(matrix)]
    scored.sort(key=lambda t: -t[1])
    return scored[:k]


def status():
    return {"backend": backend(), "turbo_available": _has_turbo(),
            "numpy_available": _has_numpy(),
            "note": "cpp is opt-in (drop in a compiled _turbo module); "
                    "numpy/python fallbacks give identical results"}


def selftest():
    matrix = [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [-1.0, 0.0]]
    result = topk([1.0, 0.0], matrix, k=2)
    ok = result[0][0] == 0 and result[1][0] == 1
    return {"backend": backend(), "topk": result, "ok": ok}


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        out = selftest()
        print(json.dumps(out, indent=2))
        sys.exit(0 if out["ok"] else 1)
    print(json.dumps(status(), indent=2))
