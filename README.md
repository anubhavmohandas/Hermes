# HERMES

**Hybrid Engine for Research, Memory, Execution & Synthesis**

A personal, multi-model autonomous capability platform built as a Claude Code plugin. Every request routes through a single orchestrator, passes through a security gate that a prompt cannot override, and feeds a self-improvement loop that never applies its own suggestions without a human approving them first.

Built by [Anubhav Mohandas](https://github.com/anubhavmohandas), grounded in 1,420 architectural patterns extracted from 56 production repositories — reimplemented fresh, not copied.

---

## Status

**Phase 3A and 3B are built and tested. Phase 3C has not started.**

| Phase | Scope | Status |
|---|---|---|
| 3A | Apollo orchestration, `brain.py` tier router, 7-layer security gate, Mnemos v1 (SQLite WAL+FTS5), Clio token tracking | ✅ Built, tested |
| 3B | Mnemos v2 (HNSW + 3-tier hybrid search), Curator v1 (mistake capture + human-gated proposals), ReasoningBank (reward-scored task memory), Dream consolidation | ✅ Built, tested |
| 3C | Cron + Delegation, Fetcher (Tavily/Firecrawl/Playwright), Connect (MCP client, OAuth) | ⬜ Not started |
| 3D | Full security audit, benchmarks, NYX Tier 3 fallback | ⬜ Not started |

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
| **Dream** | On-demand consolidation pass, lock-protected against concurrent runs. Not yet scheduled automatically — that lands with Cron in Phase 3C. |

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

**SQLite reliability depends on the filesystem.** Mnemos' WAL-mode store has failed with `disk I/O error` on at least one sandboxed/FUSE-mounted filesystem during development, while working correctly on a real local disk with the identical, unmodified code. `store.py` falls back to `DELETE` journal mode if `WAL` fails to initialize, and `hybrid_search.py` degrades to semantic-only retrieval if the SQLite-backed tiers are unavailable — but if your vault path ends up on a network drive or synced folder (Dropbox, OneDrive, iCloud Drive), verify it actually works before depending on it.

## Security constraints — non-negotiable

- Sensitive data (CVEs, recon output, pentest notes, HERMES/SAGE/NYX internals) routes to Tier 1 or Tier 2 only — never Tier 3, regardless of availability or cost.
- HERMES never auto-applies its own suggestions. Curator proposals require explicit human approval via `curator/approve.py`.
- No executable code is copied from any analyzed repository — patterns only, reimplemented fresh.

## License

MIT — see [LICENSE](LICENSE).
