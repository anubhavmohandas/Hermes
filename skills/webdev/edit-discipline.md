---
name: hermes-webdev-edit-discipline
description: "HERMES webdev sub-skill — which file-edit tool to reach for and how to verify an edit actually landed. Invoked internally by skills/webdev/SKILL.md during scaffold/sections (steps 3-4). Not Apollo-routed, not user-invocable. Reimplemented (patterns only, never copied code — Invariant #4) from Extractions/dyad/DYAD_PATTERNS.md's file-editing tool-selection matrix and mandatory read-back verification."
allowed-tools: Read, Edit, Write
user-invocable: false
---

# skills/webdev/edit-discipline — tool selection + read-back verification

Called by `skills/webdev/SKILL.md`, never by Apollo directly. This is a
small, concrete rule set for one specific failure mode: guessing wrong
about whether a targeted edit or a full rewrite is the right tool for a
given change, and not noticing when an edit silently didn't apply cleanly.

## Tool-selection matrix

| Change shape | Tool |
|---|---|
| Small, localized change (a few lines, a single value, a single function) | `Edit` — targeted find/replace |
| Majority of the file is changing, or the change touches structure throughout | `Write` — full rewrite |
| `Edit` fails twice in a row on the same target (ambiguous match, stale content) | Stop guessing at a third `Edit` — switch to `Write` for that file instead |

The two-strikes rule matters: a third attempt at the same `Edit` after two
failures is usually fighting stale context (the file changed since it was
last read, or the match string was never as unique as assumed), not a
problem `Edit` will solve on a third try. Re-`Read` the file and use `Write`.

## Mandatory read-back verification

After any edit that isn't trivially self-evident (a color swap, a copy
change — those are fine to trust), read the changed region back before
claiming it's done. This isn't paranoia for its own sake — it's the same
principle as `build-loop.md` step 5 (verification before completion) and
`skills/create` §5.1 (never report success on a skill's word alone),
applied at the single-file-edit level: an `Edit` or `Write` tool call
returning success means the write syscall succeeded, not that the
resulting file is what was intended. For anything with real structure
(nested markup, multiple interdependent selectors, generated code), verify
by reading it back or running whatever check applies (a lint pass, a
build, the page rendering) before moving to the next task.

## When this doesn't apply

Trivial, obviously-correct edits (a single hex value, a single string) do
not need a full read-back ceremony — that would be process theater for a
one-line change. Use judgment; the rule exists for edits complex enough
that "it probably worked" is actually a guess.
