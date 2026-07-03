---
deliverable: tool
route: "spec-first build (spec-kit pattern from Extractions), Claude Code native — no separate skill needed"
---

# Intake — ask before building (one message, grouped)

**Required**
1. **What should the tool do?** — the job, in one line, plus one concrete example run (input → output).
2. **Interface** — CLI / Python module / script / hook / MCP server / GUI?
3. **Inputs & outputs** — files, stdin, args, APIs? Exact formats if known.
4. **Environment** — where does it run (this Mac, server, anywhere)? Python (default) or something else?
5. **Failure policy** — what must it NEVER do? (overwrite files, hit network, run destructive commands without asking)

**Optional**
6. Speed/scale — how big are real inputs? (changes design at ~100MB+/100k items+)
7. Dependencies allowed, or stdlib-only (HERMES default: stdlib-first, Invariant #5)?
8. Who else uses it — needs `--help`, docs, tests? (tests default ON for anything non-trivial)
9. One-off script or a keeper? (keepers get a proper CLI, tests, and a home in a repo)

# Templates

**T1 — Spec (write BEFORE code — spec-kit pattern)**
> Write a short spec for [tool]: purpose (1 line), exact CLI/API surface, input/output contract with an example, error behavior for the 3 most likely bad inputs, non-goals. Keep it under a page.

**T2 — Test-first skeleton**
> From this spec, write the test cases first: the example run, each error case, and one edge case. Then implement until they pass: [spec]

# Execution

1. **Spec** — T1; show the user; confirm the contract before writing code. Cheap to fix here.
2. **Build** — T2 order: tests → implementation → make tests pass. Match HERMES house style (stdlib-first, honest errors, no silent fallbacks).
3. **Verify** — run the example from Q1 for real; run the tests; show output.
4. **Security** — if the tool touches URLs/paths/secrets, route through `meta/security` layers (url_safety, path_security, redact) — a personal tool still gets the gate.
5. **Log** — Mnemos + ReasoningBank per Apollo §2.
6. **Deliver** — path, usage line, test results, and what it deliberately does NOT do.
