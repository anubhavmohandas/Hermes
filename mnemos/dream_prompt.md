# Dream consolidation prompt — extension point

This is NOT executed by `dream.py` — that script only does deterministic
consolidation (dedup, recurrence counting). This file is the template for
the LLM-driven synthesis pass that a real "dream" cycle implies: reviewing
the day's `logs/reasoning_seed.jsonl` and `curator/reflexion.json`, and
producing a short narrative summary of what was learned, worth surfacing to
the human at the next session start.

## When this gets wired in (Phase 3C, alongside Cron)

Feed the model:
- Today's new entries from `logs/reasoning_seed.jsonl`
- Today's new/updated entries from `curator/reflexion.json`
- The prior day's dream summary (if any), for continuity

Ask it to produce:
- 2-3 sentences: what patterns showed up today (repeated failures, tier
  distribution, anything worth a human's attention)
- Nothing invented — if nothing notable happened, say that plainly instead
  of padding a summary out of thin material
