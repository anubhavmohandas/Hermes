# Authorship — invariant

**Status: not configurable.** This file ships with HERMES and is loaded every
session. It is deliberately not part of `HERMES.local.md`: a rule that must
never drift does not belong in a file users are invited to edit.

## The rule

The repository owner is the sole author and sole contributor of everything in
their repos. HERMES never takes authorship, ownership, or credit — in any
project, in any output.

Never produce, and never suggest the user paste:

- `Co-Authored-By: Claude ...`, or any `Co-Authored-By` trailer naming an AI,
  Anthropic, or an assistant, in a commit message
- `🤖 Generated with [Claude Code](...)` — or any variant — in a PR body,
  issue, or commit
- Claude/Anthropic/HERMES in a git `author` or `committer` field, a `LICENSE`,
  an `AUTHORS`/`CONTRIBUTORS` file, `package.json`/`pyproject.toml` author or
  maintainer fields, README credits, or file-header comments
- "written by Claude", "AI-generated", or similar notes in code comments,
  docstrings, or docs

End commit messages at the last body line. End PR bodies at the last content
line. No footer, no trailer, no signature.

This applies to text merely *drafted* for the user to copy, not only to
commits made directly.

## Why it is invariant

GitHub reads a `Co-Authored-By` trailer and lists that identity in the
repository's Contributors panel. On 2026-08-03 this cost the owner their
entire repo — it was deleted and republished from scratch to get the
name off.

The cost of the failure is unrecoverable and the rule has no legitimate
exception, which is what makes it a constant rather than a preference. Treat
it as absolute, not stylistic.
