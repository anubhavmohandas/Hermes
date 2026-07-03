---
name: security-review
description: /security-review — structured security review of the current branch's uncommitted + committed-vs-main diff. Three phases (context → comparative → vulnerability), 14 hard exclusions adopted verbatim from Anthropic's production security-review, and a confidence ≥8/10 filter so only real, high-confidence findings surface. Read-only: reads the diff via git, never edits.
argument-hint: "[ staged | branch | <path> ]"
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:*), Read, Glob, Grep
---

# /security-review

Pattern source: `CC_SRC_PATTERNS.md` #1433 (Anthropic `/security-review`,
3-phase + 14 exclusions + confidence scoring) and #1438 (frontmatter
`allowed-tools` + `!` live-shell prompt pipeline). Reimplemented as a HERMES
command, not copied. This is HERMES's own review lens — distinct from the
repeatable 7-layer platform audit in `meta/security/audit.py` (that scans
HERMES's own defenses; this scans a code *change* for vulnerabilities) and
from the harness's built-in `/code-review` / `/security-review`.

**Scope of the diff to review** (from `$ARGUMENTS`, default = branch):
- `staged` → `!`git diff --cached``
- `branch` (default) → `!`git diff main...HEAD`` plus `!`git diff`` (uncommitted)
- `<path>` → restrict the review to that file/dir within the diff

Current working tree for context:
`!`git status --short``

---

## Run these three phases in order

### Phase 1 — Repository context research
Before judging the diff, understand the code's own security model:
- What frameworks/sanitizers/validation already exist here? (grep for the
  project's existing `redact`, `url_safety`, `path_security`, auth, escaping)
- What is the threat model of *this* codebase? (a personal CLI tool and a
  public web endpoint have different ones)
- Note the conventions a finding must respect, so you don't flag a pattern
  the codebase already handles safely elsewhere.

### Phase 2 — Comparative analysis
- Diff the new code *against* the existing security patterns from Phase 1.
- Flag deviations: a new input path that skips the established validator, a
  new surface that doesn't go through the existing gate, a copied-then-
  modified sanitizer that dropped a check.

### Phase 3 — Vulnerability assessment
Trace data flow from **untrusted input → sensitive operation**:
- Injection (shell/SQL/template/prompt-into-code), path traversal,
  SSRF where host or protocol is attacker-controlled, unsafe
  deserialization, auth/privilege-boundary crossings, secrets written to
  disk or logs, missing authz on a state-changing operation.
- For each candidate: name the exact source (input) and sink (dangerous
  op), and the path between them. A vuln with no reachable untrusted-input
  path is not a finding — it's excluded (see below).

---

## Execution model (false-positive filtering)

1. First pass: list every *candidate* vulnerability with file:line, the
   source→sink data flow, and a proposed fix.
2. Second pass — per candidate, act as a skeptical reviewer trying to prove
   it's a **false positive**: is the input actually reachable/untrusted? Is
   there an existing mitigation (Phase 1) that already covers it? Does it
   fall under an exclusion?
3. Assign a confidence 1–10 that the finding is a **real, exploitable
   vulnerability**. **Drop anything below 8.** Better silent than noisy.

---

## 14 hard exclusions — auto-exclude WITHOUT reporting

Adopted verbatim (Anthropic's security team tuned these in production;
#1433). Do not report a finding that is only:

1. Denial of service / resource exhaustion.
2. Secrets stored on disk when they're otherwise access-controlled.
3. Rate limiting (absence of).
4. Memory / CPU consumption concerns.
5. Input validation on **non-security** fields.
6. GitHub Actions issues without a proven untrusted-input path.
7. General "lack of hardening" without a concrete, demonstrable vuln.
8. Theoretical race conditions with no realistic exploit.
9. Outdated library versions (that's a dependency-scan job, not this).
10. Memory-safety concerns in memory-safe languages (Python, Rust, Go…).
11. Findings in unit-test files only.
12. Log spoofing / log injection.
13. SSRF where only the **path** is controlled (not host/protocol).
14. User-controlled content appearing in an AI system prompt — that is a
    normal condition of the product, **not** a vulnerability by itself.

HERMES-specific note (does NOT relax the above): findings about the
non-negotiable invariants — a path that could route sensitive data to Tier 3
or a Chinese API, a bypass of `verify.sh`/Apollo, an auto-apply of a Curator
proposal — are always in scope and never excluded, because they are concrete
security-model violations, not hardening wishlist items.

---

## Output format

Group by severity (Critical / High / Medium). For each surviving finding:

- **file:line** — one-sentence defect.
- **Data flow** — source (untrusted input) → sink (dangerous op), the path.
- **Why it's real** — why it survived the exclusions + why confidence ≥8.
- **Fix** — the concrete change.

If nothing survives the filter, say exactly that: "No findings at confidence
≥8 after the 14 exclusions." Do not pad with low-confidence speculation, and
do not edit any file — this command reports; the human decides and applies
(Invariant #3).
