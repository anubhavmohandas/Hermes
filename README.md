# HERMES

**Hybrid Engine for Research, Memory, Execution & Synthesis**

A personal, multi-model autonomous capability platform built as a Claude Code plugin. Every request routes through a single orchestrator, passes through a security gate that a prompt cannot override, and feeds a self-improvement loop that never applies its own suggestions without a human approving them first.

Built by [Anubhav Mohandas](https://github.com/anubhavmohandas), grounded in 1,420 architectural patterns extracted from 58 production repositories — reimplemented fresh, not copied.

---

## Contents

- [Install](#install) · [First run](#first-run)
- [How you actually use it](#how-you-actually-use-it) — the two interfaces
- **Usage by task** — [build something](#1-build-something-the-create-flow) · [research](#2-research-the-web) · [memory](#3-memory--remember-and-recall) · [tasks](#4-tasks--plans) · [cost](#5-cost--token-tracking-clio) · [modes](#6-behavioral-modes--occam--laconic) · [watermark cleaning](#6b-palimpsest--no-ai-watermark-leaves-hermes) · [self-improvement](#7-self-improvement--curator-reasoningbank-dream) · [autonomy](#8-autonomy--cron-agenda-delegation) · [web + MCP](#9-live-web-access--mcp-connections) · [code intel](#10-code-intelligence--repo-review) · [opt-in](#11-opt-in-integrations) · [security](#12-security-tools-you-can-run-yourself)
- [Slash commands](#slash-commands) · [Full CLI cheatsheet](#full-cli-cheatsheet) · [Recipes](#recipes--multi-module-workflows)
- [Architecture](#architecture) · [Model routing](#model-routing) · [Status](#status)
- [Known limitations](#known-limitations--read-before-trusting-retrieval-quality) · [Security constraints](#security-constraints--non-negotiable) · [Troubleshooting](#troubleshooting)

---

## Install

```bash
cp HERMES.local.md.example HERMES.local.md
# edit HERMES.local.md: set NVIDIA_MODEL to your NVIDIA API model id
export NVIDIA_API_KEY=<your key from build.nvidia.com>   # Tier 2 only; optional

# Tier C (semantic retrieval) needs two third-party deps; everything else is
# stdlib-only. Install them before relying on Mnemos v2 / ReasoningBank:
pip install -r requirements.txt

python3 test_hermes.py   # full suite: green (2 by-design skips)
```

Install as a Claude Code plugin via `.claude-plugin/plugin.json`, which registers `SKILL.md` as the entry point and `hooks/verify.sh` as a `PreToolUse` hook. Hook commands use `${CLAUDE_PLUGIN_ROOT}`, so the plugin resolves its own paths — no manual path editing after install.

Order matters for the test suite: run it *after* `pip install`. **Before** the deps are installed the suite intentionally reports **one failure** — `TestActiveModulesProvablyRun.test_active_modules_runtime_deps_are_met`. That is not a bug; it is the C6 guard enforcing "a module the manifest calls *active* must provably run." `mnemos-v2`/`reasoningbank` are active and need `hnswlib`, so the guard fails until you install requirements (or move those modules to `modules.offline` in `.claude-plugin/plugin.json`). The Tier-C behavior tests themselves skip cleanly pre-deps.

`HERMES.local.md` is git-ignored on purpose — machine-specific config, never meant to be committed.

### Where things live

| What | Path |
|---|---|
| Code (the plugin) | this repo |
| Config | `~/.claude/hermes/HERMES.local.md` |
| Runtime state (vault, cron db, curator queue, agenda) | `~/.claude/hermes/` |
| Optional status-line badge | add `hooks/hermes_statusline.sh` to your `settings.json` `statusLine` |

Runtime state deliberately lives **next to your Claude config, not inside the plugin** — a plugin update would otherwise wipe your memory. Every module resolves paths through `meta/paths.py`. Ask a module where its state is (`python3 cron/scheduler.py status`) rather than assuming.

## First run

```bash
python3 mnemos/store.py init      # create the vault (runs a write canary)
python3 mnemos/store.py canary    # verify the filesystem can hold a WAL db
```

Then open Claude Code in any project and type `/status`. You should get a live report — environment, hooks, `brain.py` reachability, active modules, log paths — not a static description.

---

## How you actually use it

There are two interfaces, and they overlap on purpose.

**1. Just talk to Claude Code.** HERMES is a plugin, so every prompt in every project already routes through Apollo (the orchestrator). You don't type module names. You say what you want:

```
"build me a deck on Q3 security posture for the board"
"what did we decide about the tier-2 swap?"
"research NVIDIA's embedding models, cite sources"
"go laconic"
"keep working on this after my usage limit resets"
```

Apollo classifies the intent, checks the model tier with `brain.py`, routes to the right sub-skill, verifies the output, and logs it. The security gate fires underneath, at the platform level, on every tool call.

**2. Run the modules directly from the shell.** Every module is a standalone Python CLI with no framework around it. This is the path for scripting, cron, debugging, and for seeing exactly what HERMES sees. All commands below run from the repo root and print JSON.

The rest of this README is organized by what you want to do.

---

## 1. Build something (the create flow)

Ask for anything to be **made** and it goes through one flow: **interview → brief → build → verify → deliver.** No guessing, no half-built deliverable.

```
"make me a presentation on our incident response process"
"write a report comparing the three vendor proposals"
"build a landing page for the tool"
"create a budget spreadsheet for the year"
"build me a CLI that renames files by EXIF date"
```

What happens:

1. Apollo detects the deliverable type and loads `prompts/<type>.md`.
2. It asks every intake question your request didn't already answer — **all in one grouped message**, not a drip-feed. "Your call" is a valid answer to any optional.
3. It echoes a one-paragraph brief back and waits for your yes.
4. It routes to the skill that actually produces the file, verifies the file exists, and logs the deliverable to Mnemos.

Ten deliverable types ship today:

| You ask for | Intake file | Produced by |
|---|---|---|
| presentation / deck / slides | `prompts/presentation.md` | `pptx` skill + design skills |
| report / memo / paper | `prompts/report.md` | `docx` skill |
| spreadsheet / budget / tracker | `prompts/spreadsheet.md` | `xlsx` skill |
| pdf / fill form / merge / split | `prompts/pdf.md` | `pdf` skill |
| website / landing page / dashboard | `prompts/website.md` | `skills/webdev` |
| mobile app / react native | `prompts/mobile.md` | `skills/webdev` |
| tool / script / CLI | `prompts/tool.md` | Apollo direct |
| research / deep dive | `prompts/research.md` | `skills/research` |
| plan / roadmap / design review | `prompts/plan.md` | `skills/tasks` |
| blog / copy / resume | `prompts/content.md` | Apollo direct |

**Extending it:** add `prompts/<newtype>.md` + one routing row in `SKILL.md` §3. That's the whole mechanism.

**Web builds specifically** run design-system-first: tokens → scaffold → sections → motion/anti-slop/critique QA. Scaffolding helpers are callable directly:

```bash
python3 integrations/webdev.py tokens --out ./src/styles
python3 integrations/webdev.py component PricingCard --out ./src/components
python3 integrations/design_extract.py https://example.com --out ./design-ref
```

---

## 2. Research the web

```
"research the current state of post-quantum TLS adoption"
"find out what changed in the NVIDIA API pricing this quarter"
```

Returns findings + sources + a **stated confidence level**, and writes the result to Mnemos so it's recallable later. Deep dives run the `prompts/research.md` intake first.

Backend is Fetcher (Tavily → Firecrawl → direct fetch), with the WebSearch tool as fallback when no key is configured. Direct fetch always works; search needs a key:

```bash
python3 fetcher/fetch.py status
# {"safe_mode": true, "max_bytes": 2097152, "backends": {"tavily": false, ...}}

export TAVILY_API_KEY=...        # or FIRECRAWL_API_KEY
python3 fetcher/fetch.py search "post-quantum TLS adoption 2026" --max-results 5
python3 fetcher/fetch.py fetch https://example.com/paper --max-bytes 500000
```

Without a key, `search` says so — it never fabricates results. Every hop (including redirects) is SSRF-checked, SAFE_MODE is GET-only/byte-capped/TLS-verified, and fetched content is marked untrusted and secret-scrubbed before it reaches you.

---

## 3. Memory — remember and recall

```
"remember that the staging deploy script is at ops/deploy_staging.sh"
"what did we decide about the vault path?"
"search past sessions for the tier-2 outage"
```

Retrieval is 3-tier hybrid: **BM25 (FTS5) → regex → semantic HNSW**, with a confidence label on every answer.

```bash
# write (both stores, so all 3 tiers can find it later)
python3 mnemos/store.py write "sess-2026-08" user "staging deploy lives at ops/deploy_staging.sh"
python3 mnemos/hnsw_index.py ~/.claude/hermes/mnemos/vault/hnsw insert "staging deploy lives at ops/deploy_staging.sh"

# recall
python3 mnemos/hybrid_search.py "deploy script"
```

```json
{
  "query": "deploy script",
  "confidence": "NONE",
  "resolved_tier": null,
  "reason": "no hit cleared the confidence threshold in any tier",
  "tier_a_bm25": [], "tier_b_regex": [], "tier_c_semantic": [ ... ]
}
```

Read the `confidence` field and believe it. `HIGH`/`MEDIUM` come from exact lexical or regex matches; `LOW` is a semantic-only hit and is **capped at LOW on purpose** — see [Known limitations](#known-limitations--read-before-trusting-retrieval-quality).

Each message carries one of four memory types (`user` / `feedback` / `project` / `reference`). Omit the argument and `store.py` classifies deterministically with keyword rules — no LLM, inspectable in `store.classify_memory_type`. Pass it explicitly when you know better:

```bash
python3 mnemos/store.py write "sess-2026-08" user "I prefer terse answers" user
python3 mnemos/store.py search "terse"
python3 mnemos/store.py get "sess-2026-08"
python3 mnemos/memory_index.py check       # MEMORY.md index cap: 200 lines / 25KB
```

Direct semantic query, bypassing the hybrid layer:

```bash
python3 mnemos/hnsw_index.py ~/.claude/hermes/mnemos/vault/hnsw query "deploy" 5
```

**Real embeddings (opt-in):** `export HERMES_EMBEDDER=nvidia` swaps the default hashing vectorizer for NVIDIA `nv-embedqa-e5-v5`. The index records its backend in a meta sidecar and **refuses to load a mismatched index** rather than silently corrupting the vector space — so rebuild after switching.

---

## 4. Tasks & plans

```
"break this migration down into tasks"
"plan the rollout and track it"
```

Decomposes with the TaskCreate/TaskUpdate pattern and logs completions to Mnemos. For board-style tracking that survives the session, use the kanban integration:

```bash
python3 integrations/kanban.py add "migrate vault to APFS" --lane todo --profile hermes
python3 integrations/kanban.py board --profile hermes
python3 integrations/kanban.py move 3 doing
python3 integrations/kanban.py rm 3
```

---

## 5. Cost & token tracking (Clio)

```
"what's this costing me?"
"how many tokens did I burn this week?"
```

Read from disk — no proxy, no request interception.

```bash
python3 clio/tracker.py --group-by tier
python3 clio/tracker.py --since 2026-08-01 --source claude-code-cli
python3 clio/tracker.py --group-by task_type --source internal
```

```json
{
  "internal": { "total_requests": 0, "total_tokens": 0, "est_total_cost_usd": 0.0 },
  "claude_code_cli": {
    "sessions_found": 68, "total_turns": 5728,
    "total_tokens": 757003851, "est_cost_usd": 522.08,
    "by_session": { ... }
  }
}
```

`--source internal` is HERMES's own logged calls; `claude-code-cli` reads your real Claude Code session transcripts; `all` (default) reports both separately so you never conflate them.

---

## 6. Behavioral modes — Occam & Laconic

Two independent, reversible modes. Both persist as a flag file under `$CLAUDE_CONFIG_DIR` and are re-asserted by a hook **every turn**, so they survive long sessions instead of decaying like a one-time instruction. `hooks/hermes_statusline.sh` renders an `[OCCAM]` / `[LACONIC]` badge for whichever is active.

**Occam governs how much is built.** On by default at level `full`.

```
/occam lite      → builds what's asked, names the lazier alternative
/occam full      → enforces the ladder (default)
/occam ultra     → YAGNI extremist, challenges the requirement itself
"stop occam"     → off
```

The ladder, stopping at the first rung that holds: *does this need to exist (YAGNI) → reuse what's already in the codebase → stdlib → native platform feature → installed dep → one line → only then new code.* It never cuts input validation, error handling, security, or accessibility. Deliberate shortcuts get an `occam:` comment naming the ceiling and the upgrade path.

Five satellite skills, all read-only, all one-shot:

| Skill | What it does |
|---|---|
| `/occam-review` | Reviews the current diff for over-engineering. One line per finding: location, what to cut, what replaces it. |
| `/occam-audit` | Same hunt, whole repo: ranked list of what to delete, simplify, or replace with stdlib. |
| `/occam-debt` | Harvests every `occam:` comment into a debt ledger, so shortcuts get tracked instead of rotting. |
| `/occam-gain` | The source project's published benchmark scoreboard. Explicitly **not** a measurement of this repo. |
| `/occam-help` | Quick-reference card for every mode, level, and command. |

**Laconic governs how much is said.** Opt-in.

```
"go laconic" / "be brief" / "less tokens"   → on
"stop laconic" / "normal mode"              → off
```

While active: no preamble, no postamble, code/diff first. It **auto-suspends for one turn** when the content is safety-critical (destructive command, security warning, user confusion), then resumes.

Separately, a deterministic bulk-text compressor for shrinking a payload before a Tier 2 job — stopword drop, negations preserved, no model call:

```bash
python3 integrations/laconic_compress.py --stats "$(cat long_input.txt)"
python3 integrations/laconic_compress.py "the quick brown fox is on the mat"
```

---

## 6b. Palimpsest — no AI watermark leaves HERMES

On by default at level `safe` (unlike Laconic/Occam, which are off-by-phrase or opt-in) — the point is you shouldn't have to ask. Right after any `Write`/`Edit` call, `hooks/palimpsest_clean.sh` (`PostToolUse`) runs the file through `integrations/palimpsest/` and rewrites it in place if it finds anything watermark-shaped: invisible Unicode/format-control characters and space homoglyphs in any text file; ancillary `tEXt`/`zTXt`/`iTXt`/`eXIf`/`tIME` chunks in PNG and `APP1`/`APP11`/`COM` segments in JPEG (pixel data untouched — round-trip verified against Pillow); `docProps/core.xml`/`app.xml`/`custom.xml` identity fields in DOCX/XLSX/PPTX plus a Layer-A pass over every text-bearing XML part; best-effort same-length blanking of a PDF's `/Info` dict and XMP packet; `<meta name="generator">` tags and AI-signature comments in HTML/Markdown/SVG.

```
/palimpsest safe          → default. Layer A + metadata stripping, never rewrites a visible character
/palimpsest aggressive    → safe, plus folds Cyrillic/fullwidth-Latin lookalikes in plain text (does rewrite visible characters -- real risk to real multilingual content, hence opt-in)
/palimpsest off           → hook still fires, does no I/O
"stop palimpsest"          → off, this session
```

**What this does not cover, stated plainly:** it does not touch the assistant's own chat text before it reaches you — no hook in this platform intercepts a response pre-render, only files a tool call actually writes to disk. It does not detect or remove statistical (token-sampling) watermarks like SynthID-Text or Kirchenbauer green-list schemes — those live in which words a model chose, not in stray codepoints, and no classifier for that exists here. WebP/AVIF/HEIC/BMP/GIF/TIFF images, audio/video, EPUB and ODT aren't ported yet; `format_route.classify()` reports them as unsupported rather than silently skipping. Sensitive paths (`.env`, `.ssh`, `.aws`, `credentials*`, `*.pem`, `*.key`, ...) are never touched.

Renamed on integration from a third-party watermark-removal project, same convention as Apollo/Mnemos/Clio/Laconic/Occam — patterns and format tables extracted, code written fresh (`SKILL.md` §9).

---

## 7. Self-improvement — Curator, ReasoningBank, Dream

**Nothing here auto-applies. Ever.** Proposals sit in a queue until a human explicitly approves them.

```
"what went wrong there?"
"show me recurring failures"
"review the pending proposals"
```

```bash
# 1. consolidate raw failure log -> deduplicated, recurrence-counted taxonomy
python3 curator/consolidate.py

# 2. turn anything that recurred (count >= 2) into a proposal
python3 curator/propose.py

# 3. read the queue yourself
ls ~/.claude/hermes/curator/pending/

# 4. YOUR decision, explicitly
python3 curator/approve.py approve <id>
python3 curator/approve.py reject <id>
```

Apollo never calls `approve.py` on its own initiative, regardless of how confident it is.

**ReasoningBank** stores `{task, approach, outcome, reward, success, critique, tokens, latency}` per completed task and returns the top-scoring past approaches for a similar new one:

```bash
python3 reasoningbank/bank.py retrieve "research a CVE" 5 0.8
python3 reasoningbank/bank.py log "research CVE-2025-1234" "WebSearch then verify with NVD" \
        "success" 0.9 true "did not check vendor advisory first" 4200 8100
```

Score rewards honestly — a task that completed but needed rework is not a 0.9. Inflated rewards poison future retrieval.

**Dream** is the consolidation pass, lock-protected against concurrent runs:

```bash
python3 mnemos/dream.py           # respects the timing gate
python3 mnemos/dream.py --force   # bypasses it
```

The gate runs Dream only if `interval_hours` have elapsed **and** ≥`min_new_entries` new reflexion entries accrued — so a nightly cron run doesn't re-consolidate identical data. Config: `~/.claude/hermes/mnemos/dream/dream_config.json`.

---

## 8. Autonomy — Cron, Agenda, Delegation

### Keep working after your usage limit resets

The one people want most:

```
"keep working on this after my usage limit resets"
"run until it's done, don't stop when tokens run out"
```

```bash
python3 delegation/agenda.py add "finish the migration test suite" \
        --context "repo at ~/code/proj, tests in tests/" \
        --workspace ~/code/proj --child-timeout 1800
python3 delegation/agenda.py install-cron --interval 900   # once, ever
python3 delegation/agenda.py list
python3 delegation/agenda.py show <id>
python3 delegation/agenda.py done <id>       # or: abandon / retry
```

Rate-limited attempts retry for free and **do not count as failures**; genuine failures stall the item after N per the RecoveryLedger. Children write only inside their workspace and get Bash only if you passed `--allow-bash` at add time.

**Honest limit:** this is resume-from-progress-notes within one tick interval, not a live-session restore. It picks the work back up; it does not restore your conversation.

### Scheduled jobs

```bash
python3 cron/scheduler.py add nightly-dream "python3 mnemos/dream.py" --daily 03:30
python3 cron/scheduler.py add hourly-check "python3 meta/upstream_tracker.py check" --interval 3600
python3 cron/scheduler.py list
python3 cron/scheduler.py disable nightly-dream    # or: enable / remove
python3 cron/scheduler.py tick                     # run due jobs once, now
python3 cron/scheduler.py status
```

```json
{
  "db": "/Users/you/.claude/hermes/cron/cron.db",
  "lock_held": false, "jobs_total": 2, "jobs_enabled": 2,
  "default_timeout_seconds": 180,
  "jobs": [ { "name": "agenda-tick", "schedule": "interval", "interval_seconds": 900, ... } ]
}
```

Durable SQLite, `.tick.lock` with mtime-based staleness detection, per-job hard interrupt (default 180s), and every completed run written back to Mnemos so results are retrievable next session. Commands are classified through `approval.py` at both add-time and run-time — **approval-tier commands are refused outright**, because unattended means there is no one to approve.

Host it under launchd with `hooks/com.hermes.cron.plist.template` (full walkthrough in [docs/SCHEDULING.md](docs/SCHEDULING.md)). Cowork can't host it (Invariant #7).

> **Gotcha:** a running scheduler holds the code paths it imported at start. After changing module paths, restart it.

### Parallel sub-agents

```bash
python3 delegation/dispatch.py run "audit auth flow" "audit the db layer" "audit the API surface"
python3 delegation/dispatch.py run "overnight sweep" --async-profile --timeout 3600
python3 delegation/dispatch.py run "dry test" --dry-run
python3 delegation/dispatch.py status
```

Capped at 3 concurrent children (extras queue, they aren't rejected). `TaskStop`/`AskUserQuestion`/`EnterPlanMode`/`ExitPlanMode` are stripped from every child unconditionally — a caller who explicitly asks for one still doesn't get it. `--async-profile` children (what Cron spawns) get an observation-only tool set: `Read`/`Grep`/`Glob`/`WebSearch`, no `Write`, no `Bash`. An unattended child that can mutate answers to nobody.

Needs the `claude` CLI on PATH to actually spawn.

---

## 9. Live web access & MCP connections

Fetcher is covered in [§2](#2-research-the-web). For connecting to external tools:

```bash
# native MCP stdio client
python3 connect/mcp_client.py status -- npx -y @modelcontextprotocol/server-filesystem /tmp
python3 connect/mcp_client.py tools  -- npx -y @modelcontextprotocol/server-filesystem /tmp
python3 connect/mcp_client.py call read_file '{"path":"/tmp/a.txt"}' -- npx -y @modelcontextprotocol/server-filesystem /tmp

# OAuth 2.1 PKCE (S256 only)
python3 connect/oauth_pkce.py new
python3 connect/oauth_pkce.py challenge <verifier>

# connector ledger
python3 integrations/composio.py list
python3 integrations/composio.py enable github
python3 integrations/composio.py status
```

Capability negotiation is enforced and `X-Agent-Id` provenance is attached. Server commands run through the same approval gate as everything else.

---

## 10. Code intelligence & repo review

**What calls this? What breaks if I change it?**

```bash
python3 integrations/synapse.py build . --out graph.json --top 10
python3 integrations/synapse.py status
```

Stdlib `ast` only — same-file plus explicit `from X import Y` call resolution, no external deps. Returns nodes, edges, and the top hub functions.

**Full-codebase review, six lenses fanned out in parallel:**

```bash
python3 integrations/repopack.py pack . --out packed.md --max-file-kb 64 --max-total-mb 4
python3 integrations/repopack.py reviewers                  # list the lenses
python3 integrations/repopack.py review packed.md --lenses security,performance
python3 integrations/repopack.py review packed.md --dry-run
```

---

## 11. Opt-in integrations

Each installs on demand, each ships a **verified fallback**, none sit on the critical path. They stay dormant until called.

| Module | Command | Fallback when the good path is missing |
|---|---|---|
| **db** | `python3 integrations/db/store.py status \| migrate \| query "<sql>"` | Postgres if `DATABASE_URL` is set, else SQLite |
| **media** | `python3 integrations/media.py status`<br>`… plan download\|frames\|transcribe <target> [--fps N]` | Per-tool availability check (yt-dlp/ffmpeg/whisper) → honest "not installed", never a fake result |
| **kanban** | `python3 integrations/kanban.py add\|move\|rm\|board` | none needed — SQLite-backed, always works |
| **turbo memory** | `python3 integrations/turbo_memory.py [selftest]` | C++ if compiled → numpy → pure Python, identical results |
| **notebooklm** | `python3 integrations/notebooklm.py synth <source>… \| status` | Local deterministic synthesis always available; online path needs a Google key, off by default |
| **composio** | `python3 integrations/composio.py list\|enable\|disable\|status` | ledger-only, no network required to inspect |
| **synapse** | `python3 integrations/synapse.py build [path] \| status` | none needed — stdlib `ast` |
| **webdev** | `python3 integrations/webdev.py tokens\|component\|status` | none needed |

```bash
python3 integrations/turbo_memory.py
# {"backend": "numpy", "turbo_available": false, "numpy_available": true,
#  "note": "cpp is opt-in ...; numpy/python fallbacks give identical results"}
```

---

## 12. Security tools you can run yourself

The 7-layer gate fires automatically as a `PreToolUse` hook — you don't invoke it, and a prompt can't talk around it. These are the things you *can* drive:

```bash
# repeatable 11-check audit of all 7 layers
python3 meta/security/audit.py
python3 meta/security/audit.py --record        # record a green run

# single-use, command-bound, 300s approval token for one dangerous command
python3 meta/security/approval_token.py grant "rm -rf ./build"
python3 meta/security/approval_token.py check "rm -rf ./build"
python3 meta/security/approval_token.py list

# tier-3 selection guard (selects; never dispatches)
python3 tier3.py route --task "summarize this public changelog"
python3 tier3.py chain

# tier check for any task, before you run it
python3 brain.py check --task "analyze CVE-2025-1234 recon notes" --model claude-opus-5
```

```json
{"sensitive": true, "task_type": "default", "tier": 1,
 "tier_name": "Tier 1 — Claude API", "model": "claude-opus-5",
 "allowed": true, "reason": "ALLOWED"}
```

Sensitivity classification is deterministic keyword matching, not a model's judgment — inspectable, testable, and it can't be argued with.

Also available: `/security-review` for a structured three-phase review of the current branch's diff (14 hard exclusions adopted from Anthropic's production review, confidence ≥8/10 filter, read-only), and `python3 meta/upstream_tracker.py watch|unwatch|ack <owner/repo> | check | list` for report-only drift tracking against source repos.

---

## Slash commands

| Command | What it gives you |
|---|---|
| `/help` | Every active module, what it does, how to trigger it, what's offline and in which phase. Regenerated live, never a stale copy. |
| `/status` | Live state: environment, hooks, `brain.py` reachability, active/inactive modules, log paths, last logged request. |
| `/goal` | Reads the current project's `GOAL.md` if there is one; falls back to HERMES's own roadmap only when cwd *is* this repo. Never silently substitutes. |
| `/security-review` | Three-phase security review of the current branch's diff. Read-only. |
| `/occam lite\|full\|ultra` | Set the minimal-code level. |
| `/occam-review` `/occam-audit` `/occam-debt` `/occam-gain` `/occam-help` | The Occam family — see [§6](#6-behavioral-modes--occam--laconic). |
| `/palimpsest safe\|aggressive\|off` | Watermark-cleaning mode — see [§6b](#6b-palimpsest--no-ai-watermark-leaves-hermes). |

---

## Full CLI cheatsheet

Everything, one line each. All run from the repo root, all print JSON.

```bash
# --- routing & tiers ---
python3 brain.py check --task "<desc>" --model <model>
python3 brain.py log --task-type <type> --tier <N> --outcome success|failure \
        --success true|false --tokens <n> --latency <ms> [--model M] [--decision D]
python3 brain.py log-failure --task "<desc>" \
        --category validation|dependency|logic|assumption|type|unknown \
        --rule "<what should have been checked>" --failure-mode "<what went wrong>"
python3 tier3.py route --task "<desc>" | chain
python3 nvidia_client.py status | chat "<prompt>" [--model NAME] [--system TEXT]

# --- memory ---
python3 mnemos/store.py init | canary | write <sess> <role> <content> [type] | search <q> | get <sess>
python3 mnemos/hybrid_search.py "<query>" [k]
python3 mnemos/hnsw_index.py <index_dir> insert "<text>" | query "<text>" [k]
python3 mnemos/memory_index.py check [path]
python3 mnemos/dream.py [--force]

# --- self-improvement ---
python3 curator/consolidate.py
python3 curator/propose.py
python3 curator/approve.py approve|reject <id>
python3 reasoningbank/bank.py retrieve "<task>" [k] [min_reward]
python3 reasoningbank/bank.py log <task> <approach> <outcome> <reward> <success> [critique] [tokens] [latency]

# --- cost ---
python3 clio/tracker.py [--group-by tier|task_type] [--since DATE] [--source internal|claude-code-cli|all]

# --- autonomy ---
python3 cron/scheduler.py add <name> "<cmd>" --interval N|--daily HH:MM|--once [--timeout S]
python3 cron/scheduler.py list | tick | status | loop [--poll N] | enable|disable|remove <name>
python3 delegation/dispatch.py run "<prompt>"... [--async-profile] [--timeout S] [--model M] [--dry-run]
python3 delegation/dispatch.py status
python3 delegation/agenda.py add "<goal>" [--context C] [--workspace W] [--allow-bash] \
        [--child-timeout S] [--max-failures N] [--model M]
python3 delegation/agenda.py list | status | tick [--dry-run] | show|done|abandon|retry <id>
python3 delegation/agenda.py install-cron [--interval 900]

# --- web & connections ---
python3 fetcher/fetch.py fetch <url> [--max-bytes N] | search "<q>" [--max-results N] | status
python3 connect/mcp_client.py tools | call <tool> '<json>' | status -- <server cmd>
python3 connect/oauth_pkce.py new | challenge <verifier>

# --- security ---
python3 meta/security/audit.py [--record]
python3 meta/security/approval_token.py grant|check "<command>" | list
python3 meta/upstream_tracker.py watch|unwatch|ack <owner/repo> | check | list

# --- integrations ---
python3 integrations/db/store.py status | migrate | query "<sql>"
python3 integrations/kanban.py add "<title>" [--profile P] [--lane L] | move <id> <lane> | rm <id> | board [--profile P]
python3 integrations/media.py status | plan download|frames|transcribe <target> [--fps N]
python3 integrations/notebooklm.py synth <source>... | status
python3 integrations/turbo_memory.py [selftest]
python3 integrations/composio.py list | enable <c> | disable <c> | status
python3 integrations/synapse.py build [path] [--out FILE] [--top N] | status
python3 integrations/repopack.py pack <root> [--out F] | reviewers | review <pack> [--lenses L] [--dry-run]
python3 integrations/webdev.py tokens --out <dir> | component <Name> --out <dir> | status
python3 integrations/design_extract.py <url> [--out <dir>] | status
python3 integrations/laconic_compress.py [--stats] "<text>"
```

---

## Recipes — multi-module workflows

**Nightly self-improvement, fully automated but still human-gated.**

```bash
python3 cron/scheduler.py add nightly-dream "python3 mnemos/dream.py" --daily 03:30
python3 cron/scheduler.py add nightly-propose "python3 curator/propose.py" --daily 03:45
# next morning:
ls ~/.claude/hermes/curator/pending/ && python3 curator/approve.py approve <id>
```

Consolidation and proposal generation run unattended; **applying** anything still needs you.

**Ship a feature overnight, resume through the usage-limit reset.**

```bash
python3 delegation/agenda.py add "add pagination to the reports endpoint" \
        --context "FastAPI app, tests in tests/test_reports.py" \
        --workspace ~/code/api --allow-bash --child-timeout 1800
python3 delegation/agenda.py install-cron --interval 900
python3 delegation/agenda.py status    # check in whenever
```

**Research → brief → deck, one continuous flow.** Just talk:

```
"research how our three competitors handle SSO, then build me a deck comparing them"
```

Apollo runs `skills/research` (Fetcher-backed, sources cited, written to Mnemos), then `skills/create` → `prompts/presentation.md` intake → `pptx`. The research is recallable next week without re-running it.

**Audit a repo you just inherited.**

```bash
python3 integrations/synapse.py build . --top 15        # where are the hubs?
python3 integrations/repopack.py pack . --out packed.md
python3 integrations/repopack.py review packed.md       # 6 lenses in parallel
# then, in Claude Code:
/occam-audit                                            # what can be deleted
```

**Cost postmortem after a heavy week.**

```bash
python3 clio/tracker.py --since 2026-08-01 --group-by task_type --source all
```

Then compress bulk input before the next Tier 2 batch job:

```bash
python3 integrations/laconic_compress.py --stats "$(cat corpus.txt)"
```

---

## Architecture

```
User → Apollo (orchestrator) → brain.py (tier check) → [security hook, always fires] → sub-skill → self-improvement log → output
```

Nothing bypasses Apollo. Nothing bypasses the security gate — it's a `PreToolUse` hook registered at the platform level, not a prompt instruction, so it can't be talked around.

| Module | What it does |
|---|---|
| **Apollo** (`SKILL.md`) | Master router. Classifies intent, confirms model tier before routing, runs a verification pass on every output. |
| **Create flow** (`skills/create` → `webdev` / `documents` / `research` / `tasks`) | Deliverable orchestrator: intake interview → brief → route to the matching sub-skill → verify the output exists → log to Mnemos. |
| **brain.py** | Deterministic (not LLM-based) sensitivity classification and 3-tier model routing. |
| **meta/security/** | 7 independent defense-in-depth layers: write denylist, path traversal, SSRF prevention, skill static analysis, dangerous-command gate, pre-exec binary scanner, secret redaction. |
| **Mnemos** | Memory. v1 is SQLite WAL+FTS5 lexical search. v2 adds 3-tier hybrid retrieval (BM25 → regex → HNSW semantic). |
| **Clio** | Token/cost tracking, read from disk — no proxy or request interception. |
| **Curator** | Captures failures into a deduplicated, recurrence-counted taxonomy and proposes fixes. Proposals sit in `~/.claude/hermes/curator/pending/` until a human approves or rejects them. Nothing auto-applies, ever. |
| **ReasoningBank** | Stores `{task, approach, outcome, reward, critique}` per completed task; retrieves top-scoring past approaches (reward > 0.8) for similar new tasks. |
| **Dream** | On-demand consolidation pass, lock-protected, timing-gated, schedulable via Cron. |
| **Cron** (`cron/scheduler.py`) | Durable SQLite scheduler — `.tick.lock`, per-job 3-minute hard interrupt, every run written back to Mnemos. Approval-tier commands refused at add- and run-time. Hosted under launchd. |
| **Delegation** (`delegation/dispatch.py`) | Sub-agent fan-out capped at 3 concurrent children. Four tools stripped from every child unconditionally; overnight children get an observation-only tool set. |
| **Agenda** (`delegation/agenda.py`) | Durable goal queue that retries through usage-limit resets and resumes from progress notes. |
| **Fetcher** (`fetcher/fetch.py`) | Live web access, SSRF-checked every redirect hop, SAFE_MODE (GET-only, byte-capped, TLS-verified), key-gated search that never fabricates results. |
| **Connect** (`connect/`) | Native MCP stdio client with enforced capability negotiation + `X-Agent-Id` provenance, and an OAuth 2.1 PKCE (S256-only) helper. |
| **Tier-3 guard** (`tier3.py`) | Availability-only fallback selection with an independent second sensitivity check, Chinese-API exclusion, and EU/US jurisdiction filter (fails closed on unknown jurisdiction). Selects; never dispatches. |
| **Approval tokens** (`meta/security/approval_token.py`) | Single-use, command-bound, 300s token lets a human approve one specific dangerous command through the otherwise fail-closed hook. |
| **Laconic / Occam** (`meta/laconic.py`, `meta/occam.py`) | Behavioral modes — how much is said, how much is built. Hook-enforced every turn. |
| **Palimpsest** (`meta/palimpsest.py`, `integrations/palimpsest/`) | Strips AI-provenance watermarks/metadata from files right after Write/Edit writes them. Mechanical (`PostToolUse` hook), not a model-behavior mode — doesn't touch chat text before render. |
| **Opt-in integrations** (`integrations/`) | db, webdev, media, kanban, turbo memory, NotebookLM, Composio, synapse, repopack — each independently installable with a verified fallback, none on the critical path. |

## Model routing

| Tier | Target | When |
|---|---|---|
| 1 | Claude API | Default. Mandatory for sensitive data — CVEs, recon, pentest notes, HERMES/SAGE/NYX internals. |
| 2 | NVIDIA API | Bulk/cost-sensitive tasks, non-sensitive only (remote cloud API — data leaves the machine). |
| 3 | NYX fallback (EU/US only) | Availability fallback only. Never routes sensitive data, regardless of cost or availability. |

**Permanently excluded, no opt-in, no exceptions:** Kimi (Moonshot AI), GLM (Zhipu AI), MiMo (Xiaomi), MiniMax, DeepSeek. Every tier is a remote API now, so the exclusion applies on all tiers — including DeepSeek-family models served through the NVIDIA API.

HERMES never silently substitutes a tier in either direction. If Tier 2 is down, it says so and asks.

## Status

**Stages 0–5 are built and unit-tested — 198 tests green (196 pass + 2 environment-conditional skips by design if `hnswlib`/`numpy` aren't installed).** Stage 0 is proven end-to-end on real disk: one genuine request has flowed through the full loop — route → cross-process memory → reward retrieval → human-gated Curator approval (evidence kept locally in `logs/proof_gate0.md` — audit records stay out of the repo). The `PreToolUse` security gate (`hooks/verify.sh`) is installed and live-verified as of 2026-07-05 — confirmed via `/hooks` in a real Claude Code session (matcher `(all)`, plugin `hermes@hermes`) and via real blocked tool calls (`sudo`, SSRF to the cloud metadata IP via `curl`/`nc`, decimal-encoded and variable-obfuscated IP forms) each producing a matching, timestamp-correlated entry in `logs/reflexion_seed.json` — not just a unit test. Stages 1–5 beyond the gate itself are proven at the component level; the Stage 3 external-integration paths were exercised live on real infrastructure 2026-07-05 — the then-current Tier 2 backend, real Tavily key, real `@modelcontextprotocol/server-filesystem` handshake (evidence kept locally in `logs/proof_gate4.md`). Tier 2 has since been swapped to the NVIDIA API (2026-07-16) and its live chat path is still UNVERIFIED: attempted 2026-08-05 against the configured key and the API returned `401 Unauthorized` on `/v1/chat/completions`, so no Tier 2 completion has ever round-tripped. The same attempt found that `/v1/models` — the old readiness probe — answers HTTP 200 with no credentials at all, meaning `status()` had been reporting `reachable: true` for a key that cannot infer; the probe now issues a real 1-token completion instead, so `tier2_ready` reflects the path Apollo actually gates. Autonomy paths (Cron/Delegation under real unattended load) remain proven at the component level only. NYX (Stage 6) is deliberately out of scope: NYX doesn't exist yet.

| Stage | Scope | Status |
|---|---|---|
| 0 | Prove & package: `requirements.txt`, import-guarded Tier C, `test_hermes.py`, clean tree, one real end-to-end request on real disk | ✅ Proven (real disk; loop closed once with human gate) |
| 1 (3A) | Apollo orchestration, `brain.py` tier router, 7-layer security gate, Mnemos v1 (SQLite WAL+FTS5), Clio token tracking | ✅ Built, unit-tested · orchestrator routing behaviorally proven live, 10/10 real `claude -p` cases, real CLI host, `logs/proof_gate2.md` (Gate 2 closed 2026-07-11 — proxy limitation noted there: model was pointed at its own routing table, not tested on blind ambiguous input) |
| 2 (3B) | Mnemos v2 (HNSW + 3-tier hybrid search), Curator v1 (human-gated proposals), ReasoningBank (reward-scored task memory), Dream consolidation | ✅ Built, unit-tested |
| 3 (3C) | Cron (durable SQLite scheduler, `.tick.lock`, 3-min interrupt, Mnemos write-back), Delegation (≤3 children, forbidden-tool restriction), Fetcher (Tavily/Firecrawl, SAFE_MODE, SSRF-every-hop), Connect (native MCP client + capability negotiation + PKCE OAuth) | ✅ Built, unit-tested · Tier-2/Tavily/MCP live paths proven on real infra 2026-07-05 (Tier 2 was local Ollama then; now the NVIDIA API — live path unverified since the swap); 6 failure modes tested and fail closed, two CLI robustness bugs found and fixed same session; Apollo's "never silently substitute tiers" rule confirmed live under 3 real Tier-2-outage cases including one adversarial-pressure case (`logs/proof_gate4.md`, `logs/proof_failuremode.md`, `logs/proof_apollo_tier_fallback.md`, all local) — real-daemon-kill, genuinely-revoked-key, and multi-turn/jailbreak robustness of the tier rule remain untested |
| 4 (3D) | Repeatable 7-layer audit, Clio benchmark baseline, Tier-3 routing guard (2nd sensitivity check + EU/US jurisdiction), D1 interactive approval tokens, streaming think-block scrubber, upstream drift tracker | ✅ Built, unit-tested |
| 5 | Laconic token-reduction, Occam lazy-minimal-code mode (hook-enforced ladder + 5 satellite skills), Palimpsest AI-watermark/provenance-metadata stripping (`PostToolUse` hook on Write/Edit), opt-in breadth each with a fallback: db, webdev, media, kanban, turbo memory, NotebookLM, Composio | ✅ Built, unit-tested (opt-in, each with fallback) |
| 6 | NYX integration | ⬜ Out of scope — NYX not built yet |

More walkthroughs with captured real output: [docs/WORKFLOWS.md](docs/WORKFLOWS.md). Scheduling setup: [docs/SCHEDULING.md](docs/SCHEDULING.md). Design rationale: [docs/DECISIONS.md](docs/DECISIONS.md).

## Known limitations — read before trusting retrieval quality

**Mnemos v2's "semantic" search is not backed by a real embedding model.** `mnemos/embedder.py` is a deterministic hashing-trick bag-of-words/char-n-gram vectorizer — it catches lexical and substring overlap, not paraphrase or conceptual similarity. It was benchmarked at 0.933 recall@5 on a hand-labeled corpus, but that corpus was constructed with vocabulary overlap between queries and relevant documents; it does not demonstrate semantic generalization. "logical qubit fault tolerance" will **not** reliably match "quantum error correction". Retrieval confidence is capped at `LOW` for semantic-only hits in `hybrid_search.py` for exactly this reason. A real embedding model is available as the opt-in `nvidia` backend (`HERMES_EMBEDDER=nvidia`, NVIDIA API `nv-embedqa-e5-v5`) — `hnsw_index.py` and `hybrid_search.py` don't need to change.

**SQLite reliability depends on the filesystem.** Mnemos' WAL-mode store has failed with `disk I/O error` on at least one sandboxed/FUSE-mounted filesystem during development, while working correctly on a real local disk with the identical, unmodified code (confirmed 2026-07-04: a two-process write/retrieve passes on real local APFS disk — the failures were the FUSE-mounted view only). `store.py` falls back to `DELETE` journal mode if `WAL` fails to initialize, and `hybrid_search.py` degrades to semantic-only retrieval if the SQLite-backed tiers are unavailable — but if your vault path ends up on a network drive or synced folder (Dropbox, OneDrive, iCloud Drive), run `python3 mnemos/store.py canary` before depending on it.

## Security constraints — non-negotiable

- Sensitive data (CVEs, recon output, pentest notes, HERMES/SAGE/NYX internals) routes to **Tier 1 only** — never Tier 2, never Tier 3, regardless of availability or cost. Tier 2 stopped being a valid destination for sensitive work when it became the remote NVIDIA API: the old "Tier 1 or Tier 2" rule was sound only while Tier 2 was local Ollama and the data never left the machine. `meta/policy.get_tier()` has enforced sensitive→Tier 1 since that swap. The Tier-3 guard (`tier3.py`) re-runs the sensitivity check independently before any fallback route, so two call sites must both fail for sensitive data to leak.
- HERMES never auto-applies its own suggestions. Curator proposals require explicit human approval via `curator/approve.py`; dangerous shell commands require a single-use human-granted approval token; scheduled Cron jobs cannot carry approval-tier commands at all.
- No executable code is copied from any analyzed repository — patterns only, reimplemented fresh. This holds across all 58 source repos.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `disk I/O error` from Mnemos | Vault is on a FUSE/network/synced mount. `python3 mnemos/store.py canary` confirms it; move the vault to real local disk. |
| One test fails before `pip install` | Expected. The C6 guard enforces "active module must provably run." Install `requirements.txt`. |
| `tier2_ready: false` | Check `NVIDIA_API_KEY` and `NVIDIA_MODEL`. The probe issues a real 1-token completion, so a 401 shows up honestly instead of a false green. |
| Search returns nothing, confidence `NONE` | Nothing cleared the threshold. Check you wrote to **both** stores — `store.py write` *and* `hnsw_index.py insert` into `~/.claude/hermes/mnemos/vault/hnsw`. |
| Cron job silently uses old code | The running scheduler holds the paths it imported at start. Restart it after any path change. |
| Delegation does nothing | Needs the `claude` CLI on PATH to spawn children. |
| Fetcher `search` refuses | No `TAVILY_API_KEY`/`FIRECRAWL_API_KEY`. It declines rather than fabricating results; direct `fetch` still works. |
| A module reports "not installed" | That's the honest fallback, working as designed. Install the underlying tool or use the stated fallback path. |
| Mode didn't stick across turns | Laconic, Occam and Palimpsest all persist to a flag file under `$CLAUDE_CONFIG_DIR`; Laconic/Occam reassert every turn, Palimpsest only reasserts at `SessionStart` since its enforcement is a `PostToolUse` hook, not a per-turn model reminder — check the hooks are registered with `/hooks`. |

## License

MIT — see [LICENSE](LICENSE).
