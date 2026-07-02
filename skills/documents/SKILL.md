---
name: hermes-documents
description: HERMES document generation sub-skill. Apollo routes here for write/create/generate/document/report/PDF/DOCX/XLSX/PPTX requests. Detects the target format and routes to the corresponding installed document skill (docx/pdf/xlsx/pptx), then returns the produced file path. Logs the deliverable into Mnemos v1.
allowed-tools: Read, Write, Bash
user-invocable: false
---

# skills/documents — Document generation sub-skill

Called by Apollo, not directly by the user.

## What this does in Phase 3A

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
docx/pdf/xlsx/pptx generation — those already exist as their own skills.
Its only job is: detect format correctly, hand off, verify the output
landed, log it.

## Extension point

None needed structurally — the four format skills already cover the
document surface. If a new format shows up (e.g. Google Slides direct
export) it slots in as one more branch in the detection step above.
