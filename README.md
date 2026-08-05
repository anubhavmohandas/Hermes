# HERMES

**Hybrid Engine for Research, Memory, Execution & Synthesis**

A personal, multi-model autonomous capability platform built as a Claude Code plugin. Every request routes through a single orchestrator, passes through a security gate that a prompt cannot override, and feeds a self-improvement loop that never applies its own suggestions without a human approving them first.

Built by [Anubhav Mohandas](https://github.com/anubhavmohandas), grounded in 1,420 architectural patterns extracted from 58 production repositories — reimplemented fresh, not copied.

---

## Status

**Stages 0–5 are built and unit-tested — 198 tests green (196 pass + 2 environment-conditional skips by design if `hnswlib`/`numpy` aren't installed).** Stage 0 is proven end-to-end on real disk: one genuine request has flowed through the full loop — route → cross-process memory → reward retrieval → human-gated Curator approval (evidence kept locally in `logs/proof_gate0.md` — audit records stay out of the repo). The `PreToolUse` security gate (`hooks/verify.sh`) is installed and live-verified as of 2026-07-05 — confirmed via `/hooks` in a real Claude Code session (matcher `(all)`, plugin `hermes@hermes`) and via real blocked tool calls (`sudo`, SSRF to the cloud metadata IP via `curl`/`nc`, decimal-encoded and variable-obfuscated IP forms) each producing a matching, timestamp-correlated entry in `logs/reflexion_seed.json` — not just a unit test. Stages 1–5 beyond the gate itself are proven at the component level; the Stage 3 external-integration paths were exercised live on real infrastructure 2026-07-05 — the then-current Tier 2 backend, real Tavily key, real `@modelcontextprotocol/server-filesystem` handshake (evidence kept locally in `logs/proof_gate4.md`). Tier 2 has since been swapped to the NVIDIA API (2026-07-16) and its live chat path is still UNVERIFIED: attempted 2026-08-05 against the configured key and the API returned `401 Unauthorized` on `/v1/chat/completions`, so no Tier 2 completion has ever round-tripped. The same attempt found that `/v1/models` — the old readiness probe — answers HTTP 200 with no credentials at all, meaning `status()` had been reporting `reachable: true` for a key that cannot infer; the probe now issues a real 1-token completion instead, so `tier2_ready` reflects the path Apollo actually gates. Autonomy paths (Cron/Delegation under real unattended load) remain proven at the component level only. NYX (Stage 6) is deliberately out of scope: NYX doesn't exist yet.

| Stage | Scope | Status |
|---|---|---|
| 0 | Prove & package: `requirements.txt`, import-guarded Tier C, `test_hermes.py`, clean tree, one real end-to-end request on real disk | ✅ Proven (real disk; loop closed once with human gate) |
| 1 (3A) | Apollo orchestration, `brain.py` tier router, 7-layer security gate, Mnemos v1 (SQLite WAL+FTS5), Clio token tracking | ✅ Built, unit-tested · orchestrator routing behaviorally proven live, 10/10 real `claude -p` cases, real CLI host, `logs/proof_gate2.md` (Gate 2 closed 2026-07-11 — proxy limitation noted there: model was pointed at its own routing table, not tested on blind ambiguous input) |
| 2 (3B) | Mnemos v2 (HNSW + 3-tier hybrid search), Curator v1 (human-gated proposals), ReasoningBank (reward-scored task memory), Dream consolidation | ✅ Built, unit-tested |
| 3 (3C) | Cron (durable SQLite scheduler, `.tick.lock`, 3-min interrupt, Mnemos write-back), Delegation (≤3 children, forbidden-tool restriction), Fetcher (Tavily/Firecrawl, SAFE_MODE, SSRF-every-hop), Connect (native MCP client + capability negotiation + PKCE OAuth) | ✅ Built, unit-tested · Tier-2/Tavily/MCP live paths proven on real infra 2026-07-05 (Tier 2 was local Ollama then; now the NVIDIA API — live path unverified since the swap); 6 failure modes tested and fail closed, two CLI robustness bugs found and fixed same session; Apollo's "never silently substitute tiers" rule confirmed live under 3 real Tier-2-outage cases including one adversarial-pressure case (`logs/proof_gate4.md`, `logs/proof_failuremode.md`, `logs/proof_apollo_tier_fallback.md`, all local) — real-daemon-kill, genuinely-revoked-key, and multi-turn/jailbreak robustness of the tier rule remain untested |
| 4 (3D) | Repeatable 7-layer audit, Clio benchmark baseline, Tier-3 routing guard (2nd sensitivity check + EU/US jurisdiction), D1 interactive approval tokens, streaming think-block scrubber, upstream drift tracker | ✅ Built, unit-tested |
| 5 | Laconic token-reduction (per-turn hook + bulk-text compress), Occam lazy-minimal-code mode (hook-enforced ladder, lite/full/ultra + review/audit/debt satellite skills), opt-in breadth each with a fallback: db (Supabase/SQLite + migrations), webdev, media, kanban, turbo memory (C++/NumPy/Python), NotebookLM, Composio | ✅ Built, unit-tested (opt-in, each with fallback) |
| 6 | NYX integration | ⬜ Out of scope — NYX not built yet |

## Architecture

```
User → Apollo (orchestrator) → brain.py (tier check) → [security hook, always fires] → sub-skill → self-improvement log → output
```

Nothing bypasses Apollo. Nothing bypasses the security gate — it's a `PreToolUse` hook registered at the platform level, not a prompt instruction, so it can't be talked around.

| Module | What it does |
|---|---|
| **Apollo** (`SKILL.md`) | Master router. Classifies intent, confirms model tier before routing, runs a verification pass on every output. |
| **Create flow** (`skills/create` → `webdev` / `documents` / `research` / `tasks`) | Deliverable orchestrator. When you ask for something to be *made* — a website, app, report, deck, spreadsheet, research brief, or task plan — it runs an intake interview, confirms the brief, routes to the matching sub-skill (webdev for sites/apps, documents for DOCX/PDF/XLSX/PPTX, research for search-backed briefs, tasks for decomposition), verifies the output exists, and logs it to Mnemos. |
| **brain.py** | Deterministic (not LLM-based) sensitivity classification and 3-tier model routing. |
| **meta/security/** | 7 independent defense-in-depth layers: write denylist, path traversal, SSRF prevention, skill static analysis, dangerous-command gate, pre-exec binary scanner, secret redaction. |
| **Mnemos** | Memory. v1 is SQLite WAL+FTS5 lexical search. v2 adds a 3-tier hybrid retrieval pipeline (BM25 → regex → HNSW semantic). |
| **Clio** | Token/cost tracking, read from disk — no proxy or request interception. |
| **Curator** | Captures failures into a deduplicated, recurrence-counted taxonomy and proposes fixes. Proposals sit in `~/.claude/hermes/curator/pending/` until a human explicitly approves or rejects them via `curator/approve.py`. Nothing auto-applies, ever. |
| **ReasoningBank** | Stores `{task, approach, outcome, reward, critique}` per completed task; retrieves the top-scoring past approaches (reward > 0.8) for similar new tasks. |
| **Dream** | On-demand consolidation pass, lock-protected against concurrent runs. Now schedulable via Cron (`cron/scheduler.py add dream "python3 mnemos/dream.py" --daily 03:30`). |
| **Cron** (`cron/scheduler.py`) | Durable SQLite scheduler — `.tick.lock` (mtime-based staleness), per-job 3-minute hard interrupt, every completed run written back to Mnemos so results are retrievable next session. Commands classified through `approval.py` at add- and run-time; approval-tier commands are refused (unattended = no one to approve). Hosted under launchd (`hooks/com.hermes.cron.plist.template`); Cowork can't host it (Invariant #7). |
| **Delegation** (`delegation/dispatch.py`) | Sub-agent fan-out capped at 3 concurrent children. `TaskStop`/`AskUserQuestion`/`EnterPlanMode`/`ExitPlanMode` are stripped from every child unconditionally; overnight children get an observation-only tool set. |
| **Fetcher** (`fetcher/fetch.py`) | Live web access with SSRF checks on every redirect hop, SAFE_MODE (GET-only, byte-capped, TLS-verified), and key-gated Tavily/Firecrawl search that never fabricates results. Fetched content is marked untrusted and secret-scrubbed. |
| **Connect** (`connect/`) | Native MCP stdio client with enforced capability negotiation + `X-Agent-Id` provenance, and an OAuth 2.1 PKCE (S256-only) helper. Server commands run through the same approval gate as everything else. |
| **Tier-3 guard** (`tier3.py`) | Availability-only fallback selection with an independent second sensitivity check, Chinese-API exclusion, and EU/US jurisdiction filter (fails closed on unknown jurisdiction). Selects; never dispatches. |
| **Approval tokens** (`meta/security/approval_token.py`) | D1 resolution: a single-use, command-bound, 300s token lets a human approve one specific dangerous command through the otherwise fail-closed hook. |
| **Laconic** (`meta/laconic.py`, `integrations/laconic_compress.py`) | Token-reduction: a per-turn hook (flag-file mode toggle, auto-clarity override) for live-session brevity, plus a deterministic stopword-drop compressor for bulk text before a Tier 2 job. |
| **Occam** (`meta/occam.py`, `skills/occam*`) | Minimal-code behavioral mode: enforces a "lazy ladder" on every coding task — does this need to exist (YAGNI) → reuse what's in the codebase → stdlib → native platform feature → installed dep → one line → only then new code. Hook-wired at `SessionStart` (full ruleset), `UserPromptSubmit` (per-turn reminder), and `SubagentStart` (propagates to subagents). Ships five satellite skills — see the Occam family below. |
| **Opt-in integrations** (`integrations/`) | db, webdev, media, kanban, turbo memory, NotebookLM, Composio — each independently installable with a verified fallback, none on the critical path. |

## Behavioral modes — Laconic & Occam

Two independent, reversible output modes. Both persist state as a flag file under `$CLAUDE_CONFIG_DIR` (default `~/.claude`) and are re-asserted by a hook every turn, so they survive long sessions instead of decaying like a one-time instruction. `hooks/hermes_statusline.sh` renders a `[OCCAM]` / `[LACONIC]` badge for whichever is active — add it to your `settings.json` `statusLine` once (plugins can't set that key themselves; the SessionStart hook nudges you).

**Laconic** governs *how much is said*. Opt-in: say "go laconic" / "be brief" / "less tokens" to activate, "stop laconic" / "normal mode" to turn off. While active, every response is compressed — no preamble, no postamble, code/diff first. It auto-suspends for one turn when the content is safety-critical (destructive command, security warning, user confusion), then resumes. `meta/laconic.py` also exposes a separate bulk-text compressor (`can_compress` / `validate_compression`) with a sensitive-path denylist and structural integrity checks, used to shrink files before a Tier 2 job.

**Occam** governs *how much is built*. On by default at level `full`; switch with `/occam lite|full|ultra`, off with "stop occam" / "normal mode". It channels a lazy senior dev: question whether the code needs to exist at all before writing it, prefer deletion over addition, boring over clever, and never add a dependency for what a few lines can do. It never cuts input validation, error handling, security, or accessibility. Levels: `lite` builds what's asked but names the lazier alternative, `full` enforces the ladder (default), `ultra` is the YAGNI extremist that challenges the requirement itself. Deliberate shortcuts are left as `occam:` comments naming the ceiling and upgrade path.

The Occam family (one-shot skills, all read-only):

| Skill | What it does |
|---|---|
| `/occam-review` | Reviews the current diff exclusively for over-engineering — reinvented stdlib, unneeded deps, speculative abstractions. One line per finding: location, what to cut, what replaces it. Complements a correctness review; this one only hunts complexity. |
| `/occam-audit` | Same hunt, whole repo instead of a diff: a ranked list of what to delete, simplify, or replace with stdlib/native equivalents. |
| `/occam-debt` | Harvests every `occam:` comment in the codebase into a debt ledger, so deliberate shortcuts get tracked instead of rotting into "later means never". |
| `/occam-gain` | Shows the source project's published benchmark scoreboard for the lazy-ladder approach (less code, less cost, more speed). Explicitly not a measurement of this repo. |
| `/occam-help` | Quick-reference card for all Occam modes, levels, and commands. |

## Model routing

| Tier | Target | When |
|---|---|---|
| 1 | Claude API | Default. Mandatory for sensitive data — CVEs, recon, pentest notes, HERMES/SAGE/NYX internals. |
| 2 | NVIDIA API | Bulk/cost-sensitive tasks, non-sensitive only (remote cloud API — data leaves the machine). |
| 3 | NYX fallback (EU/US only) | Availability fallback only. Never routes sensitive data, regardless of cost or availability. |

**Permanently excluded, no opt-in, no exceptions:** Kimi (Moonshot AI), GLM (Zhipu AI), MiMo (Xiaomi), MiniMax, DeepSeek. Every tier is a remote API now, so the exclusion applies on all tiers — including DeepSeek-family models served through the NVIDIA API.

## Setup

```bash
cp HERMES.local.md.example HERMES.local.md
# edit HERMES.local.md: set NVIDIA_MODEL to your NVIDIA API model id
# export NVIDIA_API_KEY=<your key from build.nvidia.com>

# Tier C (semantic retrieval) needs two third-party deps; everything else is
# stdlib-only. Install them before relying on Mnemos v2 / ReasoningBank:
pip install -r requirements.txt

python3 test_hermes.py   # full suite: green (2 by-design skips)
```

Order matters for the test suite: run it *after* `pip install`. **Before** the
deps are installed, the suite intentionally reports **one failure** —
`TestActiveModulesProvablyRun.test_active_modules_runtime_deps_are_met`. That is
not a bug; it is the C6 guard enforcing "a module the manifest calls *active*
must provably run." `mnemos-v2`/`reasoningbank` are active and need `hnswlib`, so
the guard fails until you install requirements (or move those modules to
`modules.offline` in `.claude-plugin/plugin.json`). The Tier-C behavior tests
themselves skip cleanly pre-deps; only the guard fails, and it goes green the
moment the deps are present.

`HERMES.local.md` is git-ignored on purpose — it carries machine-specific config and is never meant to be committed.

Install as a Claude Code plugin via `.claude-plugin/plugin.json`, which registers `SKILL.md` as the entry point and `hooks/verify.sh` as a `PreToolUse` hook. The hook commands use `${CLAUDE_PLUGIN_ROOT}`, so the plugin resolves its own paths — no manual path editing after install.

## Known limitations — read before trusting retrieval quality

**Mnemos v2's "semantic" search is not backed by a real embedding model.** `mnemos/embedder.py` is a deterministic hashing-trick bag-of-words/char-n-gram vectorizer — it catches lexical and substring overlap, not paraphrase or conceptual similarity. It was benchmarked at 0.933 recall@5 on a hand-labeled corpus, but that corpus was constructed with vocabulary overlap between queries and relevant documents; it does not demonstrate semantic generalization. Retrieval confidence is capped at `LOW` for semantic-only hits in `hybrid_search.py` for exactly this reason. A real embedding model is available as the opt-in `nvidia` backend (NVIDIA API `nv-embedqa-e5-v5`, `HERMES_EMBEDDER=nvidia`) — `hnsw_index.py` and `hybrid_search.py` don't need to change.

**SQLite reliability depends on the filesystem.** Mnemos' WAL-mode store has failed with `disk I/O error` on at least one sandboxed/FUSE-mounted filesystem during development, while working correctly on a real local disk with the identical, unmodified code (confirmed 2026-07-04: a two-process write/retrieve passes on real local APFS disk — the failures were the FUSE-mounted view only). `store.py` falls back to `DELETE` journal mode if `WAL` fails to initialize, and `hybrid_search.py` degrades to semantic-only retrieval if the SQLite-backed tiers are unavailable — but if your vault path ends up on a network drive or synced folder (Dropbox, OneDrive, iCloud Drive), verify it actually works before depending on it.

## Security constraints — non-negotiable

- Sensitive data (CVEs, recon output, pentest notes, HERMES/SAGE/NYX internals) routes to **Tier 1 only** — never Tier 2, never Tier 3, regardless of availability or cost. Tier 2 stopped being a valid destination for sensitive work when it became the remote NVIDIA API: the old "Tier 1 or Tier 2" rule was sound only while Tier 2 was local Ollama and the data never left the machine. `meta/policy.get_tier()` has enforced sensitive→Tier 1 since that swap; this line described the retired policy until 2026-08-05. The Tier-3 guard (`tier3.py`) re-runs the sensitivity check independently before any fallback route, so two call sites must both fail for sensitive data to leak.
- HERMES never auto-applies its own suggestions. Curator proposals require explicit human approval via `curator/approve.py`; dangerous shell commands require a single-use human-granted approval token; scheduled Cron jobs cannot carry approval-tier commands at all.
- No executable code is copied from any analyzed repository — patterns only, reimplemented fresh. This holds across all 58 source repos, including the newly-merged Fetcher/Connect sources.

## License

MIT — see [LICENSE](LICENSE).
