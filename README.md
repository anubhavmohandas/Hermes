# HERMES

**Hybrid Engine for Research, Memory, Execution & Synthesis**

A personal, multi-model autonomous capability platform built as a Claude Code plugin. Every request routes through a single orchestrator, passes through a security gate that a prompt cannot override, and feeds a self-improvement loop that never applies its own suggestions without a human approving them first.

Built by [Anubhav Mohandas](https://github.com/anubhavmohandas), grounded in 1,420 architectural patterns extracted from 58 production repositories — reimplemented fresh, not copied.

---

## Status

**Stages 0–5 are built and unit-tested — 156 tests green (a couple skip until their optional dep — Ollama embeddings, markitdown — is installed).** Stage 0 is proven end-to-end on real disk: one genuine request has flowed through the full loop — route → cross-process memory → reward retrieval → human-gated Curator approval (evidence in `logs/proof_gate0.md`). Stages 1–5 are proven at the component level; proving the autonomy and external-integration paths on live traffic is in progress. NYX (Stage 6) is deliberately out of scope: NYX doesn't exist yet.

| Stage | Scope | Status |
|---|---|---|
| 0 | Prove & package: `requirements.txt`, import-guarded Tier C, `test_hermes.py`, clean tree, one real end-to-end request on real disk | ✅ Proven (real disk; loop closed once with human gate) |
| 1 (3A) | Apollo orchestration, `brain.py` tier router, 7-layer security gate, Mnemos v1 (SQLite WAL+FTS5), Clio token tracking | ✅ Built, unit-tested · orchestrator routing not yet behaviorally tested (Gate 2) |
| 2 (3B) | Mnemos v2 (HNSW + 3-tier hybrid search), Curator v1 (human-gated proposals), ReasoningBank (reward-scored task memory), Dream consolidation | ✅ Built, unit-tested |
| 3 (3C) | Cron (durable SQLite scheduler, `.tick.lock`, 3-min interrupt, Mnemos write-back), Delegation (≤3 children, forbidden-tool restriction), Fetcher (Tavily/Firecrawl, SAFE_MODE, SSRF-every-hop), Connect (native MCP client + capability negotiation + PKCE OAuth) | ✅ Built, unit-tested · live external paths (Ollama/search/MCP) not yet exercised (Gate 4) |
| 4 (3D) | Repeatable 7-layer audit, Clio benchmark baseline, Tier-3 routing guard (2nd sensitivity check + EU/US jurisdiction), D1 interactive approval tokens, streaming think-block scrubber, upstream drift tracker | ✅ Built, unit-tested |
| 5 | Opt-in breadth, each with a fallback: db (Supabase/SQLite + migrations), webdev, media, caveman, kanban, turbo memory (C++/NumPy/Python), NotebookLM, Composio | ✅ Built, unit-tested (opt-in, each with fallback) |
| 6 | NYX integration | ⬜ Out of scope — NYX not built yet |

## Architecture

```
User → Apollo (orchestrator) → brain.py (tier check) → [security hook, always fires] → sub-skill → self-improvement log → output
```

Nothing bypasses Apollo. Nothing bypasses the security gate — it's a `PreToolUse` hook registered at the platform level, not a prompt instruction, so it can't be talked around.

| Module | What it does |
|---|---|
| **Apollo** (`SKILL.md`) | Master router. Classifies intent, confirms model tier before routing, runs a verification pass on every output. |
| **brain.py** | Deterministic (not LLM-based) sensitivity classification and 3-tier model routing. |
| **meta/security/** | 7 independent defense-in-depth layers: write denylist, path traversal, SSRF prevention, skill static analysis, dangerous-command gate, pre-exec binary scanner, secret redaction. |
| **Mnemos** | Memory. v1 is SQLite WAL+FTS5 lexical search. v2 adds a 3-tier hybrid retrieval pipeline (BM25 → regex → HNSW semantic). |
| **Clio** | Token/cost tracking, read from disk — no proxy or request interception. |
| **Curator** | Captures failures into a deduplicated, recurrence-counted taxonomy and proposes fixes. Proposals sit in `curator/pending/` until a human explicitly approves or rejects them. Nothing auto-applies, ever. |
| **ReasoningBank** | Stores `{task, approach, outcome, reward, critique}` per completed task; retrieves the top-scoring past approaches (reward > 0.8) for similar new tasks. |
| **Dream** | On-demand consolidation pass, lock-protected against concurrent runs. Now schedulable via Cron (`cron/scheduler.py add dream "python3 mnemos/dream.py" --daily 03:30`). |
| **Cron** (`cron/scheduler.py`) | Durable SQLite scheduler — `.tick.lock` (mtime-based staleness), per-job 3-minute hard interrupt, every completed run written back to Mnemos so results are retrievable next session. Commands classified through `approval.py` at add- and run-time; approval-tier commands are refused (unattended = no one to approve). Hosted under launchd (`hooks/com.hermes.cron.plist.template`); Cowork can't host it (Invariant #7). |
| **Delegation** (`delegation/dispatch.py`) | Sub-agent fan-out capped at 3 concurrent children. `TaskStop`/`AskUserQuestion`/`EnterPlanMode`/`ExitPlanMode` are stripped from every child unconditionally; overnight children get an observation-only tool set. |
| **Fetcher** (`fetcher/fetch.py`) | Live web access with SSRF checks on every redirect hop, SAFE_MODE (GET-only, byte-capped, TLS-verified), and key-gated Tavily/Firecrawl search that never fabricates results. Fetched content is marked untrusted and secret-scrubbed. |
| **Connect** (`connect/`) | Native MCP stdio client with enforced capability negotiation + `X-Agent-Id` provenance, and an OAuth 2.1 PKCE (S256-only) helper. Server commands run through the same approval gate as everything else. |
| **Tier-3 guard** (`tier3.py`) | Availability-only fallback selection with an independent second sensitivity check, Chinese-API exclusion, and EU/US jurisdiction filter (fails closed on unknown jurisdiction). Selects; never dispatches. |
| **Approval tokens** (`meta/security/approval_token.py`) | D1 resolution: a single-use, command-bound, 300s token lets a human approve one specific dangerous command through the otherwise fail-closed hook. |
| **Opt-in integrations** (`integrations/`) | db, webdev, media, caveman, kanban, turbo memory, NotebookLM, Composio — each independently installable with a verified fallback, none on the critical path. |

## Model routing

| Tier | Target | When |
|---|---|---|
| 1 | Claude API | Default. Mandatory for sensitive data — CVEs, recon, pentest notes, HERMES/SAGE/NYX internals. |
| 2 | Local Ollama | Bulk/offline/cost-sensitive tasks. Data never leaves the machine. |
| 3 | NYX fallback (EU/US only) | Availability fallback only. Never routes sensitive data, regardless of cost or availability. |

**Permanently excluded, no opt-in, no exceptions:** Kimi (Moonshot AI), GLM (Zhipu AI), MiMo (Xiaomi), MiniMax, DeepSeek — via API. Open-weight versions of these running locally on Ollama are not excluded; the constraint is about data leaving the machine, not the model itself.

## Setup

```bash
cp HERMES.local.md.example HERMES.local.md
# edit HERMES.local.md: set OLLAMA_MODEL to your local model name
```

`HERMES.local.md` is git-ignored on purpose — it carries machine-specific config and is never meant to be committed.

Install as a Claude Code plugin via `.claude-plugin/plugin.json`, which registers `SKILL.md` as the entry point and `hooks/verify.sh` as a `PreToolUse` hook.

## Known limitations — read before trusting retrieval quality

**Mnemos v2's "semantic" search is not backed by a real embedding model.** `mnemos/embedder.py` is a deterministic hashing-trick bag-of-words/char-n-gram vectorizer — it catches lexical and substring overlap, not paraphrase or conceptual similarity. It was benchmarked at 0.933 recall@5 on a hand-labeled corpus, but that corpus was constructed with vocabulary overlap between queries and relevant documents; it does not demonstrate semantic generalization. Retrieval confidence is capped at `LOW` for semantic-only hits in `hybrid_search.py` for exactly this reason. Swapping in a real local embedding model (e.g. Ollama `nomic-embed-text`) only requires changing `embedder.py` — `hnsw_index.py` and `hybrid_search.py` don't need to change.

**SQLite reliability depends on the filesystem.** Mnemos' WAL-mode store has failed with `disk I/O error` on at least one sandboxed/FUSE-mounted filesystem during development, while working correctly on a real local disk with the identical, unmodified code (confirmed 2026-07-04: a two-process write/retrieve passes on real local APFS disk — the failures were the FUSE-mounted view only). `store.py` falls back to `DELETE` journal mode if `WAL` fails to initialize, and `hybrid_search.py` degrades to semantic-only retrieval if the SQLite-backed tiers are unavailable — but if your vault path ends up on a network drive or synced folder (Dropbox, OneDrive, iCloud Drive), verify it actually works before depending on it.

## Security constraints — non-negotiable

- Sensitive data (CVEs, recon output, pentest notes, HERMES/SAGE/NYX internals) routes to Tier 1 or Tier 2 only — never Tier 3, regardless of availability or cost. The Tier-3 guard (`tier3.py`) re-runs the sensitivity check independently before any fallback route, so two call sites must both fail for sensitive data to leak.
- HERMES never auto-applies its own suggestions. Curator proposals require explicit human approval via `curator/approve.py`; dangerous shell commands require a single-use human-granted approval token; scheduled Cron jobs cannot carry approval-tier commands at all.
- No executable code is copied from any analyzed repository — patterns only, reimplemented fresh. This holds across all 58 source repos, including the newly-merged Fetcher/Connect sources.

## License

MIT — see [LICENSE](LICENSE).
