---
deliverable: report
route: "docx skill (~/.claude/skills/docx)"
---

# Intake — ask before building (one message, grouped)

**Required**
1. **Subject** — what is the report about, in one line?
2. **Type** — status report / research report / security assessment / technical doc / proposal / memo / academic paper?
3. **Reader** — who reads it, and what decision or understanding should it drive?
4. **Length** — pages or word count? (1-pager, 3-5 pages, 10+, no limit)
5. **Source material** — what should it be built FROM? (files to read, research HERMES already did in Mnemos, fresh research needed, user's notes)

**Optional**
6. Structure — required sections? (exec summary, findings, methodology, recommendations, appendix) Or standard for the type?
7. Tone — formal / plain-language / academic (citations?) / internal-casual?
8. Evidence style — tables, charts, code blocks, screenshots?
9. Format — .docx (default), .pdf (route to pdf skill after), or plain markdown?
10. Anything confidential to exclude or redact? (pentest data, client names — sensitive content also forces Tier 1/2 routing)

# Templates

**T1 — Report blueprint**
> Act as a professional [type] writer. Create a complete outline for a report on [subject] for [reader]. Define the purpose, the sections in order, what each section must establish, and the ideal length. Structure it so the reader can act on it after one read.

**T2 — Section drafter**
> Write the [section name] section of a [type] report on [subject]. Audience: [reader]. Base it strictly on the following source material — do not invent facts: [material]. Keep it [tone], and flag any claim that lacks support in the sources.

**T3 — Executive summary compressor**
> Write an executive summary (max [n] lines) of the following report. Lead with the single most important finding, then the decision/action it calls for: [paste report]

**T4 — Clarity & tightening editor**
> Rewrite the following report section to be clearer and tighter without losing substance. Cut filler, strengthen topic sentences, keep all facts and numbers intact: [paste content]

# Execution

1. **Gather** — pull source material per Q5: `mnemos/hybrid_search.py` for past findings, Read for files, `skills/research` if fresh research is needed (that's its own sub-flow).
2. **Outline** — T1; show the user; confirm before drafting.
3. **Draft** — T2 per section, sources attached. Never fabricate data — a report with a hole labeled "needs data" beats one with invented numbers.
4. **Compress** — T3 for the exec summary (written last, placed first).
5. **Edit** — T4 pass over the full draft.
6. **Build** — invoke `docx` skill with the final content (or `pdf` skill if Q9 said PDF). Verify file exists.
7. **Log** — Mnemos + ReasoningBank per Apollo §2.
8. **Deliver** — path + the exec summary inline + offer one revision round.
