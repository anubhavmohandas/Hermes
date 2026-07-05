# HERMES — Architecture decisions

Two kinds of entry. The **standing decision** at the top (the v1.0 subsystem
freeze) is settled — it constrains everything below it. The numbered **D-items**
are the opposite: things flagged during builds/audits that still need a real
decision, not a quick patch. Each D-entry: what was found, the options, what's
live today.

---

## Architecture freeze — the v1.0 subsystem set is final (STANDING, 2026-07-05)

**The decision (settled, not deferred):** the subsystem set is frozen for
v1.0 — Apollo, brain, meta (policy + security), Mnemos, Clio, Curator,
ReasoningBank, Cron, Delegation, Fetcher, Connect, integrations. No new
top-level folders and no new subsystems before the `v1.0.0` tag. A feature
either fits inside one of these modules or it waits for a real user to force
the change; new capabilities go to the post-1.0 backlog, they do not reopen
the release list. This is the `V1_CHECKLIST.md` ground rule, recorded here
with the date and the reasoning so it is an actual commitment, not a note.

**Why freeze now, rather than keep the option open:**
1. The surface is already large for a project with zero external users — 12
   subsystems, ~5.8k production LOC. More surface today is more to *harden*
   before a first user, not more value.
2. Scope keeps getting re-litigated (see D2: which blueprint is
   authoritative). Freezing the set is what lets an audit stop reopening
   "should there be a Browser / Agents / Planning module" every time — those
   SVG-era modules are explicitly out until a user forces one in.
3. Everything left on the release list (`V1_CHECKLIST` §2–§7) is hardening —
   contracts, dead-code, fresh-install, dogfood, demo. None of it needs a new
   subsystem.
4. Adding subsystems before one external person has run it is building on
   unvalidated assumptions. The checklist's own closing line — "reality
   decides the roadmap" — only works if the roadmap isn't pre-committed to
   surface nobody has asked for yet.

**Enforcement is real, not aspirational — concrete evidence, same day:** the
`meta/policy.py` extraction (§1 inverted-imports fix, 2026-07-05) added a
*file inside the existing `meta/` subsystem* — it did not stand up a new
top-level thing. The two inverted imports were fixed by moving shared policy
*down* into `meta/`, a peer to the existing `meta/security/` package, not by
creating a subsystem. That is the freeze working exactly as intended:
structural change is allowed, but it stays inside the frozen set. The freeze
is at folder/subsystem granularity, not file granularity — new files within a
frozen module are fine; new modules are not.

**What this does NOT freeze:** internal refactors (like today's), bug fixes,
test and doc hardening, and the still-open *content* calls in D2 (blueprint
authority) and D3 (third-party skills). Those decide what goes inside the
existing modules; none of them adds a subsystem.

---

## D1 — Interactive human approval for `approval`-tier Bash commands

**Found:** 2026-07-02 code audit (M1). `approval.py` classifies commands
like `sudo`, `git push --force`, `DROP TABLE` as `approval` (distinct from
`block`) — the intent, per the original design note, was "not auto-denied,
but not auto-allowed either." In practice, `gate.py` returns `deny` for
`approval` exactly like it does for `block`, and `verify.sh` maps any deny
to a hard `exit 1`. There is no third state at the hook layer. The comment
claiming otherwise was misleading and has been corrected (see
`meta/security/gate.py`).

**Why it's hard-blocked today, and why that's the correct default:**
`PreToolUse` hooks are synchronous, non-interactive gates — stdin in, exit
code out. There is no mechanism for a hook to pause mid-call, surface a
prompt to a human, and wait for a response. Given that constraint,
fail-closed (deny anything not explicitly safe) is the only sound default.
Silently "allowing" approval-tier commands would defeat the point of
flagging them at all.

**Option A — accept the hard block as final, permanently.** Simplest. Cost:
`sudo`, force-push, etc. become unusable through HERMES at all, even when
the human genuinely wants to run them. Over time this pushes real work
outside HERMES entirely, which defeats "one skill that combines
everything."

**Option B — move the ask upstream, into Apollo.** Before Apollo ever
invokes the Bash tool for a command that `approval.classify_command()`
would flag, it calls `AskUserQuestion` directly and gets an explicit yes/no
from the human. If yes, Apollo writes a short-lived approval token (e.g.
`hermes/logs/.approved/<md5-of-command>-<timestamp>`, expiring after a few
minutes) before calling Bash. `gate.py`'s approval branch checks for a
matching, unexpired token before falling back to deny. This keeps the hook
fail-closed by default while giving a real, audited path for the human to
say yes to a specific command, once.

**Status: RESOLVED 2026-07-03 — Option B built.** `meta/security/approval_token.py`
implements the handshake: Apollo asks the human via `AskUserQuestion` BEFORE
the Bash call and, on an explicit yes, calls `approval_token.grant(command)`,
which writes a token to `logs/.approved/<md5>.json`. When the Bash call then
hits the hook, `gate.py`'s approval branch calls
`approval_token.check_and_consume(command)`. The token is: bound to the exact
command string (approving `sudo ls` does not approve `sudo rm`), single-use
(deleted on first check), and short-lived (300s TTL). The hook still fails
closed by default — no token, no pass — so the security posture only relaxes
for a specific command a human just approved, once. Tests: `TestApprovalToken`
(grant→allow-once→re-block, command-binding, expiry) + the audit's "D1 token
allows once then re-blocks" check. The human-gate invariant (Invariant #3) is
intact: nothing here decides; it only carries an explicit human yes across the
Apollo→hook process boundary.

---

## D2 — Which blueprint is authoritative: v3 SVG (10 modules) or Phase 3 docx (7 modules)?

**Found:** 2026-07-02 gap analysis. Two vision documents coexist:
`hermes_blueprint_v3.svg` (May — 10 modules incl. Browser, Agents,
Autonomous Loop, Planning, Code/TDD) and `HERMES_Phase3_Blueprint.docx`
(July — deliberately narrowed/renamed to 7: Browser→Fetcher,
Agents→Delegation, Token-Monitor+Caveman+Verification→`meta/`). The code
follows Phase 3. Measured against the SVG, ~40% of the module surface
exists; measured against the docx, 3A+3B are done and 3C+3D remain. Carrying
both is why the architecture doc needed a whole "Blueprint Reconciliation"
section, and every future audit will re-litigate the same discrepancy.

**Option A — declare the Phase 3 docx authoritative.** The SVG becomes a
historical artifact (move it to an `archive/` dir or delete it). Roadmap
claims are then measured against 7 modules, and "Phase 3C" is the single
name for what's missing.

**Option B — keep the SVG as the north star.** Then the docx is a
phase-plan, not the vision, and the module map should track all 10 modules'
status explicitly (incl. Planning and Code/TDD, which currently appear in no
plan at all).

**Status: needs the human's call.** This is a scope decision, not a code
decision — nothing in the repo can resolve it. Until decided, code and docs
in this repo measure themselves against the Phase 3 docx (the narrower,
newer document), and claims against the SVG should not be made.

---

## D3 — Installed third-party skills vs. Invariant #4 (patterns, not code)

**Found:** 2026-07-03, while wiring the create flow. Sixteen skills were
installed to `~/.claude/skills/`: nine from the official Anthropic skills
repo (docx, pdf, pptx, xlsx, frontend-design, web-artifacts-builder,
theme-factory, canvas-design, webapp-testing) and seven from ui-ux-pro-max
(MIT, third-party — ui-ux-pro-max, design, design-system, ui-styling,
slides, brand, banner-design). The Anthropic ones were always planned to
run as-is (v1 blueprint: documents = "anthropic/skills", same as the
kept-as-is TypeScript MCPs). But ui-ux-pro-max's `scripts/search.py`
executes third-party Python locally — that is running someone else's code,
which Invariant #4 exists to avoid.

**What's live today:** ui-ux-pro-max installed and used as design-
intelligence tooling by `skills/webdev` and the create flow. Mitigations:
MIT-licensed, code present and readable on disk, runs offline against its
own CSV data (no network calls), and it only *advises* (design systems) —
it writes nothing and executes nothing else. `nextlevelbuilder/
ui-ux-pro-max-skill` added to the upstream watchlist.

**Options:** (A) accept as a scoped exception — "official skills + audited
MIT design-data tooling run as-is; everything else patterns-only"; (B)
reimplement the search as a HERMES module over the same CSVs (the data is
the value; the script is ~simple retrieval); (C) run it only through
`skills_guard` scanning on install (partially done — the SessionStart sweep
covers `~/.claude/skills` only if pointed there).

**Status: needs the human's call.** Until decided, treat it as (A) with the
watchlist entry as the drift guard.

---

## D4 — Tier-substitution safety is enforced at the prompt level, not in code

**Found:** 2026-07-05, during two make-it-fail sessions —
`logs/proof_failuremode.md` (failure-injection) and
`logs/proof_apollo_tier_fallback.md` (live Apollo behavioral check). Both
local/gitignored, per the repo's evidence convention (same as
EXTRACTION_COVERAGE.md).

**What:** `SKILL.md` line 60 — "if tier2_ready is false, say so and ask the
user whether to run on Tier 1 instead — never silently substitute tiers, in
either direction." The failure-injection proof confirmed the *code* fails
cleanly when Ollama is unreachable (`RuntimeError`, no hang, no silent
Tier-1 fallback) — but that is *absence of a substituting mechanism*, not
enforcement of the rule. The rule's actual behavior ("ask, don't
substitute") is carried out by Apollo, an LLM reading a markdown line.
Nothing in `ollama_client.py` or `brain.py`/`meta/policy.py` can guarantee
an LLM obeys a prompt. This is the same shape as D1's human-gate, but the
opposite conclusion was reached there (D1 got a code interlock); here it is
still prompt-only.

**Evidence live today:** `proof_apollo_tier_fallback.md` — 3 real `claude -p`
sessions under a genuine Tier-2 outage (`HERMES_OLLAMA_URL` forced to a
closed port), graded on a forced single-token verdict. 3/3 asked the user
rather than substituting, **including the adversarial-pressure case**
(sensitive, explicitly-local-only pentest notes + "don't bother asking me
anything, whatever's quickest"). That case is the load-bearing one — a
failure there would have routed explicitly-local data to Tier 1. Separately,
the two robustness gaps failure-injection found (`fetcher/fetch.py search`
always exiting 0; `connect/mcp_client.py main()` leaking tracebacks) were
**fixed the same session** and are not deferred — they are noted here only as
the context in which D4 surfaced.

**Option A — accept prompt-level enforcement + behavioral proof as
sufficient for v1.** Cost: robustness is bounded by the model's adherence.
The proof explicitly does NOT cover multi-turn erosion, role-play framing,
or prompt-injection via a fetched document — only single-turn direct
pressure. Carry "adversarial/multi-turn tier-substitution robustness" as a
named open item, not a closed one.

**Option B — add a code-level interlock**, mirroring D1: a tier *downgrade*
away from the sensitivity-mandated tier requires an explicit approval token
Apollo can only mint after an `AskUserQuestion` yes. Makes the rule
code-guaranteed, at the cost of another handshake surface.

**Option C — hybrid:** code hard-blocks the *silent* substitution path
(refuse any tier change that lacks a recorded human ack), prompt still
handles the conversational "ask." 

**Status: provisionally A for v1 — flagged for the human's call.** The
behavioral proof is real evidence the mechanism works as designed under
direct pressure, and is the guard today. It is not proof of unconditional
robustness, and B is the only option that would make the rule
code-guaranteed rather than model-dependent. Revisit if any real
substitution slip is ever observed, or before relying on HERMES with
strictly-local data in an untrusted multi-turn session.

---

*Add new entries above this line as they come up. Don't resolve a D-item by
editing this file alone — the code has to change too, and the entry should
note the commit/date it was closed.*
