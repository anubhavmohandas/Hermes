---
name: palimpsest
description: >
  Explains HERMES's AI-watermark / provenance-metadata stripper. Use when
  the user asks what Palimpsest is, whether a file HERMES wrote still
  carries AI-generation markers, how to change its mode (safe/aggressive/
  off), or why a specific format isn't covered. This is NOT a mode the
  model performs like Occam/Laconic — it's a mechanical PostToolUse hook
  that rewrites files on disk right after Write/Edit produces them. Do NOT
  claim it scrubs the assistant's own chat replies; no hook in this
  platform intercepts that text.
---

# Palimpsest

A palimpsest is a manuscript scraped clean of earlier writing so the
surface can be reused. Reimplemented from a third-party watermark-removal
project's patterns — architecture and codepoint/format tables extracted,
code written fresh — renamed on integration per HERMES convention (Apollo,
Mnemos, Clio, Laconic, Occam; see `SKILL.md` §9: no code copied from any
analyzed repo, ever). State lives in `meta/palimpsest.py`; the actual
cleaning engine is `integrations/palimpsest/` (`text_unicode.py`,
`image_meta.py`, `container_meta.py`, `format_route.py`).

## What it actually does

Right after any `Write`/`Edit`/`MultiEdit`/`NotebookEdit` tool call
finishes, `hooks/palimpsest_clean.sh` (`PostToolUse`) hands the written
path to `format_route.clean_path()`, which routes by format:

| Format | What gets stripped |
|---|---|
| Any text/code file | Layer A: zero-width/format-control Unicode, bidi overrides, Unicode Tag-block steganography chars, noncharacters, exotic-space homoglyphs normalized to `U+0020`. Emoji ZWJ sequences and flag-tag sequences are detected and preserved. |
| PNG | Ancillary chunks that only ever carry text/provenance: `tEXt`, `zTXt`, `iTXt`, `eXIf`, `tIME`, `dSIG`. Pixel data (`IDAT`) and every chunk needed to render (`IHDR`, `PLTE`, `tRNS`, color-profile chunks, APNG frames, ...) is untouched — round-trip verified against Pillow, pixels bit-identical. |
| JPEG | `APP1` (EXIF/XMP), `APP11` (JUMBF/C2PA), `COM` segments. Scan data and every other segment (including `APP14` Adobe color transform) untouched. |
| DOCX / XLSX / PPTX | `docProps/core.xml` (`dc:creator`, `cp:lastModifiedBy`, `dc:title`, `dc:subject`, `dc:description`, `cp:keywords`, `cp:category`, `cp:contentStatus` blanked — dates/revision counters left alone), `docProps/app.xml` (`Application`, `AppVersion`, `Company`, `Manager` blanked), `docProps/custom.xml` (every custom property value blanked), plus a Layer A pass over every text-bearing XML/rels part (`word/document.xml`, `xl/sharedStrings.xml`, `ppt/slides/*.xml`, ...). Safe because none of the Layer A carrier codepoints are structural XML characters (`< > & " '`), so it never needs a tag-aware parser. |
| PDF | Best-effort, byte-level, same-length in-place blanking of `/Info` dict strings (`/Title /Author /Subject /Keywords /Creator /Producer`) and the XMP metadata packet (blanking XMP-packet content is spec-sanctioned padding, not a hack). **Does not do a structural rebuild** — a PDF 1.5+ file with its Info dict inside a compressed object stream won't be reached; the result says so rather than reporting false success. |
| HTML | `<meta name="generator">` tags, HTML comments matching generator/AI-tool signatures, plus Layer A. |
| Markdown | Generator/AI-tool signature comments plus Layer A. |
| SVG | `<metadata>` blocks, `<rdf:RDF>` blocks, plus Layer A. |

Never touched, on purpose: paths matching a sensitive-file denylist
(`.env`, `.ssh`, `.aws`, `.gnupg`, `credentials*`, `secrets*`, `id_rsa*`,
`*.pem`, `*.key`) — a "cleaned" secrets file is a contradiction, not a
feature.

## What it does NOT cover (say so plainly if asked)

- **The assistant's own chat text**, before it's shown to the user. No
  hook event in this platform (`SessionStart`, `UserPromptSubmit`,
  `PreToolUse`, `PostToolUse`, `SubagentStart`) intercepts a response
  before render. Palimpsest only ever sees files that were actually
  written to disk via a tool call. If HERMES answers a question in plain
  chat and nothing gets written, Palimpsest never runs on that text.
- **Statistical (token-sampling) watermarks** — SynthID-Text, Kirchenbauer
  green-list, keyed-Gumbel/EXP schemes. These are a property of *which
  words the generating model chose*, not stray codepoints; removing them
  needs a rewrite pass against the model's own sampling distribution or a
  trained classifier — neither exists in this stdlib module. No detector
  for this class is implemented; don't imply otherwise.
- **WebP, AVIF, HEIC, BMP, GIF, TIFF** images — each needs its own
  container parser (RIFF / ISOBMFF box tree / format-specific trailer);
  not ported this pass. `format_route.classify()` reports these as
  `"unsupported"`, not silently as clean.
- **Audio/video (MP4/MOV/WAV/MP3), EPUB, ODT** — same: not ported.
- **C2PA manifest verification** — this strips chunks/segments that
  commonly *carry* a C2PA manifest; it does not parse or verify C2PA
  signatures. A signed manifest that survives elsewhere in a file this
  module doesn't yet parse would not be caught.

## Modes

```
/palimpsest safe          → default. Layer A + all metadata stripping. Never rewrites a visible character.
/palimpsest aggressive     → safe, plus folds Cyrillic/fullwidth-Latin confusables in plain text (rewrites visible characters — real risk to legitimate multilingual content, hence not the default)
/palimpsest off            → hook still fires, does no I/O
/palimpsest default <mode> → persist a new default across sessions
"stop palimpsest"          → off, this session
"start palimpsest"         → back to safe, this session
```

On by default at `safe` — this is deliberate and different from
Laconic/Occam's opt-in-by-phrase defaults, because the point of this
module is that the user shouldn't have to remember to ask for it.

## Boundaries

Palimpsest governs file provenance hygiene, not code quality (pair with
Occam) or response length (pair with Laconic). It runs after the tool
call already succeeded — it can add a note, never block or fail a write.
