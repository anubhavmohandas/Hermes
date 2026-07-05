#!/usr/bin/env python3
"""
meta/contracts.py — HERMES v1 boundary contracts (the leaf every subsystem
depends on downward, and that depends on nobody).

V1_CHECKLIST §2. Five dataclasses, one per place a bare dict/tuple currently
crosses a subsystem line. They are *targeted*, not total: internals keep their
dicts, but the moment data leaves a subsystem it takes one of these shapes.
That is what lets an internal be refactored without breaking a caller — the
caller is pinned to the dataclass, not to the dict layout underneath it.

  Task            — a unit of work handed to Delegation (dispatch input)
  DelegationPlan  — a fan-out plan: tasks + the locked concurrency cap
  SecurityDecision— gate.check() verdict (allowed / which layer / why)
  MemoryEntry     — one Mnemos row returned by search()
  ExecutionResult — the outcome of running one task

Placement (architecture freeze, DECISIONS.md STANDING 2026-07-05): this is a
new *file inside the existing, frozen `meta/` subsystem* — exactly the
precedent `meta/policy.py` set the same day. `meta/` is already HERMES's
shared kernel (policy is "the leaf both the orchestrator and its subsystems
depend on"); the boundary contracts are the same nature, so they live beside
it. No new top-level folder, no new subsystem.

Pure leaf: stdlib `dataclasses` + `typing` only. Zero HERMES imports, so there
is no circular-import risk no matter who imports it.

Each dataclass carries the adapters the boundary wrappers use:
  .from_dict() / .from_tuple()  — build the contract from an existing internal
  .to_dict()                    — hand a plain dict back to a caller that still
                                  wants one (JSON output, the CLI, older tests)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Delegation boundary — dispatch(task) -> ExecutionResult
# ---------------------------------------------------------------------------
@dataclass
class Task:
    """A single unit of work handed across the Delegation boundary. `prompt`
    is what a child `claude -p` runs; the rest are the knobs dispatch already
    accepted as loose kwargs, now named on the object that carries them."""
    prompt: str
    async_profile: bool = False          # overnight/unattended: observation-only tools
    timeout_seconds: int = 300
    model: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            prompt=d["prompt"],
            async_profile=bool(d.get("async_profile", False)),
            timeout_seconds=int(d.get("timeout_seconds", 300)),
            model=d.get("model"),
        )


@dataclass
class DelegationPlan:
    """The fan-out plan before anything is spawned. `max_concurrent` is the
    locked ≤3 cap (delegation/dispatch.MAX_CHILDREN) surfaced on the contract
    so a caller can read it without reaching into the module. More tasks than
    the cap queue and drain — they are not rejected."""
    tasks: List[Task] = field(default_factory=list)
    max_concurrent: int = 3
    async_profile: bool = False

    def to_dict(self) -> dict:
        return {
            "tasks": [t.to_dict() for t in self.tasks],
            "max_concurrent": self.max_concurrent,
            "async_profile": self.async_profile,
        }


@dataclass
class ExecutionResult:
    """The outcome of running one task. Mirrors delegation/dispatch._run_child's
    dict exactly (status/output/elapsed_ms) plus the prompt it ran, so the
    dataclass is a drop-in for what dispatch already returns per child.

    `status` vocabulary (unchanged from dispatch.classify_output):
      completed | rate_limited | failed(rc=N) | failed(spawn) | interrupted
      | dry_run | not_dispatched
    """
    status: str
    output: str = ""
    elapsed_ms: int = 0
    prompt: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "completed"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionResult":
        return cls(
            status=d["status"],
            output=d.get("output", ""),
            elapsed_ms=int(d.get("elapsed_ms", 0)),
            prompt=d.get("prompt", ""),
        )


# ---------------------------------------------------------------------------
# Security boundary — gate.check(request) -> SecurityDecision
# ---------------------------------------------------------------------------
@dataclass
class SecurityDecision:
    """The verdict from the 7-layer security gate. Mirrors gate.run_gate's
    (allowed, layer, reason) tuple. `layer` names which layer decided
    ('file_safety', 'approval', 'url_safety', … or 'none' when nothing fired)."""
    allowed: bool
    layer: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_tuple(cls, t) -> "SecurityDecision":
        allowed, layer, reason = t
        return cls(allowed=bool(allowed), layer=layer, reason=reason)


# ---------------------------------------------------------------------------
# Memory boundary — mnemos.search(query) -> list[MemoryEntry]
# ---------------------------------------------------------------------------
@dataclass
class MemoryEntry:
    """One row returned by a Mnemos search. Mirrors mnemos/store.search_messages'
    dict. `memory_type` is one of store.MEMORY_TYPES
    (user | feedback | project | reference)."""
    id: int
    session_id: str
    role: str
    content: str
    created_at: str
    memory_type: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryEntry":
        # session_id is absent from get_session() rows (already scoped to one
        # session); default to "" so the same contract covers both readers.
        return cls(
            id=int(d["id"]),
            session_id=d.get("session_id", ""),
            role=d["role"],
            content=d["content"],
            created_at=d.get("created_at", ""),
            memory_type=d.get("memory_type", "project"),
        )


__all__ = [
    "Task",
    "DelegationPlan",
    "SecurityDecision",
    "MemoryEntry",
    "ExecutionResult",
]
