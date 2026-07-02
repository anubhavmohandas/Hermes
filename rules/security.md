---
name: security
scope: "security/**, pentest/**, recon/**"
description: Fires when the working path touches security/, pentest/, or recon/. Forces Tier 1, restricts external calls, mandates redaction.
---

# security.md — fires on security/**, pentest/**, recon/**

Inherits `default.md`. Adds:

- All output routes Tier 1 (Claude API) only. No exceptions, no fallback to
  Tier 2 or Tier 3 for anything under these paths — `brain.py` will already
  classify most of this as sensitive via keyword match, but path-scoping is
  a second, independent enforcement layer. Defense in depth, not redundancy
  for its own sake.
- No external API calls except explicitly approved research tools
  (`WebSearch` in Phase 3A; Fetcher's gated MCPs from Phase 3C on).
- Redact sensitive findings (`meta/security/redact.py`) before writing
  anything to a file, not just before display.
- Flag CVEs, exploits, and credentials explicitly before considering a task
  complete — don't bury a live credential in the middle of a findings dump
  and call it done.
