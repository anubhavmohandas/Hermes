# src.zip patterns #1421–#1440 — coverage verdict

Assessed 2026-07-03 against the HERMES code. Question: is any of this left to
implement? Verdict per pattern below. Two were genuine gaps and are now
built; the rest were already covered, blocked by the Path-C architecture, or
deliberately out of scope.

**Legend:** ✅ built this pass · ☑️ already covered · 🧱 Path-C limit (HERMES
rides Claude Code; it cannot own the prompt/loop/cache in code — labeled
behavioral, not a gap) · 🚫 out of scope (deliberate, documented) · 📖 noted
for a future direct-API path.

| # | Pattern | Verdict → where |
|---|---|---|
| 1421 | buildEffectiveSystemPrompt 7-level chain | 🧱 On Path C the platform owns the system prompt (Apollo §5, labeled behavioral). Sub-agent prompt composition IS explicit in `delegation/dispatch.py` (fixed allow/deny, no override/proactive modes) — HERMES has no coordinator/customPrompt layering to order. |
| 1422 | systemPromptSection vs DANGEROUS_uncached | 🧱 Cache discipline; platform owns the cache on Path C. Already labeled behavioral in Apollo §5. |
| 1423 | 18 beta headers + gating | 📖 Only relevant when making DIRECT Anthropic API calls. HERMES has no direct API client (rides Claude Code; `brain.py` classifies, `ollama_client.py` hits Ollama). Recorded for a future direct-API tier. |
| 1424 | isCoordinatorMode + INTERNAL_WORKER_TOOLS | 🚫 Coordinator/worker swarm with inter-agent messaging + SyntheticOutput. HERMES delegation is deliberately capped (≤3 children, no inter-agent channel) — blueprint decision. |
| 1425 | isAgentSwarmsEnabled dual-path (GrowthBook) | 🚫 GrowthBook feature-gating for external swarm rollout. HERMES is single-user, no GrowthBook, swarm capped by design. |
| 1426 | **autoDream 4-gate + timing thresholds** | ✅ **Built.** `mnemos/dream.py should_run()` — cheapest-first gate: first-run → interval_hours elapsed → min_new_entries accrued. Scheduled runs respect it; `--force` bypasses. Was a real gap: `interval_hours` was dead config nothing read. Tests: `TestDreamTimingGate`. |
| 1427 | extractMemories post-query via stop hooks | 🧱/☑️ HERMES can't register a platform stop-hook for extraction on Path C. The *intent* (log/extract AFTER the sub-skill returns, not mid-query) is Apollo §2 "after the sub-skill returns" + reflexion logging. The no-tools/1-turn forked-extractor is the shape `delegation/agenda.py` and future extraction would use. |
| 1428 | /ultraplan CCR remote plan mode | 🚫 Claude-Code-on-web infra (teleport + sentinel). HERMES is local/CLI; the harness already provides remote review. Out of scope. |
| 1429 | Swarm 4-backend (iTerm2/Tmux/Pane/InProcess) | 🚫 Terminal-multiplexer backends. HERMES delegation = subprocess `claude -p` (the InProcess-equivalent), deliberately simple. |
| 1430 | Task-type hierarchy + "sensitive never remote" | ☑️ The security-load-bearing rule is enforced: `tier3.py` re-runs a SECOND sensitivity check and REFUSES sensitive→Tier 3 with no override param. The 4-type taxonomy maps to cron(dream)/delegation(local)/agenda — informational, no code owed. |
| 1431 | CompanionSprite / Buddy | 🚫 Presentational personality companion with its own UI. No place in a personal headless system. |
| 1432 | /advisor secondary reviewer model | 📖 Plausible Stage-5 opt-in (attach a 2nd model to review sensitive decisions). Not blueprint-required; the review *discipline* is covered by /security-review + repopack lenses. Left as a noted future option, not built. |
| 1433 | **/security-review 3-phase + 14 exclusions + conf 8/10** | ✅ **Built** (flagged "adopt verbatim"). `commands/security-review.md` — read-only tools, 3 phases, 14 exclusions verbatim, confidence ≥8 filter, human-gate (reports never edits). `integrations/repopack.py` security lens aligned to the same rules. Tests: `TestSecurityReviewCommand`. |
| 1434 | /think-back auto-install + animation | 🚫 Year-in-review animation/marketplace feature. Out of scope. |
| 1435 | /btw forked oracle (no-tools, 1-turn, parent cache) | 🧱 The parent-cache reuse needs platform ownership of the loop. The *usable* half — a lightweight 1-turn no-tools side query — is achievable but low-value; not built. Noted. |
| 1436 | /review local + /ultrareview remote split | ☑️ Provided by the harness (`/code-review`, `/code-review ultra`). HERMES's own change-review is now `/security-review`; no need to rebuild the harness commands. |
| 1437 | createMovedToPluginCommand migration | 🚫 Marketplace-migration stub. HERMES isn't migrating commands to a marketplace. |
| 1438 | parseFrontmatter + `!`shell`` prompt pipeline | ☑️ Consumed, not rebuilt: it's a native Claude Code slash-command feature. `commands/security-review.md` uses exactly this (`allowed-tools` frontmatter + `!`git diff`` live embedding). |
| 1439 | Background cron + NL→cron parsing | ☑️/📖 `cron/scheduler.py` already persists to SQLite (survives restart) with `--interval/--daily/--once`. Natural-language schedule parsing ("every morning"→cron) is the only delta — a minor convenience, not built; explicit flags are more precise for a personal system. |
| 1440 | Analysis checkpoint / summary | — Summary only, nothing to implement. |

## Bottom line

- **Genuinely left → now built (2):** #1426 dream timing gate, #1433
  /security-review command.
- **Already covered (5):** #1430 (sensitive-never-remote), #1436, #1438,
  #1439 (core), plus #1427's intent.
- **Path-C behavioral, not a code gap (4):** #1421, #1422, #1427, #1435.
- **Deliberately out of scope (7):** #1424, #1425, #1428, #1429, #1431,
  #1434, #1437 — coordinator/swarm/companion/CCR/marketplace machinery
  HERMES intentionally does not carry.
- **Noted for future, not owed now (2):** #1423 (direct-API beta headers),
  #1432 (/advisor).

Nothing from #1421–#1440 is left that fits HERMES's Path-C, single-user,
patterns-not-code design. The src.zip corpus is fully reconciled.
