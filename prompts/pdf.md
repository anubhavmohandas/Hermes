---
deliverable: pdf
route: "pdf skill (~/.claude/skills/pdf)"
---

# Intake — ask before building

**Required**
1. **Operation** — generate new PDF / fill a form / merge files / split / extract content?
2. **Input** — which file(s), or what content should the new PDF contain?
3. **Output** — desired filename/location?

**Optional**
4. For generation: is this really a PDF job, or a report (→ `prompts/report.md`, docx→pdf) or slides (→ `prompts/presentation.md`)? Route to the richer flow when content needs authoring — the pdf skill shines at form-fill/merge/split/extract, not long-form writing.
5. For form-fill: field values — and are any sensitive (forces Tier 1/2)?

# Execution

1. Confirm operation + inputs exist (Read/Glob before claiming).
2. Invoke `pdf` skill. Verify output file exists.
3. Log — Mnemos + ReasoningBank per Apollo §2. Deliver path.
