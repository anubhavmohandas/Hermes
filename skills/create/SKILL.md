---
name: hermes-create
description: HERMES deliverable-creation orchestrator. Apollo routes here whenever the user wants something MADE — a presentation, report, spreadsheet, PDF, website, web app, mobile app, tool, or research brief. Runs the intake interview from prompts/<type>.md, confirms the brief, routes to the executing skill, verifies the output exists, logs it, and delivers. One flow, every deliverable.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, WebSearch
user-invocable: false
---

# skills/create — intake-first deliverable flow

Called by Apollo, not directly by the user. This is the "one person uses
HERMES and gets a working result" layer: **interview → brief → build →
verify → deliver.** Never skip to building.

## 1. Detect the deliverable type

| User asks for… | Load |
|---|---|
| presentation / deck / slides / pptx | `prompts/presentation.md` |
| report / memo / paper / write-up / docx | `prompts/report.md` |
| spreadsheet / excel / budget / tracker / xlsx | `prompts/spreadsheet.md` |
| pdf / fill form / merge / split | `prompts/pdf.md` |
| website / landing page / web app / dashboard / frontend | `prompts/website.md` |
| mobile app / android / ios / react native | `prompts/mobile.md` |
| tool / script / CLI / utility / automation | `prompts/tool.md` |
| research / investigate / deep dive / find out | `prompts/research.md` |

Ambiguous ("make me something for my client meeting")? Ask which, with the
options — don't guess.

Type not in the table? Say there's no intake file yet, offer the closest
one, and note that adding `prompts/<newtype>.md` + an Apollo routing row is
the extension path (see `prompts/README.md`).

## 2. Intake interview

1. Read the type's `prompts/<type>.md`.
2. Strike every intake question the user's request already answered.
3. Ask ALL remaining questions in ONE grouped message — required first,
   optional after, numbered, answerable in one reply. Tell the user
   "your call" is a valid answer for optionals.
4. No drip-feed interrogation. One round; at most one follow-up round if a
   required answer is missing or contradictory.

## 3. Confirm the brief

Echo back a compact brief — "Building: [what] for [audience], goal [goal],
[length/stack/format], style [style]" — and get a yes or an adjustment
BEFORE building. This is the cheap moment to be wrong.

## 4. Execute

Follow the file's **Execution** section step by step. Non-negotiables:

- The route targets in the file are real: installed skills live in
  `~/.claude/skills/` (docx, pptx, xlsx, pdf, ui-ux-pro-max, slides,
  design, frontend-design, theme-factory, web-artifacts-builder,
  webapp-testing, canvas-design, brand, banner-design, ui-styling,
  design-system). If one is missing, SAY SO and degrade honestly
  (markdown outline instead of a fake .pptx) — Invariant #5.
- Outline/structure checkpoints in the Execution steps are real user
  checkpoints, not rhetorical.
- Tier discipline still applies: Apollo already ran `brain.py check`;
  sensitive content stays Tier 1/2 (that includes slide content and
  report data, not just queries).

## 5. Verify, log, deliver

1. **Verify:** the promised artifact exists (file check / build runs /
   tests pass — whatever the type's Execution section names). Never
   report success on a skill's word alone.
2. **Log:** Mnemos write ("created <type>: <path> — <one-liner>") and the
   ReasoningBank entry per Apollo §2 — honest reward.
3. **Deliver:** path + short summary + one offered revision round.

## Ground rule

This skill owns the FLOW, not the craft. Content quality comes from the
templates in `prompts/`, design intelligence from the installed design
skills, file generation from the document skills. If a step produces
something weak, fix it through the type's own polish/clarity pass (most
files have one) — don't freelance a new pipeline mid-task.
