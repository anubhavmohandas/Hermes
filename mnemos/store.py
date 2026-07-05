#!/usr/bin/env python3
"""
mnemos/store.py — Mnemos v1: SQLite WAL + FTS5 session store.

Pattern sources (reimplemented fresh, no code copied):
  - hermes-agent P18 (hermes_state.py): WAL mode, FTS5 trigram, 15-retry
    jittered backoff on write contention, passive checkpoint every 50 writes.

This is Phase 3A scope only: durable session storage + lexical (FTS5) search.
HNSW semantic search and 3-tier hybrid retrieval land in Phase 3B (Mnemos v2).
"""
import random
import re
import sqlite3
import sys
import time
from pathlib import Path

_HERMES_ROOT = Path(__file__).resolve().parent.parent
if str(_HERMES_ROOT) not in sys.path:
    sys.path.insert(0, str(_HERMES_ROOT))
from meta.contracts import MemoryEntry  # noqa: E402  boundary contract (V1_CHECKLIST §2)

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "vault" / "mnemos.db"
MAX_RETRIES = 15
BACKOFF_MIN_MS = 20
BACKOFF_MAX_MS = 150
CHECKPOINT_EVERY_N_WRITES = 50

# The 4 memory types from HERMES_Phase3_Blueprint.docx §4.1. Classification is
# deterministic keyword rules — same philosophy as brain.py's sensitivity
# check: hard-coded, inspectable, not LLM-based.
MEMORY_TYPES = ("user", "feedback", "project", "reference")

_REFERENCE_RE = re.compile(
    r"https?://|www\.|(?:[\w\-./]+/)+[\w\-.]+\.\w{1,6}|\bsee (?:the )?docs?\b|\bdashboard\b|\bticket\b",
    re.IGNORECASE)
# Feedback = guidance/corrections about HOW to work. Recall raised 2026-07-03
# after verification found natural corrections ("you got that wrong, fix it")
# matching nothing and silently falling through to the `project` catch-all —
# which is the exact signal Curator depends on. Grouped so the intent is
# legible: directives, corrections, and standing preferences.
_FEEDBACK_RE = re.compile(
    # directives
    r"\bdon'?t\b|\bnever\b|\balways\b|\binstead of\b|\byou should(?:n'?t)?\b|\bshould(?:'ve| have)\b|"
    r"\bshouldn'?t\b|\bstop (?:doing|using)\b|\bmake sure\b|\bfrom now on\b|\bnext time\b|\bin (?:the )?future\b|"
    # corrections
    r"\bgot (?:that|it|this)\b.{0,20}\bwrong\b|\b(?:that|it|this)(?:'s| is| was)? (?:wrong|incorrect|not right)\b|"
    r"\byou'?re wrong\b|\bfix (?:it|that|this)\b|\bredo\b|\byou missed\b|\bnot what i (?:asked|wanted|meant|said)\b|"
    r"\bmistake\b|\bcorrection\b|"
    # standing preferences about the work
    r"\bprefer(?:red|ence)?\b|\btoo (?:verbose|wordy|long|terse|brief|short)\b|\bbe (?:more|less)\b",
    re.IGNORECASE)
_USER_RE = re.compile(
    r"\bi am\b|\bi'?m a\b|\bmy (?:role|job|name|email|machine|setup|workflow|team|company)\b|"
    r"\bi work\b|\bi use\b|\bi like\b|\bi'?m the\b|\bcall me\b|\bi'?m based\b",
    re.IGNORECASE)


def classify_memory_type(content: str, role: str = "user") -> str:
    """Deterministic, priority-ordered:
      feedback  — corrections/guidance about how to work (checked first: a
                  correction often ALSO contains a path or 'I', and the
                  guidance is the more useful thing to retain)
      user      — facts about who the user is
      reference — pointers to external resources (URLs, paths, tickets)
      project   — everything else (default: ongoing work context)
    """
    text = content or ""
    if _FEEDBACK_RE.search(text):
        return "feedback"
    if role == "user" and _USER_RE.search(text):
        return "user"
    if _REFERENCE_RE.search(text):
        return "reference"
    return "project"

_write_counter = {"n": 0}


_journal_mode_cache = {}  # per-db-path cache so we don't re-probe every connection


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    key = str(db_path)
    mode = _journal_mode_cache.get(key)
    if mode is None:
        # WAL requires shared-memory (mmap) support from the underlying
        # filesystem. Network mounts / FUSE passthroughs / some synced-folder
        # setups (Dropbox, OneDrive, sandboxed containers) can raise
        # "disk I/O error" here even though plain reads/writes work fine.
        # Fall back to DELETE journal mode rather than hard-failing — WAL is
        # a performance/concurrency optimization, not a correctness
        # requirement for a single-writer local tool.
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            mode = "wal"
        except sqlite3.OperationalError:
            conn.execute("PRAGMA journal_mode=DELETE;")
            mode = "delete"
            import sys
            print(f"mnemos/store.py: WAL mode unavailable on this filesystem "
                  f"(db_path={db_path}) — falling back to DELETE journal mode. "
                  f"Concurrent-reader performance is reduced; correctness is unaffected.",
                  file=sys.stderr)
        _journal_mode_cache[key] = mode
    else:
        conn.execute(f"PRAGMA journal_mode={mode};")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def vault_canary(db_path: Path = DEFAULT_DB_PATH):
    """Write+read+delete one row to prove the vault filesystem actually
    supports SQLite writes. The WAL->DELETE fallback in _connect() does NOT
    cover this failure mode: on FUSE/network/synced-folder mounts (Dropbox,
    iCloud, OneDrive, Cowork mounts) the 'disk I/O error' hits the write
    itself, not the WAL pragma — reproduced live 2026-07-02 (C5). Better to
    refuse the vault loudly at init than discover it mid-session with every
    write dying silently. Returns (ok: bool, reason: str)."""
    try:
        conn = _connect(db_path)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS _canary (v TEXT)")
            conn.execute("INSERT INTO _canary (v) VALUES ('ok')")
            conn.commit()
            row = conn.execute("SELECT v FROM _canary LIMIT 1").fetchone()
            conn.execute("DELETE FROM _canary")
            conn.commit()
        finally:
            conn.close()
        if not row or row[0] != "ok":
            return False, f"canary read-back failed on {db_path}"
        return True, "vault writable"
    except sqlite3.OperationalError as e:
        return False, (f"vault at {db_path} failed the write canary ({e}) — this is the "
                       f"known non-local-filesystem failure (network mount / FUSE / "
                       f"Dropbox/iCloud/OneDrive-synced folder). Move VAULT_PATH to a "
                       f"real local disk.")


def _migrate_memory_type(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
    if cols and "memory_type" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN memory_type TEXT NOT NULL DEFAULT 'project'")


def init_db(db_path: Path = DEFAULT_DB_PATH):
    ok, reason = vault_canary(db_path)
    if not ok:
        raise RuntimeError(f"mnemos/store.py: REFUSING vault — {reason}")
    conn = _connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            memory_type TEXT NOT NULL DEFAULT 'project',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    _migrate_memory_type(conn)  # pre-3B databases lack the column
    # FTS5 with trigram tokenizer — substring search, handles CJK.
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            content, session_id UNINDEXED, tokenize='trigram'
        );
    """)
    conn.commit()
    conn.close()
    return db_path


def _execute_with_retry(db_path: Path, fn):
    """Runs fn(conn) with 15 retries + 20-150ms jitter backoff on 'database is locked'."""
    last_err = None
    for attempt in range(MAX_RETRIES):
        conn = _connect(db_path)
        try:
            result = fn(conn)
            conn.commit()
            return result
        except sqlite3.OperationalError as e:
            last_err = e
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                jitter = random.uniform(BACKOFF_MIN_MS, BACKOFF_MAX_MS) / 1000.0
                time.sleep(jitter)
                continue
            raise
        finally:
            conn.close()
    raise RuntimeError(
        f"mnemos/store.py: vault write failed after {MAX_RETRIES} retries with "
        f"backoff ({last_err}). The vault is single-writer — this means another "
        f"process held the write lock the whole time. What to do: close any other "
        f"running HERMES process (a second CLI session, a stuck Dream/Curator job) "
        f"that may be writing to {db_path}, then retry. If nothing else is running, "
        f"a crashed process may have left a stale lock — remove {db_path}-wal / "
        f"{db_path}-shm and retry.")


def write_message(session_id: str, role: str, content: str, metadata: str = "{}",
                   db_path: Path = DEFAULT_DB_PATH, memory_type: str = None):
    if memory_type is None:
        memory_type = classify_memory_type(content, role)
    elif memory_type not in MEMORY_TYPES:
        raise ValueError(f"memory_type must be one of {MEMORY_TYPES}, got {memory_type!r}")

    def _write(conn):
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, metadata, memory_type) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, metadata, memory_type),
        )
        conn.execute(
            "INSERT INTO messages_fts (rowid, content, session_id) VALUES (?, ?, ?)",
            (cur.lastrowid, content, session_id),
        )
        return cur.lastrowid

    msg_id = _execute_with_retry(db_path, _write)

    _write_counter["n"] += 1
    if _write_counter["n"] % CHECKPOINT_EVERY_N_WRITES == 0:
        checkpoint(db_path)

    return msg_id


def checkpoint(db_path: Path = DEFAULT_DB_PATH):
    """No-op when running in DELETE journal mode fallback — checkpointing
    only means something for WAL."""
    if _journal_mode_cache.get(str(db_path)) != "wal":
        return
    conn = _connect(db_path)
    try:
        conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
        conn.commit()
    finally:
        conn.close()


def search_messages(query: str, limit: int = 10, db_path: Path = DEFAULT_DB_PATH):
    conn = _connect(db_path)
    try:
        # FTS5 trigram tokenizer requires quoting the match string.
        # Ranking note (audited 2026-07-02, C7): the blueprint specifies BM25
        # k1=1.5, b=0.75; SQLite's built-in bm25() hard-codes k1=1.2, b=0.75
        # and exposes only per-column weights — the spec'd k1 is not
        # implementable without a custom rank function. Deliberate deviation,
        # negligible at this corpus size.
        safe_query = query.replace('"', '""')
        rows = conn.execute(
            """
            SELECT m.id, m.session_id, m.role, m.content, m.created_at, m.memory_type
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (f'"{safe_query}"', limit),
        ).fetchall()
        return [
            {"id": r[0], "session_id": r[1], "role": r[2], "content": r[3],
             "created_at": r[4], "memory_type": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


def search(query: str, limit: int = 10, db_path: Path = DEFAULT_DB_PATH):
    """Public contract (V1_CHECKLIST §2): mnemos.search(query) -> list[MemoryEntry].

    Thin, pinned wrapper over search_messages(). The internal (FTS5 query,
    ranking, the row->dict mapping) can change; callers depend only on getting
    a list[MemoryEntry] back. search_messages() stays for the CLI and existing
    dict-based tests.
    """
    return [MemoryEntry.from_dict(r) for r in search_messages(query, limit=limit, db_path=db_path)]


def get_session(session_id: str, db_path: Path = DEFAULT_DB_PATH):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, role, content, created_at, memory_type FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [{"id": r[0], "role": r[1], "content": r[2], "created_at": r[3], "memory_type": r[4]}
                for r in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    import json as _json

    if len(sys.argv) < 2:
        print("usage: store.py init|canary|write|search|get ...", file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]
    if cmd == "init":
        path = init_db()
        print(f"initialized: {path}")
    elif cmd == "canary":
        ok, reason = vault_canary()
        print(reason)
        sys.exit(0 if ok else 1)
    elif cmd == "write":
        # store.py write <session_id> <role> <content> [memory_type]
        mtype = sys.argv[5] if len(sys.argv) > 5 else None
        msg_id = write_message(sys.argv[2], sys.argv[3], sys.argv[4], memory_type=mtype)
        print(f"wrote message id={msg_id}")
    elif cmd == "search":
        results = search_messages(sys.argv[2])
        print(_json.dumps(results, indent=2))
    elif cmd == "get":
        results = get_session(sys.argv[2])
        print(_json.dumps(results, indent=2))
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)
