# HERMES v1.0.0 — release notes (DRAFT)

**Status: draft, not tagged.** This file is prepared so the tag is a one-step
action once the remaining human-gated items clear (V1_CHECKLIST §7: demo video,
first external user, their friction folded back). Fill the date and cut the tag
when those are done. Nothing here should be treated as released until the tag
exists.

## What v1.0 is

A personal, multi-model autonomous capability platform shipped as a Claude Code
plugin. One orchestrator (Apollo) routes every request through a prompt-proof
7-layer security gate and a human-gated self-improvement loop. Subsystem set is
frozen (DECISIONS.md, STANDING 2026-07-05): Apollo, brain, meta (policy +
security), Mnemos, Clio, Curator, ReasoningBank, Cron, Delegation, Fetcher,
Connect, integrations. NYX (Tier 3) is deliberately out of scope until NYX
exists.

## Hardening completed for v1.0 (post-freeze)

- **Boundary contracts (§2).** Five dataclasses at the subsystem seams —
  `Task`, `DelegationPlan`, `SecurityDecision`, `MemoryEntry`, `ExecutionResult`
  in `meta/contracts.py` (a pure stdlib leaf). Three public interfaces pinned by
  contract tests so internals can be refactored without breaking callers:
  `gate.check(request) -> SecurityDecision`,
  `mnemos.search(query) -> list[MemoryEntry]`,
  `dispatch_task(task) -> ExecutionResult`.
- **Polish (§3).** Dead-code swept (tree clean; the one orphaned function kept
  as deliberate API and pinned with a test); error messages made actionable
  (e.g. vault-write retry exhaustion now says what to do); execution trace
  extended to answer *what decision / which tier / which model / how long*, and
  Clio can slice the trace by any of those fields.
- **Fresh-install friction removed (§5).** README Setup now includes the
  `pip install -r requirements.txt` step and documents the pre-deps C6-guard
  behavior; `HERMES.local.md.example` module lists reconciled with
  `.claude-plugin/plugin.json`; test-count claims resynced everywhere (174).
- **Dogfood capture (§6).** The two robustness bugs found 2026-07-05 routed
  through Curator's real pipeline; three normal-use workflow walkthroughs with
  real output in `docs/WORKFLOWS.md`.

## Test suite

174 tests green (172 pass + 2 environment-conditional skips by design). Verify
on the actual release commit before tagging (§4 tag-time re-check).

## Known limitations carried into v1.0 (unchanged, documented)

- Mnemos v2 "semantic" search is a deterministic hashing vectorizer, not a real
  embedding model; semantic-only hits are capped at LOW confidence. See README.
- Tier-substitution safety (SKILL.md "never silently substitute tiers") is
  enforced at the prompt level with a single-turn behavioral proof; multi-turn /
  prompt-injection robustness is a named open item (DECISIONS.md D4).
- SQLite reliability depends on the filesystem (WAL→DELETE fallback + write
  canary); verify before putting the vault on a network/synced drive.

## Still open before the tag (human/calendar-gated)

- 2-week actively-try-to-break-it daily-use window (§6 item 1).
- Demo video (§7).
- First external (non-author) install + run, and their friction folded back
  into §5 (§7).
- Re-run the suite on the release commit; confirm `EXTRACTION_COVERAGE.md` rows
  still true at tag time (§4).
