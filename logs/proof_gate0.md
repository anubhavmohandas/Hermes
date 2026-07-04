# Gate 0 proof file — HERMES Stabilize-to-Proven

Evidence per charter: literal log lines + command transcripts. Appended per sub-gate as each goes green.

## 0a — reasoning_seed.jsonl entry from a genuine request, latency_ms > 0 — GREEN 2026-07-04

A real Tier 1 request flowed through the designed pipeline (SKILL.md §2: check → execute → log).
The task was genuine work needed for Gate 1: extracting README.md's status claims for the
doc-truth reconciliation. Latency was measured by delegation/dispatch.py around a live
`claude -p` child, not supplied by hand.

### 1. Route check (the same seam hooks/verify.sh calls)

```
$ python3 brain.py check --task "Extract every quantitative or status claim (test counts, proven/working language) from README.md for the Gate 1 doc-truth reconciliation" --model claude-sonnet-5 --via api
{"sensitive": false, "task_type": "default", "tier": 1, "tier_name": "Tier 1 — Claude API", "model": "claude-sonnet-5", "allowed": true, "reason": "ALLOWED"}
```

### 2. Real execution — one `claude -p` delegation child (dispatch.py measured elapsed_ms)

`claude` was not on PATH; the run used the VSCode-extension-bundled binary
(`~/.vscode/extensions/anthropic.claude-code-2.1.199-darwin-arm64/resources/native-binary/claude`,
version 2.1.199) appended to PATH. dispatch.py's own `shutil.which` seam found it — no code changed.

```
$ python3 delegation/dispatch.py run "Read README.md in the current directory. Quote verbatim every line or phrase that makes a quantitative or status claim: ..." --timeout 240
{
  "dispatched": true,
  "children": 1,
  "results": [
    {
      "status": "completed",
      "elapsed_ms": 29793,
      "output": "- \"grounded in 1,420 architectural patterns extracted from 58 production repositories...\"
                 - \"**Stages 0–5 are built and proven — 123 tests green (2 environment-conditional skips)...\"
                 ... (full claim list retained for Gate 1) ..."
    }
  ]
}
```

### 3. Log through brain.py with the real measured latency

```
$ python3 brain.py log --task-type research --tier 1 --outcome success --success true --tokens 0 --latency 29793
{"timestamp": "2026-07-04T02:17:44.658237+00:00", "task_type": "research", "tier": 1, "outcome": "success", "success": true, "tokens": 0, "latency_ms": 29793}
```

### 4. Literal log line now in logs/reasoning_seed.jsonl

```
$ tail -1 logs/reasoning_seed.jsonl
{"timestamp": "2026-07-04T02:17:44.658237+00:00", "task_type": "research", "tier": 1, "outcome": "success", "success": true, "tokens": 0, "latency_ms": 29793}
```

Re-run check: `tail -1 logs/reasoning_seed.jsonl` must show latency_ms 29793.
(tokens: 0 — dispatch.py does not surface child token counts; 0 is the honest "unknown", not a claim.)

Cross-reference: this same round-trip is the Gate 4 `claude -p` delegation-child evidence
(one real child, real completion, measured latency).

### Child output retained for Gate 1 (README claims to reconcile)

- "grounded in 1,420 architectural patterns extracted from 58 production repositories — reimplemented fresh, not copied."
- "**Stages 0–5 are built and proven — 123 tests green (2 environment-conditional skips). NYX (Stage 6) is deliberately out of scope: NYX doesn't exist yet.**"
- "| 0 | Prove & package: ... one real end-to-end request on real disk | ✅ Proven |"
- "| 1 (3A) | ... | ✅ Built, tested |"
- "| 2 (3B) | ... | ✅ Built, tested |"
- "| 3 (3C) | ... | ✅ Built, tested |"
- "| 4 (3D) | ... | ✅ Built, tested |"
- "| 5 | ... | ✅ Built, tested |"
- "| 6 | NYX integration | ⬜ Out of scope — NYX not built yet |"
- "It was benchmarked at 0.933 recall@5 on a hand-labeled corpus, but that corpus was constructed with vocabulary overlap..."

## 0b — Mnemos two-process round-trip on real local disk — GREEN 2026-07-04

Vault: mnemos/vault/mnemos.db on native APFS (~/Documents, CLI host — not the Cowork/FUSE mount).
Canary and init passed with NO WAL-fallback warning, confirming the historical "disk I/O error"
was the sandbox's FUSE view, not this machine. Each store.py CLI invocation below is a separate
OS process.

```
$ python3 mnemos/store.py canary
vault writable
$ python3 mnemos/store.py init
initialized: /Users/anubhavmohandas/Documents/Claude/HERMES/hermes/mnemos/vault/mnemos.db

# process A (shell pid 32970)
$ python3 mnemos/store.py write "stabilize-2026-07-04" "user" "Gate 0a closed 2026-07-04: genuine Tier 1 request logged to reasoning_seed.jsonl with latency_ms=29793 via a real claude -p delegation child; transcript at logs/proof_gate0.md"
wrote message id=33

# process B (shell pid 33249, separate python process)
$ python3 mnemos/store.py search "29793"
[
  {
    "id": 33,
    "session_id": "stabilize-2026-07-04",
    "role": "user",
    "content": "Gate 0a closed 2026-07-04: genuine Tier 1 request logged to reasoning_seed.jsonl with latency_ms=29793 via a real claude -p delegation child; transcript at logs/proof_gate0.md",
    "created_at": "2026-07-04 02:25:43",
    "memory_type": "reference"
  }
]
```

Re-run check: `python3 mnemos/store.py search "29793"` must return message id=33.
The stored memory is itself genuine project state (the Gate 0a result), not filler.

## 0c — ReasoningBank real reward + retrieve_top_k() — GREEN 2026-07-04

The reward logged is genuinely earned: this session's Gate 0a task, whose outcome the human
independently verified on disk. Retrieval was run as a separate process, with the query being
the genuinely similar NEXT task (Gate 4's Tier 2 proof) — i.e., retrieval-before-a-similar-new-task,
as the gate requires. Embedder: default offline hash backend (lexical, per its honest label).

```
$ python3 reasoningbank/bank.py log "Prove a genuine Tier 1 request end-to-end: route with brain.py check, execute a claude -p delegation child, log measured latency to reasoning_seed.jsonl" "brain.py check routed tier 1; delegation/dispatch.py ran one claude -p child (VSCode-bundled CLI appended to PATH) measuring elapsed_ms=29793; brain.py log recorded it; human verified the log line on disk" "Gate 0a green — reasoning_seed.jsonl entry with latency_ms=29793; proof at logs/proof_gate0.md" 0.9 true "claude CLI not on PATH; version-pinned extension binary is fragile — install standalone CLI before automating" 0 29793
{... "reward": 0.9, "success": true, "latency_ms": 29793, "hnsw_label": 3}

$ python3 reasoningbank/bank.py retrieve "Prove a genuine Tier 2 request end-to-end: route with brain.py check, execute an Ollama local chat, log measured latency" 3
[
  {"label": 0, "similarity": -0.0166, "text": "research CVE-2025-1234", ... "reward": 0.95 ...},
  {"label": 3, "similarity": 0.7764, "text": "Prove a genuine Tier 1 request end-to-end: ...", ... "reward": 0.9 ...},
  {"label": 2, "similarity": 0.0652, "text": "verify HERMES Stage 0 exit gate and build state", ... "reward": 0.9 ...}
]
```

Re-run check: the retrieve command above must return label 3 with similarity ≈0.78.

HONEST OBSERVATIONS (surfaced, not acted on — Invariant #3):
1. task_log.jsonl lines 1–2 are seed/demo fixtures ("research CVE-2025-1234", paired
   good/bad approaches). They pollute the audit trail and one OUTRANKS the relevant
   memory at similarity −0.0166 because retrieve_top_k sorts reward-first. Human call:
   purge the fixtures and/or reconsider the (reward, similarity) sort order. Not changed
   here — task_log.jsonl is an audit trail and the sort is security-adjacent ranking logic.
2. Gate met as written: the real memory IS surfaced (top-3, dominant similarity).

## 0d — Curator loop closed once WITH a human — AT HUMAN GATE 2026-07-04 (machine half done)

The recurring failure is real: logs/reflexion_seed.json lines 3–4 record the same crash twice
(dedup_key 20031bba — "store.py write called before init on a fresh vault — crashed with
'no such table: messages'", from the 2026-07-02 session). consolidate.py had already rolled it
up with recurrence_count=2, meeting PROPOSAL_THRESHOLD.

```
$ python3 curator/propose.py
{"proposals_written": 1, "ids": ["err_20031bba"]}

$ cat curator/pending/err_20031bba.json
{
  "id": "err_20031bba",
  "category": "assumption",
  "task": "mnemos first write on fresh vault",
  "failure_mode": "store.py write called before init on a fresh vault — crashed with 'no such table: messages' (canary alone does not create schema)",
  "prevention_rule": "run 'store.py init' (canary + schema) before the first write on any fresh vault; write should give an actionable error naming init",
  "recurrence_count": 2,
  "status": "pending"
}

# no-duplicate check while pending (same dedup logic that must hold post-approval):
$ python3 curator/propose.py
{"proposals_written": 0, "ids": []}
```

REMAINING — HUMAN ONLY (Invariant #3, never self-approved):
1. Anubhav reviews the proposal and runs:  python3 curator/approve.py approve err_20031bba
2. Verify it landed:                       ls curator/approved/   (must show err_20031bba.json)
3. Not-re-proposed check:                  python3 curator/propose.py   (must print proposals_written: 0)
Paste those three outputs below this line to close 0d.

---
