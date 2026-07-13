---
name: hermes-webdev-build-loop
description: "HERMES webdev sub-skill — the spec-first, test-first, subagent-reviewed build loop for anything with real logic (React/Next components with state, backend-adjacent code, non-trivial interactivity — not a static marketing page). Invoked internally by skills/webdev/SKILL.md during scaffold/sections (steps 3-4) for deliverables that need it. Not Apollo-routed, not user-invocable. Reimplemented (patterns only, never copied code — Invariant #4) from Extractions/superpowers/sp_PATTERNS.md, itself a plugin by github.com/obra. Attribution: https://github.com/obra/superpowers."
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, TaskCreate, TaskUpdate, Agent
user-invocable: false
---

# skills/webdev/build-loop — spec-first, test-first, reviewed

Called by `skills/webdev/SKILL.md`, never by Apollo directly. This closes
the gap flagged 2026-07-13: HERMES could spawn subagents (`delegation/
dispatch.py`) and could check tests pass at the end (`skills/create` §5),
but had no hard gate forcing a spec before code, a failing test before
implementation, or an independent review before a task counts as done.
This sub-skill is that gate, for the webdev pipeline specifically.

**When to invoke this vs. skip it:** a static marketing/landing page with no
state and no logic (most of what `prompts/website.md` produces) doesn't
need this — `webapp-testing` QA (step 5) is enough. Invoke this sub-skill
when the deliverable has real behavior: form validation, data fetching,
stateful UI, an API route, anything a test can meaningfully fail against.
Ambiguous cases: ask, don't assume either way.

## 1. Brainstorm gate — no code before an approved spec

Before any file is written, produce a short design doc: what's being built,
the interface/contract (props, API shape, state shifted), and the explicit
non-goals. Echo it to the user and get a yes/adjustment — this is the same
"confirm the brief" checkpoint `skills/create` §3 already does at the
deliverable level; this repeats it at the component/feature level for
anything complex enough to need its own spec. Do not start step 2 until
this is confirmed.

## 2. Plan — bite-sized, zero placeholders

Break the approved spec into tasks via `TaskCreate`. Each task must be:
- Small enough to implement and verify in one focused pass.
- Free of placeholders — no "TODO: implement later," no stub that silently
  returns a fake value instead of doing the work. A task that can't be
  fully specified yet is not ready to be a task; go back to step 1.

## 3. Per-task loop — TDD Iron Law

For every task, in order:

1. **Write a failing test first.** No production code before a test exists
   that fails for the right reason. If you catch yourself about to write
   implementation code with no failing test backing it, stop — delete
   what you started and restart from the test.
2. **Write the minimum code to pass the test.** Not more.
3. **Refactor** if needed, keeping the test green.

This is a hard rule, not a preference: skipping straight to implementation
because "the test is obvious" is exactly the failure mode this gate exists
to catch. Static/no-logic sections (see the skip condition above) are
exempt — there's nothing to test-drive in a hero section's copy.

## 4. Two-stage review — independent, skeptical, evidence-based

After a task's code is written, before moving to the next task, run two
review passes. Use `Agent` to dispatch a fresh subagent for each if the
task is non-trivial — a reviewer that already knows how the code was
written is a worse reviewer than one seeing it cold:

1. **Spec-compliance pass:** does the code actually do what the approved
   spec from step 1 said, no more, no less? Not "does it look reasonable."
2. **Code-quality pass:** a second, separate pass — readability, error
   handling, edge cases, whether the test actually exercises the failure
   mode it claims to.

Each pass returns one of: `DONE`, `DONE_WITH_CONCERNS` (proceed, but log
the concern), `NEEDS_CONTEXT` (reviewer couldn't assess — go back and
clarify, don't guess on their behalf), or `BLOCKED` (real defect, fix
before proceeding). **The reviewer must not trust the implementer's own
report of what the code does — read the actual code and run the actual
test.** This is the same discipline as `skills/create` §5.1: "never report
success on a skill's word alone," applied one level down at the per-task
level.

## 5. Verification before completion

Before the overall deliverable is marked done (feeding into `skills/create`
§5's verify/log/deliver), produce fresh command output as evidence — the
actual test run, the actual build output — not a restated claim that it
passed earlier. A completion claim with no fresh evidence attached is not
a completion claim HERMES accepts from itself.

## 6. Systematic debugging, if a task gets stuck

If a task fails review or a bug surfaces mid-loop, don't guess-and-check.
Work it in order: (1) reproduce reliably, (2) read the actual error/stack,
not an assumption about it, (3) form one specific hypothesis about root
cause, (4) test that hypothesis directly before writing a fix. Skipping to
"try this and see if it works" without a stated hypothesis is exactly the
pattern that produces silent regressions elsewhere in the code.

## Honest limits

- This is heavier than most webdev requests need. Using it on a static
  page is process theater — check the skip condition in the header before
  invoking it, every time.
- `Agent` dispatch for reviews goes through `delegation/dispatch.py`'s
  existing forbidden-tool restriction and `MAX_CHILDREN = 3` cap (Apollo
  §6) — this sub-skill doesn't get a separate concurrency budget.
- Reviewer independence is aspirational within a single-session agent, not
  a hard guarantee the way a separate human reviewer would be — a fresh
  `Agent` call has no memory of the implementation session, which is the
  real mechanism, but it is still the same underlying model family. Say so
  if asked, don't oversell it as equivalent to a human second opinion.
