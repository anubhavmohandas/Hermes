---
name: hermes-webdev
description: "HERMES web/mobile development sub-skill. Apollo routes here for website / landing page / web app / dashboard / frontend / mobile app requests (usually via skills/create intake first). Wires the installed design-intelligence skills (ui-ux-pro-max, frontend-design, theme-factory, webapp-testing) plus the native animation-craft and build-loop sub-skills and integrations/webdev.py tokens into an actual build: design system → scaffold → sections (TDD build-loop for real logic) → motion + anti-slop + critique QA → deliver."
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
user-invocable: true
---

# skills/webdev — web & mobile build sub-skill

Called by Apollo. If the request arrived raw (no intake yet), run the
`prompts/website.md` (or `prompts/mobile.md`) intake through
`skills/create` first — never build a site from a one-line request.

This module is the v1 blueprint's `webdev/` made real: the design
intelligence comes from the extracted-and-installed skills, the token
plumbing from `integrations/webdev.py`. As of 2026-07-13, every
`Extractions/*_PATTERNS.md` pattern source previously cited only in a
comment is wired into the pipeline below as a real invocable step —
either a runnable script/command (`design-extract` → `integrations/
design_extract.py`, real and SSRF-safe; `mcp-playwright` / `chrome-
devtools-mcp` → real `connect/mcp_client.py` invocations, gated honestly
on whether that MCP server is actually configured) or a fully-specified
judgment framework in its own sub-skill file, the same category
`animation-craft` already was (`superpowers` → `build-loop.md`; `dyad` →
`edit-discipline.md`; `impeccable` and `open-design` folded directly into
steps 1 and 5; `browser-harness`'s coordinate-click fallback folded into
step 5). None of these are silently absent anymore — where a step needs an
MCP server that isn't configured, the pipeline says so explicitly instead
of skipping quietly.

## The build pipeline

1. **Design system first, code second.**
   `python3 ~/.claude/skills/ui-ux-pro-max/scripts/search.py "<product> <industry> <keywords>" --design-system -p "<Project>"`
   gives style, palette, font pairing, and UX guidelines (67 styles / 161
   palettes / 99 UX rules; `--stack react-native` for mobile, `--page
   dashboard` etc. for page-type guidance). Read
   `~/.claude/skills/frontend-design/SKILL.md` once per project for the
   aesthetics ground rules. No brand from intake → `theme-factory` has 10
   ready themes as a shortcut. If real brand assets (logo, existing site,
   product screenshots) exist, they outrank the generic search.py
   recommendation — a specific signal beats a category heuristic; note the
   divergence explicitly if the two disagree, don't silently pick one
   (2026-07-13 incident: see `docs/DECISIONS.md`).

   **Impeccable's "physical scene sentence" technique** (from
   `Extractions/impeccable/IMPECCABLE_PATTERNS.md`): before writing any CSS,
   state the design in one concrete sentence describing a physical scene —
   e.g. "a chrome shield console glowing on a matte black desk at night,"
   not "a modern dark tech aesthetic." A vague brief defaults to generic
   dark-mode-with-blue-accent; a scene-sentence forces real light/shadow/
   material decisions instead.

   **Cloning/matching a reference site's design system** (from
   `Extractions/design-extract/DESIGN_EXTRACT_PATTERNS.md`): if the intake
   names a real reference site instead of (or alongside) a search.py query,
   run `python3 integrations/design_extract.py <url> --out <dir>` — it
   pulls real colors, font-family declarations, and CSS custom properties
   from the live page's HTML/CSS via the same SSRF-checked fetch path
   `fetcher/fetch.py` uses elsewhere, no new attack surface. It is a
   *static* extractor (raw HTML/CSS only) — it does not get computed
   post-JS styles, hover states, or content behind modals; the script's own
   output lists that gap explicitly under `"gaps"` every time it runs. If
   the deliverable genuinely needs the interaction-driven extraction (the
   full pattern), that requires a playwright MCP server configured via
   `connect/mcp_client.py` — check `python3 connect/mcp_client.py status`
   first, and say plainly if it isn't configured rather than faking the
   deeper extraction.

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

   **Which edit tool, and verifying it landed:** run every file change in
   this step and step 4 through `skills/webdev/edit-discipline.md` — the
   targeted-edit-vs-full-rewrite matrix (switch to `Write` after two failed
   `Edit` attempts on the same target, don't guess at a third) and the
   read-back-before-claiming-done rule for anything non-trivial.

4. **Sections with real copy.** Build section by section per the intake's
   sitemap. No lorem ipsum — write copy for the stated audience and goal.
   Every interactive element gets hover/focus/loading/empty/error states.
   Any animated or gestural element (buttons, dropdowns, modals, toasts,
   drag surfaces) runs through `skills/webdev/animation-craft/SKILL.md`
   first — what to animate, easing/duration, spring vs. transition. Skip
   it only for static content sections with no motion.

   **Real logic gets the build loop.** If a section has actual behavior —
   form validation, data fetching, stateful UI, an API route, anything a
   test can meaningfully fail against — run it through
   `skills/webdev/build-loop.md` (spec gate → bite-sized plan → TDD →
   independent two-stage review → evidence-based verification) instead of
   writing it freehand. A static marketing section with no state does not
   need this — check the skip condition at the top of that file before
   invoking it.

5. **QA before delivering.** `webapp-testing` skill where a browser is
   available (screenshots at mobile + desktop widths); fallback:
   `python3 fetcher/fetch.py fetch <local-url>` sanity check or static
   review against the ui-ux-pro-max UX guidelines. Fix contrast, overflow,
   and hierarchy failures before handoff, not after. Run the
   `animation-craft` Review Checklist against any motion in the build and
   report findings as its mandatory Before/After/Why table — not a prose
   list.

   **Anti-slop pass** (from `Extractions/impeccable/IMPECCABLE_PATTERNS.md`):
   before calling it done, check for the generic-AI-output tells —
   centered-hero-with-gradient-blob as a default, overuse of a single
   "AI purple," cards used for content that isn't actually card-shaped,
   any interactive element missing loading/empty/error states (already
   required by step 4, re-verify here). This is a checklist to run
   yourself, not a script HERMES executes — the deterministic linter
   Impeccable uses is Puppeteer/jsdom-based tooling that isn't installed
   here; note that honestly rather than claiming an automated pass ran.

   **Critique round** (from `Extractions/open-design/OD_PATTERNS.md`), for
   anything worth the extra pass — not every static page needs this: assess
   the build from five angles in one pass — design (visual craft), critic
   (does it actually work), brand (matches the design system from step 1),
   accessibility, copy (matches the audience/goal from intake). Score each
   1-10, and the honest composite is authoritative even if any single angle
   would score it higher — don't let a strong visual score paper over a
   real accessibility gap. Ship only above a "good enough for this
   deliverable" bar you state explicitly; if it doesn't clear the bar in a
   reasonable number of rounds, say so and hand back what's blocking it
   rather than looping indefinitely.

   **Coordinate-click fallback for flaky interaction QA** (from
   `Extractions/browser-harness/browser-harness_PATTERNS.md`): if
   `webapp-testing`'s selector-based interaction hits an iframe, shadow-DOM,
   or a re-render that breaks the selector mid-test, don't loop retrying
   the same selector — switch to a direct coordinate click at the element's
   last-known bounding-box center (Playwright's `page.mouse.click(x, y)`,
   which `webapp-testing`'s own Playwright session already has available;
   no new dependency). This is a fallback technique for one specific
   failure mode, not the default interaction method — selectors are more
   maintainable and should stay the first choice.

   **Auto-generating a regression test from this QA pass** (from
   `Extractions/mcp-playwright/mcp-playwright_PATTERNS.md`): if the
   deliverable warrants a saved regression test (real logic, not a static
   page), Playwright's own codegen records real interactions into a
   runnable spec: `npx playwright codegen <local-url> --output
   tests/<name>.spec.ts`. This runs directly if `npx`/Node is available —
   check first with `npx --version`; if it's missing, say so and skip
   rather than fabricating a "generated" test file that was actually
   hand-written. The MCP-server version of this tool
   (`Extractions/mcp-playwright`) adds 31 tools beyond codegen — reach for
   it via `connect/mcp_client.py call <tool> <json-args> -- <server cmd>`
   only if it's actually configured (`connect/mcp_client.py status`
   first); the direct `npx playwright codegen` command above needs no MCP
   setup at all and is the default path.

   **Lighthouse / Core Web Vitals scoring** (from
   `Extractions/chrome-devtools-mcp/chrome-devtools_PATTERNS.md`): if
   `webapp-testing`'s screenshot-based QA isn't enough and a real
   accessibility/performance/SEO score is wanted, Lighthouse has its own
   CLI, no MCP required: `npx lighthouse <local-url> --output json
   --output-path <dir>/lighthouse-report.json --chrome-flags="--headless"`.
   Same honesty rule as codegen above — check `npx --version` first, and
   if Node/npx genuinely isn't available in the environment, say that
   plainly instead of inventing a score. The full `chrome-devtools-mcp`
   server (UID-based element addressing across shadow-DOM, live perf
   tracing) is reachable the same way as `mcp-playwright` above, via
   `connect/mcp_client.py`, only when actually configured.

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
- The impeccable anti-slop pass, the open-design critique round, and
  build-loop's two-stage review are all reimplemented *judgment
  frameworks*, not automated tooling — nothing here runs a real linter or
  a real independent human reviewer. `build-loop`'s "fresh subagent"
  review is a genuine mechanism (no shared context with the implementer),
  but it's still the same underlying model family, not an outside
  reviewer. Say so if asked; don't oversell any of these three as
  equivalent to CI tooling or human QA.
- The core capability of `chrome-devtools-mcp` (Lighthouse) and
  `mcp-playwright` (codegen) is reachable directly via `npx` with no MCP
  setup required — verified `npx` itself works in this environment
  (2026-07-13). What's NOT wired is the MCP-server versions of either
  (UID-based shadow-DOM addressing, the other 30 mcp-playwright tools) —
  those need `connect/mcp_client.py` pointed at an actually-configured
  server, which is not set up by default. Say which of the two you mean if
  it matters: the `npx` command works today; the MCP server does not,
  until configured.
- `integrations/design_extract.py` is real and tested (verified against a
  live URL 2026-07-13), but it is a *static* extractor only — no computed
  styles, no interaction states, no OKLCH clustering, no A-F grade. That is
  the actual ceiling of what's wired, not a placeholder for "more later."
