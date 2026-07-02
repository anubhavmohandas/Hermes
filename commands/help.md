---
name: help
description: /help — lists every active HERMES module, what it does, how to trigger it, and what's offline with which phase it lands in.
---

# /help

When the user types `/help`, Apollo responds with (not verbatim copy —
regenerate from current `HERMES.local.md` + module map so it never drifts
from what's actually wired):

1. **Active modules** — one line each: name, what it does, example trigger
   phrase. Pull the list from `SKILL.md` §10 module map, "Active" rows only.
2. **Offline modules** — same format, but each line names the phase it lands
   in (3B / 3C / 3D). Do not describe offline modules as if they partially
   work.
3. **Slash commands** — `/help` (this), `/status`.
4. **Hard constraints** — one line: "Chinese APIs excluded, sensitive data
   never routes to Tier 3, HERMES never auto-applies changes." Full detail
   lives in `SKILL.md` §9 if the user asks for more.

Keep it to what fits on one screen. If the user wants the full architecture,
point them at `HERMES_Architecture.md` / `HERMES_Phase3_Blueprint.docx`
rather than reproducing them inline.
