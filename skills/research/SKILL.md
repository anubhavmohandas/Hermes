---
name: hermes-research
description: HERMES research sub-skill. Apollo routes here for search/find/research/look-up requests. Phase 3A backend is the WebSearch tool; Fetcher (Firecrawl + Tavily + Playwright MCP with SAFE_MODE gating) replaces it in Phase 3C. Returns findings + sources + a stated confidence level, and writes the result into Mnemos v1 so it's recallable later.
allowed-tools: WebSearch, Bash, Read
user-invocable: false
---

# skills/research — Research sub-skill

Called by Apollo, not directly by the user.

## What this does in Phase 3A

1. Accept a research query from Apollo (with tier already confirmed — do not
   re-check sensitivity here, Apollo already ran `brain.py check`).
2. Run the query through the `WebSearch` tool. This IS the research backend
   in Phase 3A — there is no Tavily/Firecrawl integration yet.
3. Synthesize: findings, the sources they came from, and an honest confidence
   level (`high` / `medium` / `low` — low if sources conflict or are thin).
4. Write the result into Mnemos v1 so future "what did we find on X" queries
   can recall it:
   `python3 mnemos/store.py write "<session_id>" "assistant" "<findings summary>"`
5. Return `{findings, sources, confidence}` to Apollo.

## What this explicitly does NOT do yet

- No Tavily MCP (session UUID tracking, polling backoff) — Phase 3C.
- No Firecrawl (SAFE_MODE gating, domain filter injection, structured
  extraction) — Phase 3C.
- No Playwright-driven live browsing/screenshotting — Phase 3C.
- No semantic recall of past research (Mnemos v2 HNSW) — Phase 3B. Mnemos v1
  can only find past research by lexical/substring match.

## Extension point (Phase 3C — Fetcher)

When Fetcher lands, replace step 2 above with routing logic:
- Deep/structured extraction → Firecrawl (respect its SAFE_MODE flag)
- General web search → Tavily MCP
- Needs live rendering/interaction → Playwright MCP
Keep the WebSearch fallback for when none of those MCPs are configured.
