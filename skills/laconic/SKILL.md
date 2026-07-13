---
name: laconic
description: Opt-in token-reduction mode. Activate with natural language ("go laconic", "be brief", "less tokens"), deactivate with "stop laconic" / "normal mode". Compresses every response — no preamble, no postamble, code/diff first. Auto-suspends for security warnings, destructive operations, or user confusion.
---

# Laconic mode

Reimplemented from a third-party plugin's extracted token-reduction
patterns (#161-166, `CC_SRC_PATTERNS.md` Task #29) — renamed on
integration per HERMES convention (Apollo, Mnemos, Clio, Curator follow
the same pattern: internal name differs from the source project's name).
State lives in `meta/laconic.py`;
enforcement is a per-turn `UserPromptSubmit` hook (`hooks/laconic_mode.sh`),
not a one-time instruction — one-time instructions decay over a long
session or when other plugin hooks inject competing context.

## Activation

Say any of: "go laconic", "laconic mode", "be brief", "be terse",
"less tokens", "fewer tokens", "stop wasting tokens". The hook writes a
flag file (`$CLAUDE_CONFIG_DIR/.hermes-laconic-active`, default mode
`full`) and every subsequent turn gets a compressed-output reminder
injected via `additionalContext` until deactivated.

## Deactivation

Say "stop laconic", "laconic off", "normal mode", or "be verbose again".
Flag file is removed.

## Auto-clarity override

Even while active, if the current turn's content matches a safety-critical
pattern — destructive operation (`rm -rf`, `drop table`, "delete
everything"), a security warning, or user confusion ("I don't
understand", "are you sure") — compression is suspended for that one
response. This is a content classification of the current prompt, not a
user command, and it resumes automatically next turn. Never let
compression mask a safety-critical explanation.

## File-compression capability (laconic-compress)

Separate from the per-turn mode: `meta/laconic.py` also exposes
`can_compress(path)` and `validate_compression(original, compressed)` for
compressing files (e.g. Mnemos vault entries, CLAUDE.md) before sending
them through an LLM pass.

- `can_compress()` refuses on a sensitive-path denylist (`.env`, `.ssh`,
  `.aws`, `.kube`, `.gnupg`, `credentials*`, `secrets*`, `id_rsa*`,
  `*.pem`, `*.key`), a 500KB size cap, and skips `*.original.md` backups.
  The file is never read if the check fails.
- `validate_compression()` runs after compression and errors (not warns)
  if heading count/order changed, code block content changed, or the URL
  set changed. Bullet count drift >15% is a warning only. On error, fix
  the specific failure — do not silently accept a structurally corrupted
  compression.

## What this module does NOT do

It does not touch model selection, tool routing, or security gates. It is
purely an output-verbosity behavioral mode, opt-in, reversible mid-session
at any time.
