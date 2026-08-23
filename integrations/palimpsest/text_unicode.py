#!/usr/bin/env python3
"""
integrations/palimpsest/text_unicode.py — Layer A: invisible-Unicode /
format-control / space-homoglyph stripper.

Pattern source (reimplemented fresh, no code copied): a third-party
watermark-removal project's text-layer cleaner (extracted patterns, HERMES
integration 2026-08-23 — see integrations/palimpsest/__init__.py and
meta/palimpsest.py for the rename rationale, same convention as Apollo,
Mnemos, Clio, Laconic, Occam).

Scope, stated plainly (Occam: build what's proven, name what's cut):
  - Covers deterministic, edit-based carriers: zero-width/format control
    characters, bidi override marks, variation selectors, Unicode "tag"
    characters (steganography vector), noncharacters, and space/Latin
    homoglyphs.
  - Does NOT cover statistical (token-sampling) watermarks — SynthID-Text,
    Kirchenbauer green-list, keyed-Gumbel/EXP schemes. Those are properties
    of *which words a model chose*, not stray codepoints; detecting or
    removing them needs the generating model's sampling distribution or a
    trained classifier, not a stdlib text scan. No detector for this
    exists in this module — say so if asked, never claim otherwise.
  - The confusable-homoglyph fold (Cyrillic/fullwidth Latin lookalikes) is
    OFF by default because it rewrites real characters, not just invisible
    ones — enable explicitly (aggressive=True) only when the text is known
    to be Latin-script content that acquired lookalike substitutions.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

# --- Strip set: invisible / format-control codepoints -----------------
# Zero-width family, bidi controls, Mongolian/Khmer/Hangul fillers and
# variation selectors, deprecated format chars, BOM-as-ZWNBSP, and the
# Unicode Tag block (U+E0000-E007F) — the last is a known steganography
# channel (invisible per-character tags riding on top of ordinary text).
STRIP_CODEPOINTS: frozenset[int] = frozenset(
    {
        0x00AD,  # soft hyphen
        0x034F,  # combining grapheme joiner
        0x061C,  # Arabic letter mark
        0x115F, 0x1160,  # Hangul choseong/jungseong filler
        0x17B4, 0x17B5,  # Khmer inherent vowel (invisible forms)
        0x180B, 0x180C, 0x180D, 0x180E, 0x180F,  # Mongolian FVS / vowel separator
        0x200B, 0x200C, 0x200D,  # ZWSP, ZWNJ, ZWJ
        0x200E, 0x200F,  # LRM, RLM
        0x202A, 0x202B, 0x202C, 0x202D, 0x202E,  # LRE/RLE/PDF/LRO/RLO
        0x2060, 0x2061, 0x2062, 0x2063, 0x2064,  # word joiner, invisible math ops
        0x2066, 0x2067, 0x2068, 0x2069,  # LRI/RLI/FSI/PDI
        0x206A, 0x206B, 0x206C, 0x206D, 0x206E, 0x206F,  # deprecated format chars
        0x3164,  # Hangul filler (compatibility jamo)
        0xFEFF,  # BOM / ZWNBSP
        0xFFA0,  # halfwidth Hangul filler
        0xFFF9, 0xFFFA, 0xFFFB,  # interlinear annotation controls
    }
    | set(range(0xFE00, 0xFE10))  # variation selectors 1-16
)
TAG_RANGE = range(0xE0000, 0xE0080)  # Unicode Tag block (flag-emoji + stego)
_VS_SUPPLEMENT = range(0xE0100, 0xE01F0)  # variation selectors 17-256


def _is_noncharacter(cp: int) -> bool:
    """The 66 permanently-reserved Unicode noncharacters (TUS 23.7):
    U+FDD0..U+FDEF and U+nFFFE/U+nFFFF at the end of every plane. Never
    assigned, prohibited in interchange — safe to strip unconditionally."""
    return 0xFDD0 <= cp <= 0xFDEF or (cp & 0xFFFE) == 0xFFFE


def _is_strip_cp(cp: int) -> bool:
    return (
        cp in STRIP_CODEPOINTS
        or cp in TAG_RANGE
        or cp in _VS_SUPPLEMENT
        or _is_noncharacter(cp)
    )


# --- Space homoglyphs: exotic spaces that render like U+0020 ------------
SPACE_HOMOGLYPHS: dict[int, str] = {
    cp: " "
    for cp in (
        0x00A0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005,
        0x2006, 0x2007, 0x2008, 0x2009, 0x200A, 0x202F, 0x205F, 0x3000,
    )
}

# --- Latin confusables: Cyrillic + fullwidth lookalikes (opt-in only) ---
# Built from small explicit tables plus the fullwidth Latin block, which is
# a fixed offset from ASCII (U+FF21 = fullwidth 'A' = ASCII 'A' + 0xFF01),
# so it's generated rather than hand-transcribed 52 times (Occam: formula
# over boilerplate).
_CYRILLIC_CONFUSABLES: dict[int, str] = {
    0x0410: "A", 0x0412: "B", 0x0415: "E", 0x041A: "K", 0x041C: "M",
    0x041D: "H", 0x041E: "O", 0x0420: "P", 0x0421: "C", 0x0422: "T",
    0x0425: "X", 0x0430: "a", 0x0435: "e", 0x043E: "o", 0x0440: "p",
    0x0441: "c", 0x0443: "y", 0x0445: "x", 0x0456: "i",
}
_FULLWIDTH_CONFUSABLES: dict[int, str] = {
    cp: chr(cp - 0xFEE0)
    for cp in list(range(0xFF21, 0xFF3B)) + list(range(0xFF41, 0xFF5B))
}
LATIN_CONFUSABLES: dict[int, str] = {**_CYRILLIC_CONFUSABLES, **_FULLWIDTH_CONFUSABLES}

# --- Emoji glue: ZWJ / variation selectors are load-bearing next to an
# emoji base (flag sequences, ZWJ family emoji, text/emoji presentation).
# Stripping them unconditionally breaks real, visible emoji — so they are
# only removed when NOT adjacent to something that looks like an emoji
# base. This is a heuristic, not a full emoji-sequence grammar; it favors
# preserving emoji over aggressive stripping. -----------------------------
_EMOJI_GLUE = frozenset({0x200D, 0xFE0E, 0xFE0F})


def _is_emoji_base(cp: int | None) -> bool:
    if cp is None:
        return False
    return (
        0x1F000 <= cp <= 0x1FAFF
        or 0x2190 <= cp <= 0x2BFF  # arrows, technical/misc symbols, dingbats
        or cp in (0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x3030, 0x303D, 0x3297, 0x3299)
        or cp in (0x0023, 0x002A)  # keycap '#'/'*'
        or 0x0030 <= cp <= 0x0039  # keycap digits
    )


def _char_label(ch: str) -> str:
    cp = ord(ch)
    return f"U+{cp:04X} {unicodedata.name(ch, 'UNKNOWN')} ({unicodedata.category(ch)})"


def clean_text(
    text: str,
    *,
    normalize_spaces: bool = True,
    aggressive_confusables: bool = False,
    nfkc: bool = False,
) -> tuple[str, dict]:
    """Strip Layer-A watermark carriers from *text*. Returns (cleaned, stats).

    Preserves emoji sequences (ZWJ chains, flag tags, text/emoji variation
    selectors) by checking neighbours before stripping glue codepoints.
    Everything else in STRIP_CODEPOINTS/TAG_RANGE/noncharacters is removed
    unconditionally — those have no legitimate role in interchange text.
    """
    removed: Counter[str] = Counter()
    replaced: Counter[str] = Counter()
    out: list[str] = []
    n = len(text)
    tag_run_active = False

    for i, ch in enumerate(text):
        cp = ord(ch)
        prev_cp = ord(text[i - 1]) if i > 0 else None
        next_cp = ord(text[i + 1]) if i + 1 < n else None

        if cp in _EMOJI_GLUE and (_is_emoji_base(prev_cp) or _is_emoji_base(next_cp)):
            out.append(ch)
            continue
        if cp in TAG_RANGE:
            # Subdivision flag tag sequence (e.g. England flag = black flag
            # base + a run of tag chars + cancel tag 0xE007F): keep the
            # whole run once it starts right after an emoji base. State is
            # needed here (not just the immediate neighbour) because the
            # run can be several characters long.
            if tag_run_active or _is_emoji_base(prev_cp):
                tag_run_active = True
                out.append(ch)
                continue
            removed[_char_label(ch)] += 1
            continue
        tag_run_active = False

        if _is_strip_cp(cp):
            removed[_char_label(ch)] += 1
            continue
        if normalize_spaces and cp in SPACE_HOMOGLYPHS:
            out.append(SPACE_HOMOGLYPHS[cp])
            replaced[_char_label(ch)] += 1
            continue
        if aggressive_confusables and cp in LATIN_CONFUSABLES:
            out.append(LATIN_CONFUSABLES[cp])
            replaced[_char_label(ch)] += 1
            continue
        out.append(ch)

    result = "".join(out)
    if nfkc:
        result = unicodedata.normalize("NFKC", result)

    stats = {
        "input_length": len(text),
        "output_length": len(result),
        "removed_count": sum(removed.values()),
        "replaced_count": sum(replaced.values()),
        "removed": dict(removed),
        "replaced": dict(replaced),
    }
    return result, stats


# --- Entity-encoded carriers ---------------------------------------------
# A watermark codepoint can ride inside markup as a numeric character
# reference (&#8203; / &#x200b;) instead of a literal byte — invisible in a
# text editor either way once rendered. This only ever deletes an entity
# whose *decoded* value is in the strip set (or maps it to its homoglyph
# replacement); it never touches named entities (&amp; &lt; ...) or any
# reference outside the strip set, so structural markup is untouched.
_ENTITY_RE = re.compile(r"&#(x?)([0-9a-fA-F]+);")


def clean_entity_references(text: str) -> tuple[str, int]:
    count = 0

    def _sub(m: re.Match) -> str:
        nonlocal count
        try:
            cp = int(m.group(2), 16 if m.group(1) else 10)
        except ValueError:
            return m.group(0)
        if _is_strip_cp(cp):
            count += 1
            return ""
        if cp in SPACE_HOMOGLYPHS:
            count += 1
            return " "
        return m.group(0)

    return _ENTITY_RE.sub(_sub, text), count


def inspect_text(text: str) -> dict:
    """Report-only pass: what would clean_text() touch, without touching it."""
    _cleaned, stats = clean_text(text)
    return {
        "length": len(text),
        "suspicious_count": stats["removed_count"] + stats["replaced_count"],
        "removed": stats["removed"],
        "replaced": stats["replaced"],
        "note": (
            "Layer A only (invisible Unicode + space homoglyphs). Statistical "
            "token-sampling watermarks (SynthID-Text, Kirchenbauer, Gumbel/EXP) "
            "are not detectable by this scan."
        ),
    }
