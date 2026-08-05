# v1.0 release checklist

This is a **release** list, not a feature list. When every box is checked, tag
`v1.0.0`. New capabilities go to the post-1.0 backlog — they do not reopen
this list.

**Ground rule (architecture freeze):** no new top-level folders, no new
subsystems. A feature either fits inside an existing module or it waits for a
real user to force the change. The current subsystem set (Apollo, brain,
meta/security, Mnemos, Clio, Curator, ReasoningBank, Cron, Delegation,
Fetcher, Connect, integrations) is final for v1.0.

Verified baseline at creation (2026-07-03, commit `5d0d3df`):
144/144 tests passing (2 environment-conditional skips by design), clean
tree, ~5.8k production LOC, largest file 409 lines, dependency graph clean
except two inverted imports (listed below).

---

## 1 — Architecture

- [x] Extraction corpus fully dispositioned — 58/58 rows in
      `EXTRACTION_COVERAGE.md` (kept local, untracked since 2026-07-04),
      one deferred gap (graphify) documented
- [x] Architecture freeze recorded in `DECISIONS.md` (date + rationale) —
      2026-07-05, as a STANDING decision at the top of `DECISIONS.md`.
      `meta/policy.py` landing *inside* `meta/` (a file, not a new subsystem)
      is cited there as the concrete evidence the freeze is enforceable, not
      aspirational.
- [x] Fix the only two inverted imports — subsystems reaching up into the
      orchestrator for policy calls:
      - `integrations/notebooklm.py` (`brain.check_sensitivity`)
      - `meta/security/audit.py` (`brain.check_sensitivity` /
        `check_model_allowed` / `get_tier` / `log_request`)
      **Done 2026-07-05:** policy core (sensitivity/tier/model-exclusion rules
      + the request/failure logs) extracted verbatim to `meta/policy.py`, a
      leaf with no orchestrator dependency. Both subsystems now
      `from meta import policy` and call downward. `brain.py` re-exports every
      policy name, so `ollama_client.py`, `tier3.py`, the CLI and tests keep
      using `brain.<fn>` unchanged (verified: `brain.check_sensitivity is
      meta.policy.check_sensitivity`). One test-plumbing follow-on:
      `TestBrainLogging` now patches `policy`'s log globals (their true owner)
      instead of `brain`'s re-exported aliases.
- [x] No circular imports (re-run the import scan after the fix above) —
      2026-07-05: `meta/policy.py` imports stdlib only; `brain`→`policy` is
      one-way; both subsystems import the leaf, not each other. Fresh import
      of every touched module clean; full suite 160 passed / 2 skips / 0
      errors, no `logs/` pollution.

## 2 — Domain models & contracts (targeted, not total)

- [x] Dataclasses at module boundaries only — **done 2026-07-05.** All five
      live in `meta/contracts.py`, a pure stdlib leaf (imports nothing from
      HERMES, so it can't create a cycle; a test asserts this). Placement is
      within the architecture freeze — a new *file* in the existing `meta/`
      kernel, the same precedent `meta/policy.py` set the same day, not a new
      subsystem. Internals still return dicts/tuples; the dataclasses appear at
      the seam. Each carries `to_dict`/`from_dict`(`from_tuple`) adapters so a
      caller that still wants a dict gets one.
- [x] Contract tests pinning the public interfaces — **done 2026-07-05**
      (`TestContracts`, 9 tests). Three seams pinned as thin wrappers over the
      existing internals (which stay for the CLI/hook/legacy callers):
      `gate.check(request) -> SecurityDecision` (over `run_gate`; a test asserts
      the wrapper never diverges from the tuple it wraps),
      `mnemos.search(query) -> list[MemoryEntry]` (over `search_messages`),
      `dispatch_task(task) -> ExecutionResult` + `build_plan`/`dispatch_plan`
      (over `build_child_command`/`_run_child`; the plural `dispatch(prompts)`
      is untouched).
- [x] Explicitly **not** doing: strict typing, 100% type coverage, plugin
      systems, another memory layer (per review 2026-07-03) — **honored:** the
      dataclasses are plain, untyped-beyond-the-fields containers; no strict
      typing, no new memory layer, no plugin system added.

## 3 — Polish

- [x] Dead-code sweep — **done 2026-07-05.** Repo-wide scan: no tracked
      `__pycache__`/`*.pyc`/`.DS_Store` (all gitignored, so already out of the
      git tree); no commented-out code blocks. One genuinely unreferenced
      function, `oauth_pkce.token_request_body` — kept, because it is the
      token-exchange half of the PKCE flow and its sibling `authorization_url`
      is already tested; deleting only the untested half would leave a lopsided
      public API. Turned it from orphaned into covered by adding a symmetric
      test. (The three `fetch.py` `*_open`/`redirect_request` "suspects" are
      urllib handler overrides — live via the framework, not dead.)
- [x] Naming consistency pass — **done 2026-07-05** (surveyed, found coherent).
      Public surface follows a consistent convention: `status()`/`main()` CLI
      pair across ~13 modules, a clean `run_*` family, and the new contract
      names (`search`, `check`, `dispatch_task`) align with it. No churn — the
      surface was already consistent and renaming public names is breakage risk
      for marginal gain.
- [x] Error messages actionable — **done 2026-07-05.** Audited every `raise` in
      production code; most already say what to do next. The one that only
      stated *what failed* — the Mnemos vault-write retry-exhaustion
      `RuntimeError` — now says the remedy (close the other HERMES process
      holding the single-writer lock, or clear a stale `-wal`/`-shm`).
- [x] Execution traces — **done 2026-07-05 for the schema-level gaps.** The
      trace line (`log_request`) now also carries `model` and `decision`, so it
      answers *what decision / which tier / which model / how long*; Clio can
      slice the trace by any field (`aggregate(entries, group_by=...)`) with
      cost computed per-entry-tier under any grouping. New optional params
      default to `None`, so the schema stays a fixed key set and pre-§3 call
      sites are unaffected (`TestExecutionTrace`). The remaining two enumerated
      fields (*which memory was retrieved / why a tool was called*) are
      per-call-site instrumentation to wire opportunistically during the §6
      dogfood window, where the real need for each surfaces — that is what the
      "extend where gaps are found while dogfooding" clause anticipated.

## 4 — Tests & docs

- [x] Full suite green — 144 passed at creation; 174 (172 pass + 2 by-design
      skips) as of 2026-07-05 after the §2/§3 additions (+9 contract tests,
      +4 execution-trace tests, +1 PKCE test); **now 198 (196 pass + 2 skips)
      as of 2026-08-05** after the codebase audit fixes (vendor-prefixed model
      exclusion, NVIDIA readiness probe, curator state-path regression guard,
      reflexion redaction, hook argv cap). The 174 figures elsewhere in this
      file are dated records of what was true on 2026-07-05 and are left as
      written.
- [ ] Suite still green at tag time (re-run on the release commit) — *stays
      open by design; this is a tag-time gate.* Ran green today (174, 2 skips)
      on the working tree, but the box only closes when it is re-run on the
      actual `v1.0.0` commit.
- [x] README claims match reality — **re-synced 2026-07-05.** The §2/§3 work
      moved the count from 157 to 174; updated the claim in `README.md`,
      `SKILL.md`, and `.claude-plugin/plugin.json` (a `git grep "157 tests"`
      now returns nothing). Also added the missing `pip install` step and the
      pre-deps test behavior to the README Setup section.
- [ ] `docs/` current: DECISIONS.md has the freeze entry — **done 2026-07-05**;
      EXTRACTION_COVERAGE.md rows (local, untracked) still true at tag time —
      *re-check at tag; box stays open until that half is verified too.* New
      docs added this session: `docs/WORKFLOWS.md` (§6), `docs/RELEASE_NOTES_v1.0.0.md`
      (§7 draft).

## 5 — Installation from scratch

**Correction (2026-07-05):** the first item as originally written — "passes
pre-deps (Tier C skips correctly)" — was **factually wrong**, and the
fresh-install run is what surfaced it. Pre-deps the suite does **not** pass: it
8-skips Tier C *and deliberately fails one test*,
`TestActiveModulesProvablyRun.test_active_modules_runtime_deps_are_met` — the C6
guard enforcing "a module the manifest calls *active* must provably run."
`mnemos-v2`/`reasoningbank` are active and need `hnswlib`, so that guard is
*supposed* to fail until deps are installed. The corrected criterion is below,
and the README Setup section now documents this so a fresh user isn't surprised.

- [x] Fresh copy + clean venv, corrected sequence — **verified 2026-07-05.** In
      a genuinely clean venv (no site-packages; ran on Python 3.14):
      **(1)** `python3 test_hermes.py` pre-deps → 8 Tier-C skips + the one
      by-design C6-guard failure (correct behavior, not a bug);
      **(2)** `pip install -r requirements.txt` → clean (numpy 2.5.1,
      hnswlib 0.8.0); **(3)** full suite → **174, 2 skips, green.**
      *Caveat:* this was a clean venv on the dev machine, not a bare-OS clean
      machine — it proves dependency isolation and the install/test path, not
      the presence of `python3`/`git`/build tools on a fresh OS. A true
      clean-machine run is best confirmed by the §7 first-external-user step.
- [x] `HERMES.local.md.example` sufficiency — **fixed 2026-07-05.** The fresh
      look found the example's `ACTIVE_MODULES`/`INACTIVE_MODULES` contradicted
      `.claude-plugin/plugin.json` (it listed delegation/cron/fetcher/connect/
      webdev as *inactive* while the manifest and README call them *active*).
      Reconciled the module lists to the manifest, added an `OPT_IN_MODULES`
      line, and pointed the reader at plugin.json as the source of truth. It is
      now internally consistent; "alone is enough" also assumes the two
      documented steps (set `OLLAMA_MODEL`, `pip install`), which the README
      Setup now spells out. External confirmation is the §7 item.
- [x] Plugin installs into a vanilla Claude Code without manual path surgery —
      **manifest verified 2026-07-05; prior live evidence stands.** `plugin.json`
      and `marketplace.json` are valid JSON; hook commands use
      `${CLAUDE_PLUGIN_ROOT}` so the plugin resolves its own paths (README now
      states this). A live plugin-load was confirmed 2026-07-05 (user-scope, via
      the local marketplace — recorded in project memory). *Not re-run this
      session:* a truly-vanilla clean-Claude-Code install is non-interactive
      here; it folds into the §7 external-user step.

## 6 — Dogfood

**Adversarial evidence to date (2026-07-05)** — not yet the 2-week bar, but
the section is not empty either. Three make-it-fail sessions, all with raw
command output (local/gitignored logs):
- Gate 4 — live external paths exercised for real (Ollama/Tavily/MCP), 3/3
  PASS on real infrastructure (`logs/proof_gate4.md`).
- Failure-injection — 6/6 manufactured failure modes handled without failing
  open; **2 real robustness gaps found and fixed same-session**
  (`fetcher/fetch.py search` exit code; `connect/mcp_client.py` traceback
  leak) (`logs/proof_failuremode.md`).
- Apollo tier-fallback — 3/3 obeyed "never silently substitute tiers" under
  a real Tier-2 outage, including the adversarial-pressure case
  (`logs/proof_apollo_tier_fallback.md`; open robustness question recorded as
  `DECISIONS.md` D4).

- [ ] Daily use for 2+ weeks, actively trying to make it fail — **CANNOT be
      met by any amount of work in one session; it is a calendar requirement.**
      Checklist created 2026-07-03; the evidence to date is days, not weeks.
      This box only closes with real elapsed wall-clock daily use. Flagged
      plainly as the one §6 item that no hardening pass can satisfy.
- [x] Every failure captured through Curator — **done 2026-07-05.** The two
      gaps found 2026-07-05 (`fetcher/fetch.py search` exit code;
      `connect/mcp_client.py` traceback leak) were routed through the *real*
      Curator pipeline: `brain.py log-failure` → `consolidate.py` → `propose.py`.
      Both are now in `curator/reflexion.json` (recurrence=1, category
      `validation`). Pre-tag queue review: **pending 3, approved 1, archived 0.**
      They are single-occurrence and already fixed, so they are captured in the
      reflexion record but correctly *not* auto-escalated to proposals (Curator
      proposes for *recurring* failures) — the threshold working as designed,
      no faked recurrence.
- [x] Example workflows written up from real sessions (3+) — **done 2026-07-05**
      (`docs/WORKFLOWS.md`). Three normal-use walkthroughs — Mnemos
      store→recall, Apollo sensitive-vs-bulk routing, Delegation fan-out — each
      run end-to-end with the **real captured output** shown, not prose.
      *Honestly scoped in the doc:* these are verified capability walkthroughs
      from a hardening session, explicitly not a substitute for the organic
      2-week window above.

## 7 — Release

*All four are human/calendar-gated — none can be honestly checked by a coding
pass. Left unchecked on purpose; `docs/RELEASE_NOTES_v1.0.0.md` is drafted so the
tag is a one-step action once they clear.*

- [ ] Demo video recorded — **requires a human recording session.** Cannot be
      produced here.
- [ ] First external user installed and ran it (not the author) — **requires a
      real external person.** Cannot be fabricated.
- [ ] Their first-run friction folded back into §5 — *partial, by proxy:* acting
      as a fresh installer this session surfaced and fixed real first-run
      friction (missing `pip install` step, stale `.example` module lists, the
      C6-guard surprise) — all folded into §5 above. But that is the author's
      proxy, not a genuine external user; this box waits on the item above.
- [ ] Tag `v1.0.0` — **the author's action** (per standing rule, Claude does not
      commit or tag), and gated on everything above. Release notes are ready.

---

*After the tag: reality decides the roadmap. User-reported problems outrank
any "one more cool idea."*
