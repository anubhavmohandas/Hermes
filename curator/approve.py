#!/usr/bin/env python3
"""
curator/approve.py — human review action. The ONLY way a pending proposal
moves out of pending/. Nothing in HERMES calls this automatically.
"""
import json
import sys
from pathlib import Path

CURATOR_DIR = Path(__file__).resolve().parent
PENDING_DIR = CURATOR_DIR / "pending"
APPROVED_DIR = CURATOR_DIR / "approved"
ARCHIVED_DIR = CURATOR_DIR / "archived"


def approve(proposal_id: str):
    src = PENDING_DIR / f"{proposal_id}.json"
    if not src.exists():
        return {"error": f"no pending proposal with id {proposal_id}"}
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(src.read_text())
    data["status"] = "approved"
    dest = APPROVED_DIR / f"{proposal_id}.json"
    dest.write_text(json.dumps(data, indent=2))
    src.unlink()
    return {"moved": proposal_id, "to": "approved"}


def reject(proposal_id: str):
    src = PENDING_DIR / f"{proposal_id}.json"
    if not src.exists():
        return {"error": f"no pending proposal with id {proposal_id}"}
    ARCHIVED_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(src.read_text())
    data["status"] = "archived"
    dest = ARCHIVED_DIR / f"{proposal_id}.json"
    dest.write_text(json.dumps(data, indent=2))
    src.unlink()
    return {"moved": proposal_id, "to": "archived"}


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("approve", "reject"):
        print("usage: approve.py approve|reject <id>", file=sys.stderr)
        sys.exit(2)
    fn = approve if sys.argv[1] == "approve" else reject
    print(json.dumps(fn(sys.argv[2]), indent=2))
