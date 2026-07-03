#!/usr/bin/env python3
"""
integrations/db/store.py — db module (Stage 5, opt-in).

Pattern source (reimplemented fresh, no code copied): Supabase local dev
shape (a Postgres URL + ordered SQL migrations) reduced to its portable
core. Per HERMES_GOAL_Start_to_End.md Stage 5: "db/ (Supabase local +
migrations)" — with the Invariant #5 fallback made real: **Postgres when a
DATABASE_URL + psycopg is available, local SQLite otherwise**, same
migration runner over both. Nothing here is on HERMES's critical path; it's
a place to keep structured project data with versioned schema.

Migrations are ordered .sql files in integrations/db/migrations/ named
NNNN_name.sql. A `schema_migrations` table records which have run; `migrate`
applies only the un-applied ones, in order, each in a transaction. Re-running
is a no-op (idempotent) — the whole point of tracking applied versions.

Backend selection:
  - DATABASE_URL set AND psycopg importable -> Postgres (Supabase/local pg).
  - otherwise -> SQLite at integrations/db/hermes_db.sqlite (the fallback,
    always works, zero deps). The active backend is reported, never hidden.

CLI:
    python3 integrations/db/store.py status
    python3 integrations/db/store.py migrate
    python3 integrations/db/store.py query "SELECT ..."
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent
MIGRATIONS_DIR = DB_DIR / "migrations"
SQLITE_PATH = DB_DIR / "hermes_db.sqlite"


def backend() -> str:
    if os.environ.get("DATABASE_URL"):
        try:
            import psycopg  # noqa: F401
            return "postgres"
        except ImportError:
            return "sqlite"  # URL set but driver missing -> honest fallback
    return "sqlite"


def _connect():
    if backend() == "postgres":
        import psycopg
        return psycopg.connect(os.environ["DATABASE_URL"]), "postgres"
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn, "sqlite"


def _ensure_migrations_table(conn, kind):
    ddl = ("CREATE TABLE IF NOT EXISTS schema_migrations ("
           "version TEXT PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.execute(ddl)
    conn.commit()


def _applied_versions(conn):
    try:
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _migration_files():
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(MIGRATIONS_DIR.glob("[0-9]*.sql"))


def migrate():
    MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    conn, kind = _connect()
    applied = []
    try:
        _ensure_migrations_table(conn, kind)
        done = _applied_versions(conn)
        for path in _migration_files():
            version = path.stem
            if version in done:
                continue
            sql = path.read_text()
            conn.execute("BEGIN")
            try:
                conn.executescript(sql) if kind == "sqlite" else conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)" if kind == "postgres"
                    else "INSERT INTO schema_migrations (version) VALUES (?)",
                    (version,))
                conn.commit()
                applied.append(version)
            except Exception as e:
                conn.rollback()
                return {"backend": kind, "applied": applied, "failed_on": version,
                        "error": str(e)}
    finally:
        conn.close()
    return {"backend": kind, "applied": applied,
            "already_current": len(applied) == 0}


def query(sql: str):
    conn, kind = _connect()
    try:
        cur = conn.execute(sql)
        if cur.description:
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            return {"backend": kind, "rows": rows}
        conn.commit()
        return {"backend": kind, "rowcount": cur.rowcount}
    finally:
        conn.close()


def status():
    return {
        "backend": backend(),
        "sqlite_fallback_path": str(SQLITE_PATH),
        "database_url_set": bool(os.environ.get("DATABASE_URL")),
        "migrations_dir": str(MIGRATIONS_DIR),
        "migrations_available": [p.stem for p in _migration_files()],
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "status":
        print(json.dumps(status(), indent=2))
    elif args and args[0] == "migrate":
        print(json.dumps(migrate(), indent=2))
    elif len(args) >= 2 and args[0] == "query":
        print(json.dumps(query(args[1]), indent=2))
    else:
        print("usage: store.py status | migrate | query \"<sql>\"", file=sys.stderr)
        sys.exit(2)
