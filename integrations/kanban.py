#!/usr/bin/env python3
"""
integrations/kanban.py — multi-profile Kanban board (Stage 5, opt-in).

Pattern source (reimplemented fresh, no code copied): the v1 blueprint's
"Kanban multi-profile board (only if multi-agent usage actually begins)".
Per HERMES_GOAL_Start_to_End.md Stage 5 it is explicitly conditional — this
is the minimal durable board so that WHEN Delegation fan-out (Stage 3) starts
producing parallel work, there is a place to track it per profile.

Storage: integrations/kanban.db (SQLite, gitignored, machine-local). Columns
are the three canonical lanes (todo / doing / done) plus a `profile` so
multiple agents/humans share one board without colliding. No server, no web
UI — the fallback IS the substance: a queryable table you drive from the CLI.

CLI:
    python3 integrations/kanban.py add "<title>" [--profile P] [--lane todo]
    python3 integrations/kanban.py move <id> <lane>
    python3 integrations/kanban.py board [--profile P]
    python3 integrations/kanban.py rm <id>
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meta.paths import state_file  # noqa: E402

# Board contents are the user's data — ~/.claude/hermes/ (meta/paths.py), so
# a plugin update doesn't take the board with it.
DB_PATH = state_file("integrations", "kanban.db")
LANES = ("todo", "doing", "done")


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile TEXT NOT NULL DEFAULT 'default',
            title TEXT NOT NULL,
            lane TEXT NOT NULL DEFAULT 'todo' CHECK (lane IN ('todo','doing','done')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add(title: str, profile: str = "default", lane: str = "todo"):
    if lane not in LANES:
        return {"added": False, "reason": f"lane must be one of {LANES}"}
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO cards (profile, title, lane, created_at, updated_at)"
            " VALUES (?,?,?,?,?)", (profile, title, lane, _now(), _now()))
        conn.commit()
        return {"added": True, "id": cur.lastrowid, "profile": profile, "lane": lane}
    finally:
        conn.close()


def move(card_id: int, lane: str):
    if lane not in LANES:
        return {"moved": False, "reason": f"lane must be one of {LANES}"}
    conn = _connect()
    try:
        cur = conn.execute("UPDATE cards SET lane=?, updated_at=? WHERE id=?",
                           (lane, _now(), card_id))
        conn.commit()
        return {"moved": cur.rowcount > 0, "id": card_id, "lane": lane}
    finally:
        conn.close()


def remove(card_id: int):
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM cards WHERE id=?", (card_id,))
        conn.commit()
        return {"removed": cur.rowcount > 0, "id": card_id}
    finally:
        conn.close()


def board(profile: str = None):
    conn = _connect()
    try:
        if profile:
            rows = conn.execute(
                "SELECT id, profile, title, lane FROM cards WHERE profile=? ORDER BY lane, id",
                (profile,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, profile, title, lane FROM cards ORDER BY profile, lane, id").fetchall()
    finally:
        conn.close()
    lanes = {lane: [] for lane in LANES}
    for cid, prof, title, lane in rows:
        lanes[lane].append({"id": cid, "profile": prof, "title": title})
    return {"profile": profile or "ALL",
            "counts": {lane: len(cards) for lane, cards in lanes.items()},
            "lanes": lanes}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: kanban.py add|move|rm|board ...", file=sys.stderr)
        sys.exit(2)
    cmd = args[0]
    if cmd == "add":
        profile, lane, title_parts = "default", "todo", []
        i = 1
        while i < len(args):
            if args[i] == "--profile":
                profile = args[i + 1]; i += 2
            elif args[i] == "--lane":
                lane = args[i + 1]; i += 2
            else:
                title_parts.append(args[i]); i += 1
        print(json.dumps(add(" ".join(title_parts), profile, lane), indent=2))
    elif cmd == "move" and len(args) >= 3:
        print(json.dumps(move(int(args[1]), args[2]), indent=2))
    elif cmd == "rm" and len(args) >= 2:
        print(json.dumps(remove(int(args[1])), indent=2))
    elif cmd == "board":
        profile = args[2] if len(args) >= 3 and args[1] == "--profile" else None
        print(json.dumps(board(profile), indent=2))
    else:
        print("usage: kanban.py add|move|rm|board ...", file=sys.stderr)
        sys.exit(2)
