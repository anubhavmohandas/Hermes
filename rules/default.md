---
name: default
scope: "**"
description: Fires every HERMES session, no path restriction. Baseline discipline for tier checking, secrets, and output style.
---

# default.md — fires every session

- Always confirm tier via `brain.py check` before any external call that
  touches a model or an API. Do not assume the previous turn's tier still
  applies if the task description changed materially.
- Never output secrets or API keys. Run anything suspicious through
  `meta/security/redact.py` before it hits a log or a visible response.
- Always run the Apollo verification pass (§2 of `SKILL.md`) before
  delivering final output — check the sub-skill actually answered the
  intent, don't just relay it.
- Default output style is `terse.md` unless the user has asked for verbose
  or bullets, or the complexity of the answer genuinely demands more.
- If a request maps to an offline module, say which phase it lands in.
  Don't quietly attempt a partial version of it.
