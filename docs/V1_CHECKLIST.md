# v1.0 release checklist

This is a **release** list, not a feature list. When every box is checked, tag
`v1.0.0`. New capabilities go to the post-1.0 backlog — they do not reopen
this list.

**Ground rule (architecture freeze):** no new top-level folders, no new
subsystems. A feature either fits inside an existing module or it waits for a
real user to force the change. The current subsystem set (Apollo, brain,
meta/security, Mnemos, Clio, Curator, ReasoningBank, Cron, Delegation,
Fetcher, Connect, integrations) is final for v1.0.

Verified baseline at creation (2026-07-03, commit `5d0d3df`):
144/144 tests passing (2 environment-conditional skips by design), clean
tree, ~5.8k production LOC, largest file 409 lines, dependency graph clean
except two inverted imports (listed below).

---

## 1 — Architecture

- [x] Extraction corpus fully dispositioned — 58/58 rows in
      `EXTRACTION_COVERAGE.md` (kept local, untracked since 2026-07-04),
      one deferred gap (graphify) documented
- [ ] Architecture freeze recorded in `DECISIONS.md` (date + rationale)
- [ ] Fix the only two inverted imports — subsystems reaching up into the
      orchestrator for policy calls:
      - `integrations/notebooklm.py:31` (`brain.check_sensitivity`)
      - `meta/security/audit.py:38` (`brain.check_sensitivity` /
        `check_model_allowed` / `get_tier` / `log_request`)
      Fix: move the shared policy functions into a module both can import
      (e.g. `meta/policy.py`); `brain.py` re-exports so callers don't churn.
- [ ] No circular imports (re-run the import scan after the fix above)

## 2 — Domain models & contracts (targeted, not total)

- [ ] Dataclasses at module boundaries only — where dicts cross subsystem
      lines today: `Task`, `DelegationPlan`, `SecurityDecision`,
      `MemoryEntry`, `ExecutionResult`. Internals may keep dicts.
- [ ] Contract tests pinning the public interfaces so internals can be
      refactored without breaking callers:
      `dispatch(task) -> Result`, `mnemos.search(query) -> list[MemoryEntry]`,
      `gate.check(request) -> SecurityDecision`
- [ ] Explicitly **not** doing: strict typing, 100% type coverage, plugin
      systems, another memory layer (per review 2026-07-03)

## 3 — Polish

- [ ] Dead-code sweep (unused functions, commented-out blocks, stale
      `__pycache__` artifacts out of the tree)
- [ ] Naming consistency pass across module public functions
- [ ] Error messages actionable — every raise/refusal says what to do next,
      not just what failed
- [ ] Execution traces answer: what decision, which tier/model, which prompt,
      which memory was retrieved, why a tool was called, how long it took
      (extend Clio logging where gaps are found while dogfooding)

## 4 — Tests & docs

- [x] Full suite green — 144 passed, 2 by-design skips (2026-07-03)
- [ ] Suite still green at tag time (re-run on the release commit)
- [x] README claims match reality — it said "123 tests green" (then briefly
      "156") while the suite runs 144; counts, stage table, and module list
      synced 2026-07-04 (commit d175420, pushed).
- [ ] `docs/` current: DECISIONS.md has the freeze entry,
      EXTRACTION_COVERAGE.md rows (local, untracked) still true at tag time

## 5 — Installation from scratch

- [ ] Fresh clone on a clean machine/venv: `python3 test_hermes.py` passes
      pre-deps (Tier C skips correctly), then `pip install -r
      requirements.txt`, then full pass
- [ ] `HERMES.local.md.example` alone is enough to configure a working setup
- [ ] Plugin installs into a vanilla Claude Code without manual path surgery

## 6 — Dogfood

- [ ] Daily use for 2+ weeks, actively trying to make it fail
- [ ] Every failure captured through Curator (that's what it's for) —
      pending/approved counts reviewed before tagging
- [ ] Example workflows written up from real sessions (3+, in `docs/` or
      README)

## 7 — Release

- [ ] Demo video recorded
- [ ] First external user installed and ran it (not the author)
- [ ] Their first-run friction folded back into §5
- [ ] Tag `v1.0.0`

---

*After the tag: reality decides the roadmap. User-reported problems outrank
any "one more cool idea."*
