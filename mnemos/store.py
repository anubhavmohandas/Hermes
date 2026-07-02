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
import sqlite3
import time
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "vault" / "mnemos.db"
MAX_RETRIES = 15
BACKOFF_MIN_MS = 20
BACKOFF_MAX_MS = 150
CHECKPOINT_EVERY_N_WRITES = 50

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


def init_db(db_path: Path = DEFAULT_DB_PATH):
    conn = _connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
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
    raise RuntimeError(f"write failed after {MAX_RETRIES} retries: {last_err}")


def write_message(session_id: str, role: str, content: str, metadata: str = "{}",
                   db_path: Path = DEFAULT_DB_PATH):
    def _write(conn):
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, metadata) VALUES (?, ?, ?, ?)",
            (session_id, role, content, metadata),
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
        safe_query = query.replace('"', '""')
        rows = conn.execute(
            """
            SELECT m.id, m.session_id, m.role, m.content, m.created_at
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (f'"{safe_query}"', limit),
        ).fetchall()
        return [
            {"id": r[0], "session_id": r[1], "role": r[2], "content": r[3], "created_at": r[4]}
            for r in rows
        ]
    finally:
        conn.close()


def get_session(session_id: str, db_path: Path = DEFAULT_DB_PATH):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [{"id": r[0], "role": r[1], "content": r[2], "created_at": r[3]} for r in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    import json as _json

    if len(sys.argv) < 2:
        print("usage: store.py init|write|search|get ...", file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]
    if cmd == "init":
        path = init_db()
        print(f"initialized: {path}")
    elif cmd == "write":
        # write.py write <session_id> <role> <content>
        msg_id = write_message(sys.argv[2], sys.argv[3], sys.argv[4])
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
