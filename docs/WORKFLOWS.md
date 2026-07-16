# HERMES — example workflows

Three normal-use walkthroughs, each run end-to-end with the **real output shown**
(captured 2026-07-05). They answer "what does using HERMES actually look like?"
rather than "how does it fail?" — the make-it-fail proofs live separately in
`logs/proof_*.md` (local).

**Honest scope (V1_CHECKLIST §6):** these are verified capability walkthroughs
from a hardening session, not a log of organic daily use. The 2-week
actively-try-to-break-it dogfood window (§6 item 1) is a *calendar* requirement
and remains open — no amount of same-day walkthroughs substitutes for it. What
these do establish is that the everyday paths run clean and reproducibly today.

Every command below is copy-pasteable from the repo root.

---

## Workflow 1 — remember something now, find it later (Mnemos)

The memory store classifies each note deterministically (no LLM) and retrieves
by substring/lexical match through FTS5. The search boundary returns typed
`MemoryEntry` objects (V1_CHECKLIST §2 contract), not bare dicts.

```python
import store
from pathlib import Path
db = Path("mnemos/vault/mnemos.db"); store.init_db(db)

store.write_message("sess-demo", "user",
    "I prefer terse answers and I work in the Pacific timezone", db_path=db)
store.write_message("sess-demo", "user",
    "The staging deploy script lives at ops/deploy_staging.sh", db_path=db)

for h in store.search("deploy script", db_path=db):
    print(f"[{h.memory_type}] {h.content}")
```

Real output:

```
[reference] The staging deploy script lives at ops/deploy_staging.sh
-> returned 1 MemoryEntry object(s)
```

What to notice: the deploy note was auto-classified `reference` (it carries a
path); the query "deploy script" matched it and *not* the timezone preference.
Classification is rule-based and inspectable — see `store.classify_memory_type`.

---

## Workflow 2 — route a sensitive vs. a bulk request (Apollo / brain.py)

Tier routing is deterministic policy, not a model's judgment. Sensitivity is a
hard keyword match; the tier follows from sensitivity + task type.

```bash
# sensitive (CVE) -> pinned to Tier 1 (Claude API), no exceptions
python3 brain.py check --task "analyze CVE-2025-1234 exploit chain in these recon notes" \
                       --model claude-opus-4-8

# non-sensitive bulk work -> Tier 2 (NVIDIA API)
python3 brain.py check --task "summarize 200 changelog entries, bulk offline"
```

Real output:

```json
{"sensitive": true,  "task_type": "default", "tier": 1, "tier_name": "Tier 1 — Claude API", "model": "claude-opus-4-8", "allowed": true, "reason": "ALLOWED"}
{"sensitive": false, "task_type": "bulk",    "tier": 2, "tier_name": "Tier 2 — NVIDIA API", "model": null, "allowed": true, "reason": "no model specified — tier computed only"}
```

What to notice: sensitive data goes to Tier 1 ONLY — never Tier 2 (a remote
cloud API since the NVIDIA swap) and never Tier 3 (NYX). Tier 3's independent
re-check (`tier3.py`) is what keeps sensitive data off the external fallback
even under availability pressure.

---

## Workflow 3 — fan a batch of subtasks out to child agents (Delegation)

`--dry-run` builds the exact child argv without spawning anything (so it costs
no tokens). More prompts than the locked cap (3) queue and drain in waves — they
are not rejected.

```bash
python3 delegation/dispatch.py run \
  "audit auth module" "audit billing module" "audit search module" "audit upload module" \
  --dry-run
```

Real output (trimmed):

```
dry_run: True   max_concurrent: 3   queued: 4
child[0] argv: claude -p audit auth module \
  --allowedTools Read,Grep,Glob,Bash,Write,Edit,WebSearch \
  --disallowedTools TaskStop,AskUserQuestion,EnterPlanMode,ExitPlanMode
```

What to notice: four tasks queued under a cap of three (the fourth waits, it is
not dropped), and every child is spawned with `TaskStop`, `AskUserQuestion`,
`EnterPlanMode`, and `ExitPlanMode` force-disallowed — a child cannot stop its
siblings, cannot prompt the human, and cannot enter/exit plan mode, regardless
of what the caller requests. That restriction is architectural, not advisory.
