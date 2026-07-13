---
name: help
description: /help — lists every active HERMES module, what it does, how to trigger it, and what's offline with which phase it lands in.
---

# /help

When the user types `/help`, Apollo responds with (not verbatim copy —
regenerate from current `HERMES.local.md` + module map so it never drifts
from what's actually wired):

1. **Active modules** — one line each: name, what it does, example trigger
   phrase. Pull the list from `SKILL.md` §10 module map, "Active" rows only
   (Stages 1–4: the core spine plus cron/delegation/fetcher/connect and the
   Stage-4 hardening modules; also Laconic, Stage 5 but hook-wired
   unconditionally like the others — see below).
2. **Laconic** — token-reduction. Trigger with "go laconic" / "be brief" /
   "less tokens" for the live-session per-turn mode (`meta/laconic.py` +
   `hooks/laconic_mode.sh`); say "stop laconic" to turn it off. Separately,
   `integrations/laconic_compress.py` does a one-off deterministic
   stopword-drop on bulk text before a Tier 2 job — no model call.
3. **Opt-in modules (Stage 5)** — db, webdev, media, kanban,
   turbo-memory, notebooklm, composio. Each installs on demand and ships a
   fallback; name the fallback, don't imply the online path is always on.
4. **Out of scope** — NYX (Stage 6). NYX doesn't exist yet; say so plainly.
   Do not describe it as if it partially works.
5. **Slash commands** — `/help` (this), `/status`, `/goal` (end goal + gated roadmap + next action).
6. **Hard constraints** — one line: "Chinese APIs excluded, sensitive data
   never routes to Tier 3, HERMES never auto-applies changes." Full detail
   lives in `SKILL.md` §9 if the user asks for more.

Keep it to what fits on one screen. If the user wants the full architecture,
point them at `HERMES_Architecture.md` / `HERMES_Phase3_Blueprint.docx`
rather than reproducing them inline.
