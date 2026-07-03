# prompts/ — deliverable intake + template library

One file per deliverable type. Apollo routes any "make / create / build X"
request to `skills/create/SKILL.md`, which loads the matching file here and
follows it: **ask the intake questions → fill the templates → execute the
route → verify → deliver.**

## File format (every file follows this)

```
---
deliverable: <type>
route: <the skill/module that actually produces the output>
---
# Intake        ← questions to ask the user BEFORE building (required + optional)
# Templates     ← reusable prompt templates with [placeholders]
# Execution     ← ordered steps once intake is answered
```

## Rules

1. **Never skip intake.** If the user already answered something in their
   request, don't re-ask it — but ask everything else that's marked required.
   Ask all questions in ONE message, grouped, not a drip-feed.
2. **Confirm before building.** Echo a one-paragraph brief back
   ("Building: X for audience Y, goal Z…") and get a yes/adjustment.
3. Templates are starting points, not scripts — fill placeholders from
   intake answers, drop sections that don't apply.
4. Routes point at real installed skills (`~/.claude/skills/…`) or HERMES
   modules. If a route target is missing, say so plainly (Invariant #5) —
   never fake the deliverable.
5. New deliverable type → new file here + one routing row in Apollo §3.
   That's the whole extension mechanism.

## Current library

| File | Deliverable | Route |
|---|---|---|
| `presentation.md` | PPTX deck | `pptx` skill + `slides`/`theme-factory` design skills |
| `report.md` | DOCX report / memo / paper | `docx` skill |
| `spreadsheet.md` | XLSX workbook / model | `xlsx` skill |
| `pdf.md` | PDF fill / merge / generate | `pdf` skill |
| `website.md` | Website / web app | `skills/webdev/SKILL.md` |
| `mobile.md` | Mobile app (React Native/Expo) | `skills/webdev/SKILL.md` (react-native stack) |
| `tool.md` | CLI tool / script / utility | spec-first build (spec-kit pattern), Claude Code native |
| `research.md` | Research brief / deep dive | `skills/research/SKILL.md` (Fetcher-backed) |
| `plan.md` | Staged plan / brainstorm / design review | in-conversation + `skills/tasks` tracking |
| `content.md` | Blog / social / README copy / resume / cover letter | in-conversation → `skills/documents` for file output |
