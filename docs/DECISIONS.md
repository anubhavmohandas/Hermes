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

## Gate 3 — Unattended execution threat model: cron/scheduler.py + delegation/agenda.py (STANDING, closed 2026-07-10)

**The threat:** both modules run commands with nobody present to approve
them in the moment. `approval.classify_command()` (the shared denylist) is
necessarily incomplete — it pattern-matches known-dangerous shapes (`sudo`,
`rm -rf`, `DROP TABLE`, …) but cannot enumerate every destructive command a
denylist wasn't written to recognize (`find / -delete`, a `python3 -c`
one-liner that `shutil.rmtree`s a tree, reading `~/.ssh/id_rsa` for
exfiltration — none of these match a denylist pattern but are exactly as
dangerous). A single denylist, run with `shell=True`, is the wrong shape for
something that runs unattended: a shell interprets `;`, `|`, `` ` ``, `$()`,
and `<>` redirection regardless of what the denylist caught, so any gap in
the denylist becomes a real shell injection with nobody watching.

**The fix, two independent layers (audit M3, 2026-07-05):**
1. **Positive allowlist, not just denylist** — `cron/scheduler.py`'s
   `classify_unattended()` requires every unattended command to be either a
   HERMES-internal `python3 <script-under-HERMES_ROOT>` invocation (inline
   `-c`/`-m` refused, script path must resolve inside `HERMES_ROOT`) or one
   of five trivially-safe binaries (`echo`, `true`, `false`, `sleep`,
   `date`). Anything else is refused — including everything the denylist
   alone would have called "safe." There is deliberately no override flag.
2. **`shell=False` at the execution site** — `_run_job()`
   (`cron/scheduler.py`) runs `subprocess.run(shlex.split(command),
   shell=False, ...)`. Even if a command somehow passed classification with
   a shell metacharacter in it (defense-in-depth, not the expected path —
   `_SHELL_META_RE` already refuses these at classify-time), `shell=False`
   means there is no shell present to interpret `;`/`|`/`` ` ``/`$()` — the
   whole string becomes one literal argv to one binary. `delegation/agenda.py`
   never shells out directly at all: it spawns a `claude -p` child via
   `subprocess.run(argv, ...)` (argv vector, not a string), and Bash access
   for that child is granted only when the human passed `--allow-bash` at
   add-time (Invariant #3 — unattended runs never self-escalate); whatever
   that child does with Bash still passes through the platform's own
   `PreToolUse` gate (`verify.sh`), the same enforcement every other tool
   call gets.

**Residual risk, stated plainly:** the allowlist is narrow by design (five
binaries + HERMES's own scripts) — this trades flexibility for the property
that "unattended = nobody to ask" never expands into "unattended = trust a
denylist to have thought of everything." `agenda.py`'s external-workspace
mode (`--workspace <path>`) is cwd+prompt constraint, not a filesystem
jail — an agent granted `--allow-bash` there can still write anywhere it has
OS-level permission to; that is a documented, accepted risk of granting
`--allow-bash` at all, not a gap in this hardening pass.

**Evidence (Gate 3, 2026-07-10):** `python3 -m unittest test_hermes.TestCron -v`
— 8/8 passing, including `test_unattended_allowlist_blocks_denylist_safe_but_dangerous`
(five denylist-safe-but-dangerous strings, all refused),
`test_unattended_allowlist_permits_hermes_entrypoints` (legitimate commands
still work), and the new `test_shell_false_execution_neutralizes_chained_injection_payload`
— a literal `;`-chained payload (`echo safe; touch <marker>`) run through
the exact `shlex.split(...)  + shell=False` primitive `_run_job` uses,
proving the marker file is never created. Full transcript:
`logs/proof_gate3.md`.

**Status: CLOSED.** Both required elements present — code hardening
(shell=False + positive allowlist, predates this entry) and a test proving
a known denylist-bypass string no longer executes (added 2026-07-10).

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

## D5 — HERMES's security gate is unconfirmed (and probably inactive) on the Cowork platform

**Found:** 2026-07-06, direct test in a Cowork session with the `hermes`
plugin installed and enabled. `plugin.json` lists `"platform": ["cli",
"cowork"]`, implying the `PreToolUse` hook (`hooks/verify.sh`) applies on
both. Ran `sudo id` via Cowork's own Bash tool (`mcp__workspace__bash`) to
test it — the same class of call the CLI-side proof
(`logs/reflexion_seed.json`, 2026-07-05) confirmed `verify.sh` blocks with a
distinct BLOCKED entry. In Cowork, it just ran and failed for an unrelated
container-permission reason, with no sign of the hook touching it.

**Why this is plausible, not just a fluke:** `PreToolUse` hooks attach to a
specific tool-calling pipeline. Cowork's Bash tool is a separate MCP-based
tool (`mcp__workspace__bash`), architecturally distinct from the CLI's
native tool-call loop that the hook is registered against. The skill/prompt
layer (Apollo, routing, Mnemos recall) demonstrably works in Cowork — tested
separately, confirmed live — but that's a different mechanism (an LLM
reading and choosing to follow `SKILL.md`) than a hook that fires regardless
of what the model decides.

**Consequence if true:** the core invariant "nothing bypasses the security
gate... it can't be talked around" (README, `SKILL.md`) holds on the CLI
(proven, 2026-07-05) but does NOT hold on Cowork — a materially weaker
guarantee than the docs currently imply for a platform `plugin.json` lists
as supported.

**Options:** (A) accept Cowork as skill-layer-only, no enforced gate, and
say so explicitly in README/SKILL.md rather than implying parity across
platforms; (B) find whether Cowork has its own hook-equivalent mechanism and
wire `verify.sh`'s logic into it; (C) drop `cowork` from `plugin.json`'s
declared platforms until B is resolved, so the manifest doesn't claim
security parity it hasn't got.

**Status: needs the human's call — single data point (one blocked-command
test), not exhaustive.** Until decided, treat any Cowork HERMES session as
running with Apollo's cooperation, not the CLI's enforced gate.

---

## D6 — Clio's Tier-2 (Ollama) token/latency logging is demonstrably incomplete

**Found:** 2026-07-06, live `clio/tracker.py` run against the real
`logs/reasoning_seed.jsonl`. Two Tier-2 entries showed `tokens: 0,
latency_ms: 0`, despite a real `ollama_client.py chat` call earlier the same
day (2026-07-05, Gate 4 proof) returning genuine non-zero values
(`tokens=37, latency_ms=1411`). Something is reaching Clio's log without the
real numbers attached.

**Why:** per `SKILL.md` §2 step 6o, feeding Tier-2 tokens/latency into the
log is something Apollo is instructed to do after each response — a
prompt-level habit (an LLM following a written step), not a return value
`ollama_client.py` pipes into logging automatically itself. Same enforcement
shape as D4 (rule lives in a markdown instruction, not in code that
guarantees it happens every time).

**Consequence:** Clio's Tier-2 cost/latency numbers cannot currently be
trusted as complete — some real local-model usage silently reads as
free/instant. This also bears on the "how much have I used" question
users may ask HERMES: the honest answer today is Clio has no access to
Anthropic's actual account-level usage/quota at all (verified: no
usage/quota/remaining-balance code exists anywhere in the repo), and even
its own local tally has a known gap.

**Options:** (A) have `ollama_client.py.chat()` write the log entry itself,
directly, right after a successful call — moves this from prompt-dependent
to code-guaranteed, mirrors the D1/D4-Option-B pattern; (B) leave it
Apollo-driven but add a test that fails if a real `chat()` call isn't
followed by a matching non-zero log entry within the same session; (C)
accept the gap as a known Clio limitation and say so in README's "Known
limitations" section rather than implying Clio's numbers are complete.

**Status: needs the human's call.** Option A is the cheapest fix and
directly closes the gap; flagging here rather than quietly patching it
because it changes where the log-write responsibility lives (code vs.
prompt), which is exactly the kind of call D1/D4 said belongs to a human.

---

## D7 — Multiple concurrent Claude sessions can write to the same repo with no designated driver

**Found:** 2026-07-05/06, repeatedly, during the same work described in D5
above. A VS Code Claude Code session and this Cowork session were both
making commits to `hermes` in the same window, with neither aware of the
other's state. Concretely: a commit titled `"MCP"` (`b14a2d3`) landed,
containing five files this session had just been told still needed
committing — the other session had already committed them moments earlier.
No data was lost (verified both times by diffing the actual commit against
what was claimed), but it produced confusing provenance, redundant
instructions, and one wasted round of `git add` that had nothing left to
stage.

**Why this matters beyond today:** the failure mode isn't limited to
confusing commit messages — two sessions editing the same file close
together risks a genuinely lost write, and a session trusting a stale
mental model of `git status` can give instructions that silently no-op or
conflict.

**Options:** (A) designate one session as the sole driver for git operations
at any given time, treat others as read-only/advisory; (B) accept the risk
and make "verify actual git state before instructing any git command" a
standing rule for every session (partially already true this session — see
`feedback_hermes_verify_before_trusting_reports` in Cowork memory); (C) use
a branch per active session and merge deliberately, rather than everyone
committing straight to `main`.

**Status: needs the human's call — currently running as an unmanaged
version of (B).** No incident has caused real damage yet; this is a
before-it-does entry, not an after-the-fact one.

---

## D8 — `cron/cron.db` (SQLite) writes fail on Cowork's FUSE mount — the exact Mnemos failure mode, recurring

**Found:** 2026-07-10, while building `delegation/start_loop.py` (a UX
wrapper over `agenda.add()` / `cron_scheduler.add_job()`, no new logic) and
testing it for real in this Cowork session. `agenda.install_cron()` — which
calls `cron_scheduler.add_job()` — raised `sqlite3.OperationalError: disk
I/O error`. Reproduced a second time directly against `cron_scheduler.add_job()`,
same error both times. `df -T` confirms `/sessions/.../mnt/HERMES` (this
session's view of the repo) is `type fuse`. `cron/cron.db` sits at 0 bytes
with an orphaned `cron/cron.db-journal` (512 bytes, identifies as "SQLite
Rollback Journal") that a subsequent clean `sqlite3.connect()` + integrity
check does NOT clear — `PRAGMA integrity_check` reports `ok` but
`sqlite_master` has zero tables, meaning the `CREATE TABLE IF NOT EXISTS
jobs` in `_connect()` has never successfully committed on this mount.

**Why this matters — this is not a new bug class:**
`HERMES_STABILIZE_PROMPT.md` invariant 6 already names this exact failure
mode: "Prove on REAL local disk, never the FUSE/Cowork mount (that is what
broke Mnemos before)." Cron.db uses the same SQLite-WAL pattern Mnemos
does, and now shows the same symptom. FUSE mounts (at least this one)
appear not to support the file-locking semantics SQLite depends on for
safe concurrent writes/journal replay.

**What I could NOT determine:** whether `cron/cron.db` ever held real job
rows before today. `cron/cron.db*` is gitignored (machine-local state by
design — see `cron/scheduler.py`'s own header comment), so git has no
history to check. No proof file (`logs/proof_gate*.md`) or `debug.log`
entry shows a prior successful `add_job()` call. The likelier read: this
Cowork-mounted `cron.db` never had a working `jobs` table in the first
place (the FUSE incompatibility would have blocked table creation from the
very first write attempt on this mount), and today's test simply surfaced
a latent, previously-unexercised gap rather than destroying prior state —
but this is inference, not proof, and is flagged as such.

**Consequence:** any Cowork session that calls `cron_scheduler.add_job()` —
directly, via `agenda.install_cron()`, or via the new
`delegation/start_loop.py` — will hit this. `agenda.add()` itself is
unaffected (it stores each agenda as a plain JSON file, not SQLite) and
worked correctly in the same test.

**Options:** (A) treat this as CLI-only going forward — document plainly
that `cron/scheduler.py` (and anything that calls into it, including
`agenda.install_cron()`) must be run from the real Mac, never Cowork, and
have `start_loop.py` detect the FUSE mount and warn before attempting the
cron path; (B) investigate whether SQLite's `PRAGMA journal_mode=DELETE`
(no WAL) or a different locking mode tolerates this specific FUSE
implementation better, the way Mnemos's fix (if any) was resolved —
unknown, not yet checked; (C) accept Cron as CLI-only permanently — it
already requires launchd (Invariant #7) for the tick itself, so requiring
CLI for job *creation* too may just be honest about an already-CLI-bound
subsystem, not a new limitation.

**Status: needs the human's call.** Immediate, low-risk workaround
available now: create cron jobs via `delegation/start_loop.py` or
`cron/scheduler.py add` from the CLI host, not Cowork. Agenda-only setups
(no cron install) remain fine from either environment.

editing this file alone — the code has to change too, and the entry should
note the commit/date it was closed.*

## D9 — `agenda.py tick()` silently no-ops forever under launchd if `claude` isn't on its minimal PATH (closed 2026-07-11)

**Found:** 2026-07-11, live on the production Mac. `launchctl list` showed
`com.hermes.cron` running, `cron/scheduler.py list` showed `agenda-tick`
with `last_status: "completed"` and `runs_completed: 26`, but
`agenda.py show <id>` stayed at `attempts: 0, last_attempt_at: null` — for
an agenda created ~6.5 hours earlier, almost exactly matching 26 ticks at
the 900s interval. Every tick since creation had silently done nothing.

**Root cause:** `tick()` (delegation/agenda.py) calls
`dispatch.claude_cli_available()` (`shutil.which("claude")`) before
touching the agenda; `dispatch.build_child_command()` also spawns via the
bare literal `argv[0] = "claude"` — both are PATH lookups. launchd's
environment is not the interactive shell's environment, so if `claude`
lives somewhere PATH-dependent (nvm/npm-global/homebrew/etc.), the check
fails every time. `tick()` returns early before incrementing `attempts` or
setting `last_attempt_at`, and since nothing on that path calls
`sys.exit(1)`, the process exits 0 — so `cron/scheduler.py` logs
"completed" with no way to distinguish "did nothing, PATH problem" from
"did nothing, no active agenda." No error surfaces anywhere. Exact same bug
class as the `__PYTHON_BIN__`/TCC issue closed 2026-07-10 (SCHEDULING.md),
hitting a different binary.

**Fix:** `hooks/com.hermes.cron.plist.template` now sets
`EnvironmentVariables/PATH` via a new `__PATH__` placeholder, substituted
from the interactive shell's `$PATH` at render time (same sed one-liner in
docs/SCHEDULING.md, updated). This fixes both the `claude_cli_available()`
check and the actual child spawn in one place, since both resolve `claude`
via the same inherited process environment.

**Status: CLOSED** — template + docs updated 2026-07-11. Verification is
on the user: re-render and reload the plist, then confirm `agenda.py show
<id>` shows `attempts` incrementing and `last_attempt_at` no longer `null`
after the next tick.

## D10 — `skills/webdev` silently skips steps 1-2 (design-system search, token scaffold) when brand assets already exist, no degradation notice

**Found:** 2026-07-11, live transcript review of a real Aegis landing-page
build. The skill ran step 3 (plain HTML scaffold, correct pick for a
landing page), step 4 (real copy, no lorem ipsum — verified against the
actual README), and step 5 (webapp-testing QA — real Playwright
screenshots, desktop+mobile, iterative fixes) faithfully. Steps 1
(`ui-ux-pro-max/scripts/search.py --design-system`) and 2
(`integrations/webdev.py tokens --out <dir>` → separate `tokens.css` +
JSON mirror) never ran. The model went straight from reading the existing
logo/tray-icon/favicon files to hand-writing CSS custom properties inline
in `index.html`'s `<style>` block — a reasonable design decision (grounded
in real brand assets, not invented), but not what the skill documents, and
not disclosed as a deviation. The skill's own rule ("if ui-ux-pro-max is
missing, degrade and SAY SO") was not followed either way — it wasn't
missing, it just wasn't invoked, silently.

**Why this matters:** the pipeline's honesty guarantee ("don't silently
ship the placeholder palette as if it were designed") only covers the
missing-tool case. It has no equivalent rule for "tool is installed but I
decided not to call it because brand assets already exist" — that path
skips silently with no disclosure and no fallback statement, which is a
gap in the skill's own logic, not just an execution slip.

**Consequence:** design output quality wasn't provably worse here (see
review above — copy and QA were solid), but there's currently no way to
tell "design system was consulted" from "design system was skipped" by
reading the delivery message alone — only by diffing the transcript
against the documented steps, which is not something most sessions get
reviewed this closely.

**Status: OPEN, deferred by user 2026-07-11** — "let it go as it is going"
for the current Aegis build; not blocking. Needs a human call on the actual
fix later: either (A) `skills/webdev` step 1 should still run
`ui-ux-pro-max` search even when brand assets exist, just weighted toward
matching the existing brand rather than inventing one, or (B) add an
explicit "skipping design-system search — existing brand assets found at
X, anchoring off those instead" disclosure line so the skip is visible
without needing a transcript audit.

---

## D11 — Laconic mode built; Clio's disk-reading gap closed for Claude Code CLI (CLOSED, 2026-07-13)

**Found:** user asked about two third-party plugin patterns from the
extraction corpus by garbled/mistranscribed names ("Caveman", "CodeBurn").
Verification against `CC_SRC_PATTERNS.md` (#161-166, Task #29) and
`CC_SRC_ANALYSIS_LOG.md` (codeburn, 216 files, Task #27/#47) confirmed
both were real, extracted patterns — but the user's own description of
CodeBurn ("remembers bad habits and patches itself") did not match its
actual function (disk-based token/cost tracking across 18 tools); that
was a genuine misconception, corrected before any code was written.

**Gap 1 — Caveman/token-reduction mode:** `HERMES_GapAnalysis_2026-07-02.md`
line 82 (frozen snapshot, not edited retroactively — see that doc's own
dating) recorded this as "only `output-styles/terse.md`; ~75% reduction
not built." Now built: `meta/laconic.py` (flag-file IPC per #162,
activation/deactivation phrase detection + per-turn reinforcement per
#161, auto-clarity override per #164, sensitive-path denylist +
structural compression validator per #163/#165), `hooks/laconic_mode.sh`
(UserPromptSubmit wrapper, same contract as `apollo_gate.sh`),
`skills/laconic/SKILL.md`. Renamed from the upstream pattern's own name
on integration, per HERMES's existing convention (Apollo, Mnemos, Clio,
Curator) — "Laconic" for Laconia/Sparta, historically associated with
extreme brevity of speech. Moved from `modules.opt_in` to
`modules.active` in `plugin.json` (the hook is always wired; the *mode*
itself is opt-in at runtime via natural-language toggle, not at
install-time). Tested end-to-end: activation/deactivation via flag file,
clarity-override suspension, JSON hook contract — all pass (synthetic
stdin, see session transcript).

**Gap 2 — Clio (codeburn pattern):** `EXTRACTION_COVERAGE.md` row 17
marked ✅ but `clio/tracker.py` only ever aggregated HERMES's own internal
log (`logs/reasoning_seed.jsonl`) — it never read any *external* tool's
session data off disk, which is the actual codeburn pattern (18 tools,
JSONL/SQLite/protobuf, no proxy/API key). Added `clio/cc_reader.py`: reads
real Claude Code CLI session JSONL under `~/.claude/projects/`, tolerant
of malformed lines, degrades to empty (not an error) when the directory
doesn't exist. `tracker.py` gained `report_all()` merging internal +
external sources and a `--source {internal,claude-code-cli,all}` CLI flag.
Tested against a synthetic fixture (3 turns, 2 models, one malformed
line) — parses correctly, malformed line skipped silently as designed.
Also tested against this sandbox's real (absent) `~/.claude/projects/` —
degrades to zero cleanly, no exception.

**What's still open, disclosed rather than silently left out:**
1. Only 1 of the pattern's original 18 tracked tools is covered
   (Claude Code CLI). Cursor (SQLite), Gemini (protobuf), and the other
   ~15 are not implemented — would each need their own reader module
   following the same `cc_reader.py` shape.
2. `cc_reader.py`'s parsing of the Claude Code CLI's JSONL schema is
   **confidence: LIKELY, not CERTAIN** — it's not an officially
   documented format and could shift between CLI versions. The reader
   is defensive (skips what it can't parse) but was never validated
   against a real `~/.claude/projects/` directory, only a synthetic
   fixture, because none exists on this sandbox.
3. `MODEL_PRICING_PER_1M` in `cc_reader.py` is a snapshot, explicitly
   flagged in-code as not guaranteed current — same caveat the existing
   `TIER_RATES_PER_1K` in `tracker.py` already carried.
4. No macOS-menubar or GNOME-extension surface was built — out of scope
   for a CLI-first plugin; the underlying JSON output contract
   (`report_all()`) is what a future GUI surface would shell out to,
   same separation-of-concerns the upstream project used.

**Status: CLOSED** for the scope stated above — both patterns went from
"extracted but not integrated" to "integrated and tested." Item 1 (tool
coverage breadth) and item 2 (schema confidence) are follow-up work, not
blockers, and are logged here rather than silently assumed complete.

---

## D12 — Occam: ported from a user-uploaded third-party plugin zip, not the 58-item Extractions/ corpus (CLOSED, 2026-07-16)

**Found:** user uploaded `ponytail-main.zip` (a third-party multi-host
agent plugin, MIT licensed, ~4.8.4) and asked for it to be added to
HERMES. This is NOT one of the 58 folders `EXTRACTION_COVERAGE.md` audits
— that doc's table is deliberately left untouched, since inserting a row
there would misrepresent what that dated audit actually covers. This
entry is the only record of the port.

**What the source project actually is, corrected against the user's own
description:** the user described it as a static analyzer that shrinks
an existing large codebase after the fact. That is only one piece of it
(`ponytail-audit`, whole-repo). The primary mechanism is the same
architecture family as Laconic/Caveman ([[D11]]): a `SessionStart` +
`UserPromptSubmit` + `SubagentStart` hook-enforced behavioral mode that
makes the agent write less code *as it writes new code*, via a 7-rung
ladder (YAGNI → reuse-in-repo → stdlib → native platform → installed dep
→ one line → minimum), at three intensities (lite/full/ultra) plus an
independent `review` mode. Five satellite skills ship alongside it:
`-review` (diff), `-audit` (whole repo, the part matching the user's
original description), `-debt` (harvest `<marker>:` shortcut comments
into a ledger), `-gain` (benchmark scoreboard), `-help`.

**Non-obvious discovery, worth flagging plainly:** the source repo already
documents installation for something it calls "Hermes Agent" —
`hermes plugins install owner/repo`, a Python `__init__.py` with
`register_skill/register_hook/register_command`, a `plugin.yaml` manifest.
This is a real, unrelated third-party agent-gateway product that happens
to share the name "Hermes." It is not this project. Pure name collision,
confirmed by reading `tests/hermes-plugin.test.js` and `__init__.py`
directly — no relationship, no shared code, no integration path between
that product and this one. That said, `__init__.py`'s Python mode-filtering
logic (`_filter_skill_body_for_mode`, `build_injected_context`) was a
useful reference for porting the Node.js hook logic to `meta/occam.py`,
since it's already in the same language HERMES uses.

**Renamed on integration**, per the same convention as Apollo/Mnemos/
Clio/Laconic: **Occam**, for Occam's razor (entities should not be
multiplied beyond necessity) — accurate to what the module does, not
reused from the source project's own name. Comment marker for deliberate
shortcuts changed from the source's own marker to `occam:` throughout.

**Built:**
- `meta/occam.py` — mode state (flag-file IPC, same pattern as
  `meta/laconic.py`), config resolution (env var `OCCAM_DEFAULT_MODE` >
  `~/.config/occam/config.json` > `full`), `/occam` command parsing,
  skill-body mode-filtering (ported from the source's own Python
  reference), subagent matcher scoping (`OCCAM_SUBAGENT_MATCHER`,
  fail-open on bad regex or missing `agent_type`), BOM-safe stdin JSON
  parsing (also retrofitted into `meta/laconic.py` for the same class of
  robustness — was missing there too).
- `hooks/occam_activate.sh` (`SessionStart` — full ruleset once,
  writes the flag, one-time statusline setup nudge), `hooks/occam_mode_tracker.sh`
  (`UserPromptSubmit` — command parsing + short per-turn reminder while
  active), `hooks/occam_subagent.sh` (`SubagentStart` — propagates to
  Task-spawned subagents, which never see `SessionStart` context
  otherwise; this closes the same gap the source project's own issue
  #252 describes).
- `hooks/hermes_statusline.sh` — combined Occam+Laconic mode badge,
  ported from the source's single-mode statusline script, extended to
  read both flags since HERMES now has two.
- `skills/occam/SKILL.md` + `skills/occam-{review,audit,debt,gain,help}/SKILL.md`.
- `scripts/occam_laconic_cleanup.py` — ported from the source's own
  `scripts/uninstall.js`; removes both mode flags, Occam's config file,
  and (only the segment it owns) a combined statusLine entry.
- `test_hermes.py`: `TestOccam` (10 new unit tests covering command
  parsing, exact-match deactivation, default-mode merge-not-overwrite,
  review-never-a-valid-default, skill-body mode filtering, subagent
  matcher fail-open semantics) + `laconic`/`occam` both added to
  `TestActiveModulesProvablyRun.MODULE_ENTRYPOINTS`. 185 tests total,
  same 2 pre-existing environment failures as [[D11]] (missing `hnswlib`,
  FUSE permission error), nothing new broken.

**Deliberate deviation from the source, disclosed:** the source only
re-injects its ruleset at `SessionStart` + on an explicit mode switch.
HERMES's own established doctrine ([[D11]], `hooks/apollo_gate.sh`,
pattern #161) is that long sessions drift without per-turn reinforcement,
so `UserPromptSubmit` here also emits a short one-line reminder every
turn — not the full ladder text, which would be the exact bloat this
module exists to cut.

**What's still open, disclosed rather than silently left out:**
1. `/occam-gain`'s numbers are the source project's own published
   benchmark (real FastAPI+React repo, Haiku 4.5, n=4) — explicitly
   labeled as not a HERMES-measured figure in the skill itself. Building
   an actual HERMES-run benchmark (the source's own `benchmarks/`
   harness) was scoped out of this session as a substantial separate
   effort, not silently dropped.
2. ~13 other-agent-host adapter directories in the source zip
   (`.cursor/`, `.windsurf/`, `.clinerules/`, `.codex-plugin/`,
   `.devin-plugin/`, `.openclaw/`, `.opencode/`, `.qoder/`,
   `.qoder-plugin/`, `AGENTS.md`, `ponytail-mcp/`, `pi-extension/`,
   `gemini-extension.json`) were not ported — out of scope, HERMES is
   Claude-Code/Cowork-only, porting them would mean building adapters
   for hosts HERMES doesn't run on.
3. Found mid-session: an unexplained, already-on-disk uncommitted diff
   to `README.md` (an Occam row + a "Create flow" row, accurate content
   this session didn't write) and a stale `.git/index.lock` this session
   could not remove (permission denied — same FUSE-mount class of issue
   as [[D8]]). No active git process was found holding the lock. Left
   the README content in place (accurate, non-conflicting) rather than
   fight it; flagged to the user directly as an open question, not
   silently absorbed as this session's own work. Possible explanation:
   the multi-session risk already documented in [[D7]].

**Status: CLOSED** for the scope stated above.

---

## D13 — `/goal` hardcoded HERMES's own roadmap regardless of project; made general-purpose (CLOSED, 2026-07-25)

**Found:** user ran `/goal` and got HERMES's own end-goal roadmap
(Stages 0–5, NYX excluded) printed back, in a session with no HERMES-goal
work actually in play. User's position: HERMES is a general-purpose
plugin (its execution skills — webdev, documents, research, tasks — route
in any project per `apollo_gate.sh`), so `/goal` should behave the same
way, not be special-cased to only ever describe HERMES itself.

**Why this was hardcoded in the first place:** `commands/goal.md` rule 1
said "state this verbatim, do not soften" about HERMES's own goal text —
that was correct for the command's original purpose (track HERMES's own
build against `HERMES_GOAL_Start_to_End.md`) but nothing distinguished
"the project /goal should describe" from "the project HERMES's own docs
happen to live in." Every other project got HERMES's roadmap by default,
which is wrong for a general-purpose plugin — same silent-substitution
shape as [[D10]] (webdev skipping steps without disclosure), just in the
opposite direction: printing something *unrequested* instead of skipping
something *requested*.

**Fix:** `commands/goal.md` now runs a Step 0 source-selection check before
anything else: look for `./GOAL.md` then `./.claude/GOAL.md` in cwd. If
found, that project's file is the source of truth for `full`/`status`/
`next`/stage-number, and HERMES's own 6-stage schema is not forced onto a
project that was never written in that shape. If not found and cwd is the
HERMES repo itself (checked via `HERMES_GOAL_Start_to_End.md` at project
root), fall back to HERMES's own roadmap — the original behavior, now
correctly scoped. If not found and cwd is any other project, `/goal` says
"No GOAL.md found for this project. Want me to help draft one?" and stops
— it does not silently substitute HERMES's roadmap for a project that
isn't HERMES.

**What's still open, disclosed rather than silently left out:**
1. No `GOAL.md` template/scaffold command exists yet — if a user says
   "yes, help me draft one," there's no `hermes:goal-init` or equivalent
   to generate the file interactively. The routing logic assumes the file
   either exists or doesn't; creating it well (stages? plain prose? gates?)
   is unscoped follow-up work.
2. Projects with an existing goal-tracking doc under a different filename
   (e.g. `ROADMAP.md`, `PLAN.md`) won't be picked up — only `GOAL.md` and
   `.claude/GOAL.md` are checked. Widening the search path was left out to
   avoid false-positive matches on unrelated docs.
3. Not tested against a real second project in this session — verification
   is on the user: run `/goal` in a non-HERMES project with no `GOAL.md`
   and confirm it produces the disclosure message rather than HERMES's
   roadmap, then add a `GOAL.md` there and confirm it switches source.

**Status: CLOSED** for the routing-logic scope stated above. Items 1–3 are
follow-up work, not blockers.
