---
deliverable: presentation
route: "pptx skill (~/.claude/skills/pptx) — design pass via slides + theme-factory skills"
---

# Intake — ask before building (one message, grouped)

**Required**
1. **Topic** — what is the presentation about, in one line?
2. **Goal** — what should happen after people see it? (inform / persuade / pitch / teach / report status)
3. **Audience** — who's watching, and how technical are they? (execs / engineers / students / clients / mixed)
4. **Length** — how many slides, or how many minutes of talking? (if unsure: ~1 slide per minute)
5. **Key message** — the ONE sentence someone should remember afterwards.

**Optional (ask, but accept "your call")**
6. Tone — formal / conversational / bold / academic?
7. Must-include content — data, charts, screenshots, quotes, case studies?
8. Brand/style — colors, fonts, an existing template, dark/light? (if none: run the `theme-factory` or `slides` skill for a proposed theme)
9. Storytelling or straight structure? (hook→problem→insight→solution→conclusion vs. agenda-driven)
10. Anything to explicitly avoid? (jargon, confidential data, humor…)

# Templates (saved 2026-07-03 from user's reference collection — fill [placeholders] from intake)

**T1 — Presentation blueprint**
> Act as a professional presentation consultant. Create a complete presentation blueprint for [topic]. Define the main goal, target audience, key message, slide flow, and ideal number of slides. Make the structure logical, engaging, and professional.

**T2 — Slide structure & flow architect**
> Design a slide-by-slide structure for a presentation about [topic]. For each slide, provide a clear title and explain the purpose of that slide so the presentation flows naturally from beginning to end.

**T3 — Storytelling presentation creator**
> Turn [topic] into an engaging presentation using a strong storytelling structure: hook → problem → insight → solution → conclusion. Keep the presentation professional, informative, and emotionally engaging from start to finish.

**T4 — Visual direction & design**
> Suggest a professional visual design guide for each slide in a presentation about [topic]. Recommend layouts, charts, diagrams, icons, and visuals that improve clarity and make the slides feel clean, modern, and visually polished.

**T5 — Complete slide content generator**
> Create the full content for every slide in a presentation about [topic]. Write concise, presentation-ready bullet points for each slide while keeping the content clear, professional, and easy to understand. Audience: [describe audience]

**T6 — Slide clarity & simplification editor**
> Review the following presentation content and rewrite it so it works perfectly for slides. Reduce unnecessary text, strengthen the key points, improve clarity, and make sure each slide communicates one clear idea. Content: [paste content]

# Execution (after intake is confirmed)

1. **Blueprint** — run T1 with intake answers merged in (goal/audience/length are already known — the template's "define" becomes "use"). If user chose storytelling (Q9), use T3's structure instead of a generic flow.
2. **Structure** — T2: slide-by-slide titles + purpose. Show the user the outline; get a quick yes before writing content (cheap to fix here, expensive after).
3. **Content** — T5 for every slide, honoring tone (Q6) and must-includes (Q7).
4. **Clarity pass** — T6 on the drafted content. One idea per slide.
5. **Visual direction** — T4; if no brand given (Q8), consult `theme-factory` (ready-made themes) or `slides` skill (design intelligence) for palette/typography before building.
6. **Build** — invoke the `pptx` skill (~/.claude/skills/pptx) with structure + content + visual spec. Verify the .pptx file exists at the returned path.
7. **Log** — Mnemos write ("created pptx: <path> — <topic>") + ReasoningBank entry per Apollo §2.
8. **Deliver** — file path + 3-line summary of the deck + offer one revision round.
