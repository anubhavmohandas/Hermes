---
name: hermes-documents
description: HERMES document generation sub-skill. Apollo routes here for write/create/generate/document/report/PDF/DOCX/XLSX/PPTX requests. Detects the target format and routes to the corresponding installed document skill (docx/pdf/xlsx/pptx), then returns the produced file path. Logs the deliverable into Mnemos v1.
allowed-tools: Read, Write, Bash
user-invocable: false
---

# skills/documents — Document generation sub-skill

Called by Apollo, not directly by the user.

**Where the format skills live:** installed at `~/.claude/skills/{docx,pdf,
xlsx,pptx}` (from the Anthropic skills repo, installed 2026-07-03). If one
is missing from a fresh machine, say so and degrade to a markdown deliverable
with the content intact — never fake the binary format (Invariant #5).
Reinstall source: `Documents/Claude/Skills/skills-main-anthropic.zip`.

**Intake:** if the request is "make me a report/presentation/spreadsheet
FROM SCRATCH" (content doesn't exist yet), it belongs to `skills/create` —
Apollo routes it there and the intake in `prompts/{report,presentation,
spreadsheet,pdf}.md` runs first. This sub-skill handles the format step:
content exists (or arrives from the create flow), produce the file.

## What this does

1. Accept a document request from Apollo, already tier-checked.
2. Detect the target format from the request:
   - "Word doc" / "report" / "memo" / ".docx" → invoke the `docx` skill
   - "PDF" / ".pdf" / form-fill / merge / split → invoke the `pdf` skill
   - "spreadsheet" / "Excel" / ".xlsx" / budget / data table → invoke the `xlsx` skill
   - "deck" / "slides" / "presentation" / ".pptx" → invoke the `pptx` skill
   - Plain prose with no format cue and nothing that needs to leave the
     conversation → markdown artifact, not a routed skill call
3. After the target skill produces the file, confirm it actually exists at
   the returned path before telling Apollo it succeeded — don't take a
   skill's word for it if you can trivially verify with a file check.
4. Log what was produced into Mnemos v1:
   `python3 mnemos/store.py write "<session_id>" "assistant" "created <format>: <path>"`
5. Return `{file_path, format}` to Apollo.

## Ground rule

This sub-skill is a router, not a document engine. It does not reimplement
docx/pdf/xlsx/pptx generation — those exist as installed skills (paths
above). Its only job is: detect format correctly, hand off, verify the
output landed, log it.

## Extension point

None needed structurally — the four format skills already cover the
document surface. If a new format shows up (e.g. Google Slides direct
export) it slots in as one more branch in the detection step above.
