---
deliverable: website
route: "skills/webdev/SKILL.md (design: ui-ux-pro-max + frontend-design; build: framework or integrations/webdev.py; QA: webapp-testing)"
---

# Intake — ask before building (one message, grouped)

**Required**
1. **What is it?** — landing page / portfolio / multi-page site / web app (dashboard, tool, SaaS) / e-commerce?
2. **Who's it for and what should they DO on it?** — the one conversion/action that matters (sign up, contact, read, buy).
3. **Product & industry** — one line ("beauty spa wellness service", "security research blog") — this drives the ui-ux-pro-max design-system search verbatim.
4. **Pages/sections** — list them, or "propose a sitemap for me".
5. **Stack** — React/Next.js / plain HTML+CSS+JS / no preference (then: static → plain HTML, app → Next.js).

**Optional**
6. Design direction — 2-3 adjectives (minimal, bold, dark, playful, brutalist, glassmorphism…) or reference sites you like.
7. Brand — existing colors/fonts/logo? Or should HERMES propose a design system?
8. Content — real copy/images provided, or HERMES drafts placeholder-free copy from Q2/Q3?
9. Must-have functionality — forms, auth, search, animations, charts, payments?
10. Responsive targets — mobile-first, desktop-first, both equally? (default: both, mobile-checked)
11. Where does it live — local folder only, or deploy target (Vercel/Netlify/GitHub Pages) to keep in mind?

# Templates

**T1 — Site blueprint**
> Act as a senior web designer. Create a complete blueprint for a [type] for [product/industry]. Define: target user, primary action, sitemap with the purpose of each page, section-by-section layout of the main page, and the design direction ([adjectives]). Make it conversion-focused and modern.

**T2 — Design system query** (run through ui-ux-pro-max, not the LLM)
> python3 ~/.claude/skills/ui-ux-pro-max/scripts/search.py "[product_type] [industry] [keywords]" --design-system -p "[Project Name]"

**T3 — Section builder**
> Build the [section] for [site]. Design system: [T2 output — palette, fonts, style]. It must [purpose of section], be fully responsive, and use semantic HTML with accessible contrast. No lorem ipsum — write real copy for [audience].

**T4 — Polish pass**
> Review this page against the design system and UX guidelines: [paste/attach]. Fix: visual hierarchy, spacing rhythm, contrast failures, missing hover/focus states, mobile overflow. Keep the structure — polish, don't redesign.

# Execution

1. **Blueprint** — T1 with intake merged; show sitemap + design direction; confirm before building.
2. **Design system** — T2 (`ui-ux-pro-max` search: style, palette, font pairing, UX guidelines for the stack). Read `~/.claude/skills/frontend-design/SKILL.md` for the aesthetics ground rules. Emit tokens via `python3 integrations/webdev.py tokens` seeded from the chosen palette.
3. **Build** — per stack: scaffold pages/components (T3 per section). Real copy, no filler. Wire must-haves (Q9).
4. **QA** — `webapp-testing` skill (or `fetcher/fetch.py` screenshot fallback) on desktop + mobile widths; then T4 polish pass.
5. **Log** — Mnemos + ReasoningBank per Apollo §2.
6. **Deliver** — folder path, how to run it locally (one command), screenshot(s), and what to edit where.
