---
name: occam-debt
description: >
  Harvest every `occam:` comment in the codebase into a debt ledger, so the
  deliberate shortcuts and deferrals Occam leaves behind get tracked instead
  of rotting into "later means never". Use when the user says "occam debt",
  "/occam-debt", "what did occam defer", "list the shortcuts", "occam
  ledger", or "what did we mark to do later". One-shot report, changes nothing.
---

Reimplemented from a third-party plugin's debt-ledger skill, renamed on
integration — including the comment marker itself: `occam:` (not the
source project's own marker), matching `skills/occam/SKILL.md`'s Rules
section.

Every deliberate Occam shortcut is marked with an `occam:` comment naming
its ceiling and upgrade path. This collects them into one ledger so a deferral
can't quietly become permanent.

## Scan

Grep the repo for comment markers, skipping `node_modules`, `.git`, `__pycache__`,
and build output:

`grep -rnE '(#|//) ?occam:' .`  (add other comment prefixes if your stack uses them)

Each hit is one ledger row. The comment prefix keeps prose that merely mentions
the convention out of the ledger.

## Output

One row per marker, grouped by file:

`<file>:<line>, <what was simplified>. ceiling: <the limit named>. upgrade: <the trigger to revisit>.`

The convention is `occam: <ceiling>, <upgrade path>`, so pull the ceiling
and the trigger straight from the comment. Want an owner per row too? add
`git blame -L<line>,<line>`.

Flag the rot risk: any `occam:` comment that names no upgrade path or
trigger gets a `no-trigger` tag, those are the ones that silently rot.

End with `<N> markers, <M> with no trigger.` Nothing found: `No occam: debt. Clean ledger.`

## Boundaries

Reads and reports only, changes nothing. To persist it, ask and it writes the
ledger to a file (e.g. `OCCAM-DEBT.md`). One-shot. "stop occam-debt" or
"normal mode" to revert (no mode was set to begin with).
