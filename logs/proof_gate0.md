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

## 0b — Mnemos two-process round-trip on real local disk — OPEN

## 0c — ReasoningBank real reward + retrieve_top_k() — OPEN

## 0d — Curator loop closed once WITH a human — OPEN (requires human approval step)
