# webdev/autopilot — Manus-style end-to-end build mode

Pattern source: manus.im's agent loop (plan file → autonomous execution →
live preview → shipped URL). **Reimplemented natively** — HERMES does not
call the Manus API: it's a paid, credit-metered agent, and handing a build
to a second agent means losing HERMES's design system, tests, and Mnemos
logging. What's worth copying is the *loop shape*, not the service.

## When

User says "just build it", "autopilot", "go end-to-end", or intake Q12 =
autopilot. Default stays the confirm-each-phase flow in `SKILL.md`.
**Intake still runs** — autopilot removes mid-build check-ins, not the
brief. No brief confirmation → no autopilot.

## The loop

1. **Plan file.** Write `<project>/todo.md` — phases (design system →
   tokens → scaffold → each section → QA → deliver), each a checkbox with
   the concrete output path. This is the single source of progress; mirror
   it with TaskCreate so the Cowork widget shows it too.
2. **Execute without asking.** Work top-down, tick boxes in `todo.md` as
   each item's output exists on disk (verified, not assumed — same rule as
   `edit-discipline.md`). Decisions that would normally be a question →
   pick the default, append to `todo.md` under `## Assumptions`.
3. **Stop conditions** (the only reasons to break autonomy):
   - anything irreversible or paid (deploy to prod, domain, API keys,
     `npm publish`),
   - same step failing 3× — write the blocker under `## Blocked`, stop,
     report,
   - brief contradiction discovered mid-build.
4. **Live preview.** After scaffold, start the dev server
   (`npm run dev` / `python3 -m http.server`) and give the user the URL
   once. In Cowork, a static build can also be published as a private
   Artifact for a shareable preview.
5. **QA gate unchanged.** Full step-5 QA (screenshots, anti-slop, critique,
   animation-craft table). Autopilot is not a QA skip.
6. **Ship (opt-in only).** If intake Q11 named Netlify/Vercel AND the user
   said deploy: `netlify deploy --dir <build>` (draft URL, not `--prod`) or
   `vercel` (preview, not `--prod`). Check the CLI is installed and logged
   in first (`netlify status` / `vercel whoami`); if not, say so and stop at
   the local build. Promoting to prod is always a stop-condition question.
7. **Deliver.** `todo.md` fully ticked + Assumptions list + preview/deploy
   URL + the one command to run locally.

## Honest limits

- No sandboxed VM like Manus — it runs in whatever shell HERMES has. A
  missing Node/npm stops the loop at step 3; it doesn't get installed
  silently on the user's machine.
- "Autonomous" = no check-ins, not unbounded. Long builds still hit tool
  timeouts; `todo.md` is what makes a resume possible.
- If Manus-the-service is explicitly wanted later (e.g. offload deep web
  research), wire it through `connect/` behind `MANUS_API_KEY`, off by
  default — not built.
