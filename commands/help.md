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
   Stage-4 hardening modules; also Laconic, Occam and Palimpsest, Stage 5 but
   hook-wired unconditionally like the others — see below).
2. **Laconic** — token-reduction. Trigger with "go laconic" / "be brief" /
   "less tokens" for the live-session per-turn mode (`meta/laconic.py` +
   `hooks/laconic_mode.sh`); say "stop laconic" to turn it off. Separately,
   `integrations/laconic_compress.py` does a one-off deterministic
   stopword-drop on bulk text before a Tier 2 job — no model call.
3. **Occam** — minimal-code mode, active every session by default (`full`).
   `meta/occam.py` enforces a YAGNI → reuse → stdlib → native → dep → one
   line → minimum ladder on every coding task, hook-wired at `SessionStart`
   (full ruleset), `UserPromptSubmit` (`/occam lite|full|ultra|off`, per-turn
   reminder), and `SubagentStart` (propagates to Task subagents). Five
   satellite skills: `/occam-review` (diff), `/occam-audit` (whole repo),
   `/occam-debt` (harvest `occam:` shortcut comments), `/occam-gain` (the
   source project's own benchmark scoreboard, not a HERMES-measured number
   — say so if asked), `/occam-help`. Say "stop occam" to turn it off.
4. **Palimpsest** — AI-watermark/provenance-metadata stripping, active every
   session by default (`safe`). Different in kind from Laconic/Occam: it
   doesn't change how the model talks, it's a mechanical `PostToolUse` hook
   (`meta/palimpsest.py` + `hooks/palimpsest_clean.sh`) that scans and
   rewrites a file right after `Write`/`Edit` produces it — invisible
   Unicode, PNG/JPEG ancillary metadata, OOXML docProps, PDF Info/XMP,
   HTML/SVG generator tags. Does NOT touch chat text before it's shown; no
   hook in this platform exposes that. `/palimpsest safe|aggressive|off`;
   say "stop palimpsest" to turn it off.
5. **Opt-in modules (Stage 5)** — db, webdev, media, kanban,
   turbo-memory, notebooklm, composio. Each installs on demand and ships a
   fallback; name the fallback, don't imply the online path is always on.
6. **Out of scope** — NYX (Stage 6). NYX doesn't exist yet; say so plainly.
   Do not describe it as if it partially works.
7. **Slash commands** — `/help` (this), `/status`, `/goal` (end goal + gated roadmap + next action).
8. **Hard constraints** — one line: "Chinese APIs excluded, sensitive data
   never routes to Tier 3, HERMES never auto-applies changes." Full detail
   lives in `SKILL.md` §9 if the user asks for more.

Keep it to what fits on one screen. If the user wants the full architecture,
point them at `HERMES_Architecture.md` / `HERMES_Phase3_Blueprint.docx`
rather than reproducing them inline.
