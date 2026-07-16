---
name: occam-gain
description: >
  Show the source project's published benchmark scoreboard for the
  lazy-ladder approach: less code, less cost, more speed. One-shot
  display, not a persistent mode, and explicitly not a number for this
  repo. Trigger: /occam-gain, "occam gain", "what does occam save",
  "show occam impact", "occam scoreboard".
---

# Occam Gain

Display this scoreboard when invoked. One-shot: do NOT change mode, write
flag files, or persist anything.

**Provenance, stated plainly:** these are not HERMES's own measured
numbers — HERMES has not run this benchmark. They are the third-party
source project's own published results (a headless Claude Code session
editing a real FastAPI+React repo, 12 feature tickets, n=4, Haiku 4.5,
`git diff` scored against a no-skill baseline), reproduced here because
the ladder this skill enforces (`skills/occam/SKILL.md`) is a faithful
port of the same ladder that produced them. If HERMES ever runs its own
benchmark, replace this card with that number instead of this one.

## Scoreboard

Render plain ASCII bars. The bar length shows the measured range; the label
carries the exact figure:

```
  occam gain (source project's published benchmark, not HERMES's own)

  Lines of code   no-skill   ████████████████████  100%
                  ladder     █████████░···········   46%   ▼ 54%
  Tokens          no-skill   ████████████████████  100%
                  ladder     ███████████████▌·····   78%   ▼ 22%
  Cost            no-skill   ████████████████████  100%
                  ladder     ████████████████······   80%   ▼ 20%
  Time            no-skill   ████████████████████  100%
                  ladder     ██████████████▌·······   73%   ▼ 27%
  Safety          held at 100% on the same adversarial tier as baseline

  This repo:  /occam-debt  (shortcuts you deferred)
              /occam-audit (what's still cuttable)
```

## Honesty boundary

These are the source project's benchmark medians, not this repo's. NEVER
print a per-repo savings number ("you saved X lines/tokens here"): the
unbuilt version was never written, so there is no real baseline to
subtract from in a live repo. The only real per-repo figures come from
`/occam-debt` (a counted ledger of what was actually deferred here), and
this card points there instead of inventing one.

## Boundaries

One-shot display. Edits nothing, changes no mode.
"stop occam" or "normal mode": revert (no mode was set to begin with).
