#!/usr/bin/env python3
"""
curator/approve.py — human review action. The ONLY way a pending proposal
moves out of pending/. Nothing in HERMES calls this automatically.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meta.paths import state_dir  # noqa: E402

# MUST resolve to the same directories curator/propose.py writes to. These were
# repo-relative until 2026-08-05 while propose.py had already moved to
# state_dir() — so every proposal was written to ~/.claude/hermes/curator/pending
# and looked up in the (empty) in-repo one, and the human gate could never be
# used. Any change here changes propose.py too; the pairing is asserted in
# TestCurator.test_approve_and_propose_resolve_to_same_dirs.
PENDING_DIR = state_dir("curator", "pending")
APPROVED_DIR = state_dir("curator", "approved")
ARCHIVED_DIR = state_dir("curator", "archived")
CURATOR_DIR = PENDING_DIR.parent


def _move(proposal_id: str, dest_dir: Path, new_status: str):
    """Write to dest_dir first, THEN attempt to remove src — guards the
    unlink so a failure doesn't crash the caller (matches the pattern
    already established in mnemos/dream.py's release_lock()). Audited
    2026-07-02 (M2): on at least one sandboxed/FUSE-mounted filesystem,
    unlink() can fail even after a successful write, which previously left
    the SAME proposal id sitting in both pending/ and the destination dir
    simultaneously — reproduced live during that audit. This does not break
    dedup (curator/propose.py checks all three dirs before proposing again),
    but it does mean a human browsing pending/ could see something already
    decided. The warning below makes that visible instead of silent."""
    src = PENDING_DIR / f"{proposal_id}.json"
    if not src.exists():
        return {"error": f"no pending proposal with id {proposal_id}"}
    dest_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(src.read_text())
    data["status"] = new_status
    dest = dest_dir / f"{proposal_id}.json"
    dest.write_text(json.dumps(data, indent=2))
    try:
        src.unlink()
    except OSError as e:
        print(f"approve.py: wrote {dest} but could not remove {src} ({e}) — "
              f"proposal now exists in BOTH pending/ and {dest_dir.name}/. "
              f"Safe to ignore for dedup purposes, but delete {src} manually "
              f"so it doesn't show as still-pending.", file=sys.stderr)
        return {"moved": proposal_id, "to": dest_dir.name, "warning": "pending copy not removed, see stderr"}
    return {"moved": proposal_id, "to": dest_dir.name}


def approve(proposal_id: str):
    return _move(proposal_id, APPROVED_DIR, "approved")


def reject(proposal_id: str):
    return _move(proposal_id, ARCHIVED_DIR, "archived")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("approve", "reject"):
        print("usage: approve.py approve|reject <id>", file=sys.stderr)
        sys.exit(2)
    fn = approve if sys.argv[1] == "approve" else reject
    result = fn(sys.argv[2])
    print(json.dumps(result, indent=2))
    # Exit nonzero on a miss so a scripted caller can tell "approved" from
    # "there was nothing by that id" — it printed {"error": ...} and exited 0.
    sys.exit(1 if "error" in result else 0)
