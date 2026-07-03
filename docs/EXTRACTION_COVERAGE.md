# Extraction coverage — all 58 source folders vs. the code

Verified 2026-07-03 against `HERMES/Extractions/` (58 folders; the zips in
`Documents/Claude/Skills/` are the same corpus). Question answered: *is every
extraction's use case implemented in HERMES, and where?* Duplicate use cases
are collapsed per the "skip similar" rule and marked ⏭.

**Legend:** ✅ implemented (patterns live in code) · 📦 installed & used as-is
(official/audited skills — see D3) · 📖 reference (patterns absorbed into
design, no dedicated module needed) · ⏭ skipped (duplicate use case, named
survivor covers it) · 🚫 excluded by design (documented decision) · ⚠️ the
one genuine open gap.

| # | Extraction | Use case | Status → where in HERMES |
|---|---|---|---|
| 1 | autoresearch (Karpathy) | overnight autonomous loop | ✅ `delegation/agenda.py` (program.md pattern → durable agenda + resume) + `cron/` |
| 2 | ruflo (claude-flow) | ReasoningBank #80, HNSW #81 | ✅ `reasoningbank/bank.py`, `mnemos/hnsw_index.py` (M=16, efC=200, cosine) |
| 3 | hermes-agent | P03/P05/P08/P12/P16/P18/P20 | ✅ curator, mnemos store (WAL/FTS5/retry), 7 security layers, think_scrubber |
| 4 | SuperClaude_Framework | SelfCorrectionEngine #153 | ✅ `curator/` 6-category taxonomy, MD5 dedup, prevention rules |
| 5 | letta | sleeptime consolidation, compaction | ✅ `mnemos/dream.py` + tick scheduling |
| 6 | mem0 | hybrid memory scoring (RRF) | ✅/⚠️ deliberate deviation: tiered-confidence (A/B/C) instead of RRF weights — documented in hybrid_search |
| 7 | agentmemory | hybrid search + confidence | ✅ `mnemos/hybrid_search.py` |
| 8 | mempalace | memory benchmark targets | ✅ `mnemos/benchmark.py` |
| 9 | codebase-memory-mcp | RAM-first 3-tier search; C++ turbo | ✅ hybrid_search (BM25→regex→semantic) + `integrations/turbo_memory.py` |
| 10 | claude-code-leaked | hook protocol, compaction, SSRF guard | ✅ `hooks/verify.sh`, `meta/security/url_safety.py`, Apollo §5/§7 discipline |
| 11 | claude-code-main | QueryEngine fallback, CostTracker, autoDream | ✅ `brain.py` tiers, `clio/tracker.py`, `mnemos/dream.py` |
| 12 | claude-code-main-v2 | same family, newer | ✅ same modules |
| 13 | claw-code-ultraworkers | worker cap, RecoveryLedger, PolicyEngine | ✅ dispatch MAX_CHILDREN=3, agenda stall ledger, Apollo routing table |
| 14 | claude-skills-main | C-level handoff, compound plugins | ✅ agenda resume prompt (CONTEXT/CONSTRAINT/CRITERIA/CONTINUE); composable sub-skills |
| 15 | claude-task-master | task decomposition | ✅ `skills/tasks/` |
| 16 | claude-usage-meter | token tracking | ✅ `clio/tracker.py` (codeburn read-from-disk approach) |
| 17 | codeburn | 18-tool disk-based token tracking | ✅ `clio/tracker.py` |
| 18 | tavily-mcp | search API shape | ✅ `fetcher/fetch.py` |
| 19 | firecrawl-mcp | scrape/format params | ✅ `fetcher/fetch.py` |
| 20 | mcp-playwright | SAFE_MODE action gating | ✅ `fetcher/fetch.py` SAFE_MODE |
| 21 | browser-harness | fetch caps | ✅ `fetcher/fetch.py` MAX_BYTES/redirect caps |
| 22 | modelcontextprotocol | MCP spec | ✅ `connect/mcp_client.py` + `oauth_pkce.py` |
| 23 | chrome-devtools-mcp | browser MCP server | 📖 attachable via Connect when configured; no bundled server |
| 24 | ollama | local inference | ✅ `ollama_client.py` + embedder `ollama` backend |
| 25 | skills-main-anthropic | docx/pdf/pptx/xlsx + design skills | 📦 installed at `~/.claude/skills/` (9 skills), routed by `skills/documents` + create flow |
| 26 | ui-ux-pro-max | design intelligence (styles/palettes/UX) | 📦 installed (7 skills incl. slides/brand/design-system), wired in `skills/webdev` |
| 27 | ui-ux-pro-max-skill | same repo, second copy | ⏭ duplicate of #26 |
| 28 | dyad | full-stack app gen | 📖 design-system-first pipeline in `skills/webdev`; full generator deliberately not cloned (Invariant #4) |
| 29 | open-design | design systems | 📖 `skills/webdev` pattern source |
| 30 | impeccable | UI polish passes | 📖 webdev QA/polish step |
| 31 | design-extract | design-token extraction | 📖 token seam = `integrations/webdev.py` tokens; auto-extractor not needed yet |
| 32 | taste-skill | anti-slop frontend taste | ⏭ duplicate use case — ui-ux-pro-max + frontend-design cover it (optional extra install) |
| 33 | repomix | repo packing + 6 reviewer agents | ✅ `integrations/repopack.py` (pack + 6 lenses fanned via delegation) |
| 34 | superpowers | parallel dispatch, TDD, brainstorm→plan | ✅ `delegation/dispatch.py`, `prompts/tool.md`, `prompts/plan.md` |
| 35 | gstack | layered injection defense, autoplan | ✅ `meta/security/` 7 layers (own set), `prompts/plan.md`; BERT/ONNX layers not adopted (scope) |
| 36 | spec-kit | spec-first development | ✅ `prompts/tool.md` T1 + `prompts/plan.md` |
| 37 | mattpocock-skills | TS workflow guardrails | 📖 `prompts/tool.md` / webdev conventions |
| 38 | everything-claude-code | GateGuard read-before-edit | ✅ platform enforces Read-before-Edit; `meta/security/gate.py` for the rest |
| 39 | awesome-claude-code | playbook | 📖 Apollo design reference |
| 40 | claude-code-best-practice | memory/architecture decisions | 📖 Mnemos design reference |
| 41 | awesome-claude-skills | Composio catalog | ✅ `integrations/composio.py` (sandboxed ledger) |
| 42 | ai-agents-for-beginners | agent fundamentals | 📖 reference only |
| 43 | awesome-llm-apps | cross-domain app patterns | 📖 reference only |
| 44 | Flowise | flow orchestration (BFS engines) | 📖 Apollo routing/policy design; LangGraph-style engine not needed on Path C |
| 45 | langflow | visual flow builder | 📖 reference only |
| 46 | langchain | orchestration backbone | 🚫 dropped by Phase 3 decision — "No LangChain in core" |
| 47 | agentic-inbox | email agent pipeline | 📖 Connect connector pattern (build when an email connector is actually wanted) |
| 48 | ragflow | RAG parsing/chunking | 📖 mnemos/fetcher chunking reference |
| 49 | notebooklm-py | vault synthesis + audio | ✅ `integrations/notebooklm.py` (opt-in, documented API risk) |
| 50 | claude-video | video download/transcribe | ✅ `integrations/media.py` |
| 51 | claude-watch | /watch structured notes | ✅ `integrations/media.py` |
| 52 | cli-develop (Supabase) | db module | ✅ `integrations/db/store.py` |
| 53 | open-webui | LLM web frontend | 🚫 NYX (Stage 6) reference — out of scope by decision |
| 54 | marketingskills | content strategy | ✅ `prompts/content.md` (strategy depth stays pattern-reference) |
| 55 | career-ops | job-search/application agents | ⏭ use case covered by `prompts/content.md` T3 (career tailor); full multi-agent job pipeline skipped as duplicate content-use-case |
| 56 | graphify | codebase → knowledge graph | ⚠️ **the one genuine open gap** — the v1 "synapse" use case. Nearest today: repopack (whole-repo review) + Mnemos search. Build decision deferred: opt-in Stage 5 item if real need appears |
| 57 | Claude source `src` analysis artifacts | platform pattern corpus | ✅ distilled in `CC_SRC_PATTERNS.md`, consumed across all modules |
| 58 | Extractions/ misc analysis folders (`*_PATTERNS.md` only) | analysis, not runtime | 📖 by definition |

## Bottom line

- **Implemented or installed:** 38 of 58.
- **Reference-only by design** (patterns absorbed, no module warranted): 13.
- **Skipped as duplicate use case** (named survivor exists): 3 (#27, #32, #55).
- **Excluded by documented decision:** 2 (langchain, open-webui/Stage 6).
- **Genuine open gap:** 1 — **graphify / codebase knowledge-graph (synapse)**.
  Everything else from the corpus has a home. If the graph need becomes real,
  it enters Stage 5 as `integrations/synapse.py` with graphify's
  detect→extract→graph→cluster pipeline as the pattern source.

*Keep this table honest: when a new extraction lands or a module is built or
retired, update the row in the same change.*
