#!/usr/bin/env python3
"""
curator/propose.py — Curator human-gate proposal generator.

Pattern source (reimplemented fresh, no code copied): hermes-agent
skill_provenance.py pattern — Curator proposes, human decides. Nothing in
this file ever auto-applies anything. It only ever WRITES a proposal file
to curator/pending/ for a human to read and act on manually.

Reads curator/reflexion.json (already deduped + recurrence-counted by
consolidate.py) and, for any failure that has recurred (recurrence_count >=
PROPOSAL_THRESHOLD), writes a pending-queue entry in the exact schema from
HERMES_Phase3_Blueprint.docx section 3.2 — IF one doesn't already exist for
that id in pending/, approved/, or archived/ (no duplicate proposals for
the same recurring failure).

proposed_action is a deterministic, category-keyed suggestion — not an LLM
call. It's a starting point for the human to edit, not a finished verdict.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meta.paths import state_dir, state_file  # noqa: E402

# Proposals are the user's pending decisions — runtime state under
# ~/.claude/hermes/ (meta/paths.py), named per item because curator/ holds
# this module's own source alongside them.
REFLEXION_PATH = state_file("curator", "reflexion.json")
PENDING_DIR = state_dir("curator", "pending")
APPROVED_DIR = state_dir("curator", "approved")
ARCHIVED_DIR = state_dir("curator", "archived")
CURATOR_DIR = REFLEXION_PATH.parent

PROPOSAL_THRESHOLD = 2  # recurrence_count >= this triggers a proposal

CATEGORY_ACTION_TEMPLATES = {
    "validation": "Add an explicit validation/existence check before this step runs, so the failure surfaces before it propagates.",
    "dependency": "Verify the dependency (tool/file/service) is actually available before the step that assumes it, with a clear error if it's missing.",
    "logic": "Re-examine the control flow around this task type — the logic itself produced the wrong outcome, not a missing check.",
    "assumption": "Replace the assumption with an explicit check. State plainly what was assumed and verify it before proceeding.",
    "type": "Add a type/shape check at the boundary where this data enters the failing step.",
    "unknown": "Category unclear from the raw failure — needs a human to read the task+failure_mode and classify before a fix can be proposed.",
}


def _existing_ids():
    ids = set()
    for d in (PENDING_DIR, APPROVED_DIR, ARCHIVED_DIR):
        if d.exists():
            for f in d.glob("*.json"):
                ids.add(f.stem)
    return ids


def generate_proposals():
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVED_DIR.mkdir(parents=True, exist_ok=True)

    if not REFLEXION_PATH.exists():
        return {"proposals_written": 0, "reason": "no curator/reflexion.json yet — run consolidate.py first"}

    reflexion = json.loads(REFLEXION_PATH.read_text())
    existing = _existing_ids()
    written = []

    for entry in reflexion:
        if entry["recurrence_count"] < PROPOSAL_THRESHOLD:
            continue
        if entry["id"] in existing:
            continue  # already proposed (pending/approved/archived) — don't duplicate

        proposal = {
            "id": entry["id"],
            "timestamp": entry["last_seen"],
            "category": entry["category"],
            "task": entry["task"],
            "failure_mode": entry["failure_mode"],
            "prevention_rule": entry["prevention_rule"],
            "recurrence_count": entry["recurrence_count"],
            "proposed_action": CATEGORY_ACTION_TEMPLATES.get(entry["category"], CATEGORY_ACTION_TEMPLATES["unknown"]),
            "status": "pending",
        }
        out_path = PENDING_DIR / f"{entry['id']}.json"
        out_path.write_text(json.dumps(proposal, indent=2))
        written.append(entry["id"])

    return {"proposals_written": len(written), "ids": written}


if __name__ == "__main__":
    print(json.dumps(generate_proposals(), indent=2))
