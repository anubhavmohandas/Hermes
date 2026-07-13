---
name: goal
description: /goal — the complete HERMES end goal and the ordered, gated roadmap to reach it. End goal = every module reimplemented from all extracted patterns EXCEPT NYX integration (NYX doesn't exist yet). Restates the goal, checks which stage the build is actually in, and names the single next action. Full detail in HERMES_GOAL_Start_to_End.md.
argument-hint: "[ full | status | next | 0 | 1 | 2 | 3 | 4 | 5 ]"
---

# /goal

**THE END GOAL (state this verbatim, do not soften):**
HERMES has *everything* — all ~20 v1-blueprint modules, each reimplemented
fresh from the extracted patterns — **EXCEPT NYX integration.** The corpus is
**58 source repos**, consolidated into a single home at `HERMES/Extractions/`
(merged Jul 3 2026 from `HERMES/Extractions` [46] + `Skills/Extractions` [12],
zero overlap). Includes the Claude Code **leaked + latest source**
(`claude-code-leaked`, `claude-code-main`, `-v2`, `claw-code-ultraworkers`,
distilled into `CC_SRC_PATTERNS.md` — 1,420 patterns), the personal Anthropic
skills repos (`skills-main-anthropic`, `claude-skills-main`), and the
Fetcher/Connect sources (`tavily-mcp`, `firecrawl-mcp`, `mcp-playwright`,
`browser-harness`, `chrome-devtools-mcp`, `modelcontextprotocol`). NYX is not
built yet, so Stage 6 (embedding under `nyx/tools/hermes/`) is deliberately
excluded. Reaching Stages 0 → 5 IS the goal. Patterns only, never copied code.

When the user types `/goal`, Apollo behaves per `$ARGUMENTS`:

- **(no argument)** or **`full`** → print the whole goal + all stages 0–5
  with their one-line exit gates (the block below). This is the default: lay
  out everything that needs doing, in order.
- **`status`** / **`where`** → run the live checks from `/status`, then map
  the real state onto the stage table and answer one question plainly: *which
  stage's exit gate is the first one not yet green?* That is the current
  stage. Name it, show which gate items pass/fail, stop there.
- **`next`** → the single next concrete action only. No roadmap dump.
- **`0`–`5`** → expand just that stage: its Build list + Exit Gate, and
  whether the gate is currently green.

**Hard rules when answering `/goal` (carry verbatim):**
1. Never report a later stage as reachable while an earlier stage's exit gate
   is red. Gates are ordered and non-skippable.
2. Report real state, not aspiration — same discipline as `/status`. If
   `reasoning_seed.jsonl` is empty, Stage 0 is NOT green, no matter what any
   doc claims.
3. This command never *executes* a stage. It states the goal and proposes the
   next action; the human decides and triggers the work. (Invariant #3 —
   HERMES never auto-applies.)
4. NYX is out of scope. If asked about it, say so and point to Stage 6 as
   "future, not part of the goal."

---

## The stages (source of truth: `HERMES_GOAL_Start_to_End.md`)

**Reconciliation:** v1 Ph1=3A=Stage1, Ph2=3B=Stage2, Ph3=3C=Stage3,
Ph4=3D=Stage4, Ph5=Stage5, Ph6=NYX=out of scope. Stage 0 is new: prove +
package what's already built.

- **STAGE 0 — Prove & Package** *(current front line)*
  Build: `requirements.txt` (hnswlib, numpy); import-guard Tier C so a missing
  dep degrades not crashes; `test_hermes.py` (routing, Chinese-API block,
  verify.sh sensitive-block, `sk-ant-` redaction, Curator dedup+gate,
  ReasoningBank reward filter); clean the tree (double `err_8a8b7dab.json`,
  empty test DBs, stale `.dream.lock`); commit the audit fixes + `docs/`; run
  ONE real request end-to-end on real disk.
  **Gate:** `pytest` green from a clean clone with only `requirements.txt`
  installed AND `reasoning_seed.jsonl` has ≥1 real entry AND Mnemos
  write+search passes on real (non-FUSE) disk.

- **STAGE 1 — Core Skeleton** *(v1 Ph1 / 3A — code built)*
  Apollo router, brain.py tier+sensitivity, verify.sh hook, 7 security
  layers, skills/{research,tasks,documents}, Mnemos v1, Clio v1.
  **Gate:** the 3 Phase-1 tests pass inside `test_hermes.py`.

- **STAGE 2 — Memory & Self-Improvement** *(v1 Ph2 / 3B — code built)*
  Mnemos v2 HNSW + 3-tier hybrid search, Curator v1 (human-gate), ReasoningBank
  (reward>0.8 injection), Dream. Tier C is a hashing-trick embedder, NOT
  semantic — do not oversell it (real embedder is Stage 4).
  **Gate:** a mistake in session A yields a `pending/` proposal that survives
  to session B and only moves to `approved/` by explicit human action; a
  reward>0.8 past approach is retrieved before a similar new task.

- **STAGE 3 — Autonomy & Research** *(v1 Ph3 / 3C — NOT started; earns "autonomous")*
  Cron (durable SQLite, `.tick.lock`, 3-min interrupt — keystone), Delegation
  (≤3 children; no TaskStop/AskUserQuestion/EnterPlanMode for sub-agents),
  Fetcher (Tavily/Firecrawl/Playwright, SAFE_MODE), Connect (MCP client, PKCE
  OAuth). Cowork can't host the loop — CLI/launchd only.
  **Gate:** an overnight Cron job completes unattended and writes to Mnemos,
  retrievable next morning; interrupt + lock proven under forced concurrency.

- **STAGE 4 — Hardening** *(v1 Ph4 / 3D — NOT started)*
  Repeatable 7-layer audit; benchmarks in Clio (tokens/tier, latency, recall);
  REAL embedder (Ollama `nomic-embed-text`) behind `embed()`; NYX Tier 3
  fallback with jurisdiction + 2nd sensitivity check (never sensitive data);
  resolve D1 (interactive approval for sudo/force-push/DROP TABLE);
  think-block scrubber; upstream tracker.
  **Gate:** audit findings closed with re-run evidence; benchmark baseline in
  Clio; Tier 3 provably refuses sensitive data in a test.

- **STAGE 5 — Integrations & Create** *(v1 Ph5 — the breadth that makes it "everything")*
  db/ (Supabase), webdev/, media/ (claude-video, /watch), Composio connectors
  (sandboxed, permission-per-connector), C++ turbo memory (Python fallback),
  NotebookLM synthesis (opt-in), Laconic token-reduction mode (built
  2026-07-13), Kanban. Each ships with a fallback.
  **Gate:** each module present with its fallback verified. This completes the
  end goal (everything except NYX).

- **STAGE 6 — NYX** → **OUT OF SCOPE.** Not part of this goal. Revisit only
  once NYX exists.

---

## Invariants (repeat if relevant to the answer)
Nothing bypasses Apollo/verify.sh · sensitive → Tier 1/2 only, Chinese APIs
have no code path · never auto-apply (human gate always) · patterns not code ·
every optional layer degrades gracefully · Cowork can't host the overnight
loop.
