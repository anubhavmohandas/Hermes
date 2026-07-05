---
name: hermes-webdev
description: "HERMES web/mobile development sub-skill. Apollo routes here for website / landing page / web app / dashboard / frontend / mobile app requests (usually via skills/create intake first). Wires the installed design-intelligence skills (ui-ux-pro-max, frontend-design, theme-factory, webapp-testing) and integrations/webdev.py tokens into an actual build: design system → scaffold → sections → QA → deliver."
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
user-invocable: false
---

# skills/webdev — web & mobile build sub-skill

Called by Apollo. If the request arrived raw (no intake yet), run the
`prompts/website.md` (or `prompts/mobile.md`) intake through
`skills/create` first — never build a site from a one-line request.

This module is the v1 blueprint's `webdev/` made real: the design
intelligence comes from the extracted-and-installed skills, the token
plumbing from `integrations/webdev.py`. Pattern sources for anything
beyond that: `Extractions/{dyad,impeccable,open-design,design-extract}/
*_PATTERNS.md` — patterns only, never copied code (Invariant #4).

## The build pipeline

1. **Design system first, code second.**
   `python3 ~/.claude/skills/ui-ux-pro-max/scripts/search.py "<product> <industry> <keywords>" --design-system -p "<Project>"`
   gives style, palette, font pairing, and UX guidelines (67 styles / 161
   palettes / 99 UX rules; `--stack react-native` for mobile, `--page
   dashboard` etc. for page-type guidance). Read
   `~/.claude/skills/frontend-design/SKILL.md` once per project for the
   aesthetics ground rules. No brand from intake → `theme-factory` has 10
   ready themes as a shortcut.

2. **Tokens.** Seed `integrations/webdev.py`-style tokens (CSS custom
   properties + JSON mirror) from the chosen palette so CSS and JS share
   one source of truth. `python3 integrations/webdev.py tokens --out <dir>`
   emits the scaffold; overwrite its defaults with the design-system
   values — the defaults are placeholders, not a brand.

3. **Scaffold per stack.**
   - Plain site → semantic HTML + the tokens.css, no build step.
   - React/Next.js → components under `components/`, tokens imported
     globally; `integrations/webdev.py component <Name>` for quick
     starts.
   - React Native/Expo → screens + navigation, tokens via the JSON
     mirror.

4. **Sections with real copy.** Build section by section per the intake's
   sitemap. No lorem ipsum — write copy for the stated audience and goal.
   Every interactive element gets hover/focus/loading/empty/error states.

5. **QA before delivering.** `webapp-testing` skill where a browser is
   available (screenshots at mobile + desktop widths); fallback:
   `python3 fetcher/fetch.py fetch <local-url>` sanity check or static
   review against the ui-ux-pro-max UX guidelines. Fix contrast, overflow,
   and hierarchy failures before handoff, not after.

6. **Verify → log → deliver** per `skills/create` §5: the site runs (name
   the one command to start it), Mnemos + ReasoningBank logged, delivery
   includes folder path + screenshots + where to edit what.

## Honest limits

- This produces real front-ends and Expo apps; it does not provision
  backends, databases, or deployments — `integrations/db/store.py` covers
  local data needs; deploy targets are noted in delivery, not executed.
- App-store packaging (signing, store listings) is out of scope for a
  first pass; Expo Go preview is the deliverable.
- If `~/.claude/skills/ui-ux-pro-max` is missing, degrade to
  `frontend-design` guidance + webdev.py defaults and SAY SO — don't
  silently ship the placeholder palette as if it were designed.
