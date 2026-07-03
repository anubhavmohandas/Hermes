---
deliverable: research
route: "skills/research/SKILL.md (Fetcher-backed: Tavily → Firecrawl → direct fetch → WebSearch fallback)"
---

# Intake — ask before researching (one message, grouped)

**Required**
1. **Question** — what exactly do you want to know? (a question, not a topic — "is X exploitable via Y" beats "X security")
2. **Depth** — quick answer (minutes) / solid brief (structured findings + sources) / deep dive (multi-source, possibly overnight via Cron)?
3. **Freshness** — does recency matter? (news/CVEs: yes → live Fetcher; concepts: no)
4. **Sensitivity** — does the QUERY itself reveal anything sensitive (target names, client info, unpublished vulns)? → forces Tier 1/2 and no third-party search APIs; sensitive queries use direct fetch only.

**Optional**
5. Source preference — official docs, papers, code, news, forums? Anything to distrust?
6. Output shape — inline answer, markdown brief, or full report (→ `prompts/report.md` afterwards)?
7. What do you already know/believe — so research confirms or challenges it instead of repeating it?
8. Overnight OK? Deep dives can run as a Cron job and land in Mnemos by morning (CLI only, Invariant #7).

# Templates

**T1 — Research plan**
> Break the question "[question]" into 3-6 sub-questions that, answered together, fully answer it. For each: the best source type and a search query. Flag which sub-questions likely have conflicting sources.

**T2 — Synthesis**
> Synthesize findings on "[question]" from these sources: [findings+sources]. State: what's established (multiple agreeing sources), what's contested (name the disagreement), what's unknown. Confidence per claim: high/medium/low. Cite which source supports what. Do not smooth over conflicts.

# Execution

1. **Plan** — T1; for deep dives show the plan first.
2. **Search** — per sub-question through `skills/research` (Fetcher backend, SAFE_MODE; sensitive → direct fetch only, no API leakage). Log source URLs as you go.
3. **Synthesize** — T2. Real confidence levels — LOW is an honest answer.
4. **Store** — findings into Mnemos (`store.py write` + HNSW insert) so "what did we find on X" works next session.
5. **Log** — ReasoningBank per Apollo §2.
6. **Deliver** — per Q6: answer / brief / hand off to report flow. Always with sources and confidence.
