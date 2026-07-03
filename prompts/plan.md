---
deliverable: plan
route: "skills/tasks/SKILL.md for tracking; the plan itself is authored in-conversation (superpowers/gstack autoplan pattern)"
---

# Intake — ask before planning (one message, grouped)

**Required**
1. **What are we planning?** — a build, a research campaign, a pentest engagement, a migration, a launch?
2. **End state** — how do we know it's done? One measurable sentence.
3. **Constraints** — deadline, budget, tools you must/can't use, what already exists.
4. **Depth** — quick brainstorm / structured plan with stages / full design review (challenge assumptions before planning)?

**Optional**
5. Risks you already fear — what's most likely to kill this?
6. Who executes — just you+HERMES, or others (then the plan needs handoff clarity)?
7. Should stages get exit gates (HERMES house style — no stage starts until the previous gate is provably green)?

# Templates

**T1 — Brainstorm (divergent first)**
> Brainstorm approaches to [goal]. Generate 5 meaningfully different options — including one conservative, one aggressive, and one that questions the premise. For each: core idea, biggest risk, what it's best when. No evaluation yet.

**T2 — Design review (challenge before commit)**
> Act as a skeptical senior reviewer of this plan: [plan/approach]. Attack it: hidden assumptions, failure modes, what breaks at 10x, what was decided implicitly that should be explicit. End with: keep / fix-then-keep / rethink, and why.

**T3 — Autoplan (convergent)**
> Turn [chosen approach] into an ordered, staged plan for [goal]. Per stage: goal, build list, exit gate (a provable check, not a feeling). Constraints: [constraints]. Flag the single riskiest stage and its fallback.

# Execution

1. **Diverge** — T1 if Q4 ≥ brainstorm; present options, user picks (or asks HERMES to recommend with reasoning).
2. **Challenge** — T2 on the picked approach if Q4 = design review.
3. **Converge** — T3 into the staged plan with exit gates (Q7).
4. **Track** — hand stages to `skills/tasks` (TaskCreate) so progress is tracked; big multi-session plans also get written to a plan file the user names.
5. **Log** — Mnemos write ("plan: <goal> — <n> stages") + ReasoningBank per Apollo §2.
6. **Deliver** — the plan + the single next concrete action (HERMES house rule: always name the next action).
