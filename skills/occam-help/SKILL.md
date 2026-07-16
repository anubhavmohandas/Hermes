---
name: occam-help
description: >
  Quick-reference card for all Occam modes, skills, and commands.
  One-shot display, not a persistent mode. Trigger: /occam-help,
  "occam help", "what occam commands", "how do I use occam".
---

# Occam Help

Display this reference card when invoked. One-shot, do NOT change mode,
write flag files, or persist anything.

## Levels

| Level | Trigger | What change |
|-------|---------|-------------|
| **Lite** | `/occam lite` | Build what's asked, name the lazier alternative in one line. |
| **Full** | `/occam` | The ladder enforced: YAGNI → stdlib → native → one line → minimum. Default. |
| **Ultra** | `/occam ultra` | YAGNI extremist. Deletion before addition. Challenges requirements before building. |

Level sticks until changed or session end.

## Skills

| Skill | Trigger | What it does |
|-------|---------|--------------|
| **occam** | `/occam` | Lazy mode itself. Simplest solution that works. |
| **occam-review** | `/occam-review` | Over-engineering review of the current diff: `L42: yagni: factory, one product. Inline.` |
| **occam-audit** | `/occam-audit` | Whole-repo over-engineering audit: ranked list of what to delete. |
| **occam-debt** | `/occam-debt` | Harvest `occam:` shortcut comments into a tracked ledger. |
| **occam-gain** | `/occam-gain` | Source project's measured-impact scoreboard (not HERMES's own number — see that skill's honesty boundary). |
| **occam-help** | `/occam-help` | This card. |

## Deactivate

Say "stop occam" or "normal mode". Resume anytime with `/occam`.
`/occam off` also works.

## Configure default mode

Default mode = `full`, auto-active every session. Change it:

**Environment variable** (highest priority):
```bash
export OCCAM_DEFAULT_MODE=ultra
```

**Config file** (`~/.config/occam/config.json`, Windows: `%APPDATA%\occam\config.json`):
```json
{ "defaultMode": "lite" }
```

Set `"off"` to disable auto-activation on session start, activate manually
with `/occam` when wanted.

Resolution: env var > config file > `full`.

## Boundaries

Occam governs what you build, not how you talk — pair with `/go laconic`
(`skills/laconic/SKILL.md`) for terse prose on top of lazy code.
