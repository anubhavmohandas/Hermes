---
name: hermes-tasks
description: HERMES task decomposition sub-skill. Apollo routes here for task/plan/break-down/todo/track requests. Uses the TaskCreate/TaskUpdate pattern to decompose and track work, and logs completions into Mnemos v1. Extension point for deeper Task-Master-style slash commands is noted but not built in Phase 3A.
allowed-tools: TaskCreate, TaskUpdate, Bash, Read
user-invocable: false
---

# skills/tasks — Task decomposition sub-skill

Called by Apollo, not directly by the user.

## What this does in Phase 3A

1. Accept a task description from Apollo.
2. Decompose it into concrete subtasks using `TaskCreate` (one call per
   subtask, or a batch if the tool supports it) — same pattern used
   everywhere else in this HERMES build itself.
3. Track progress with `TaskUpdate` as work proceeds (`pending` →
   `in_progress` → `completed`).
4. On completion, write a short outcome line into Mnemos v1:
   `python3 mnemos/store.py write "<session_id>" "assistant" "completed: <task>"`
5. Return the task list with current status to Apollo.

## Ground rule

Don't create a task list for something that's genuinely one step — that's
noise, not tracking. Match the granularity to what actually has multiple
distinct pieces of work.

## What this explicitly does NOT do yet

- No Task Master-style custom slash commands (`/task:decompose`, etc.) — not
  scheduled to a specific phase in the current blueprint; revisit if the
  plain TaskCreate/TaskUpdate pattern turns out to be insufficient.
- No cross-session task persistence beyond what Mnemos v1 already logs as
  plain text — a real durable task store is Cron/Delegation territory,
  Phase 3C.
