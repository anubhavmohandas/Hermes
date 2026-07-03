#!/usr/bin/env python3
"""
integrations/caveman.py — Caveman mode (Stage 5): aggressive token reduction.

Pattern source (reimplemented fresh, no code copied): the `caveman` extraction
repo's premise — drop function words, keep content words, to cut tokens on
bulk/offline work where terseness beats grammar. Distinct from
output-styles/terse.md (a prompt-level style): this is a deterministic TEXT
TRANSFORM you can apply to a payload before it goes to a Tier 2 bulk job.

Fallback (Invariant #5): it only ever removes tokens from a known stopword
set and collapses whitespace — it never rewrites content words, so the
degraded case is "less compression", never "corrupted meaning". `--stats`
reports the real reduction so you can decide if it's worth it per task.

Honest limit: this trades readability for tokens. Do NOT run it on anything
a human reads as prose, on code, or on sensitive text where a dropped "not"
changes meaning — the stopword set deliberately keeps negations ("not",
"no", "never") for exactly that reason.

CLI:
    python3 integrations/caveman.py "<text>"        # compressed text
    python3 integrations/caveman.py --stats "<text>"
"""
import json
import re
import sys

# Function words safe to drop. Negations and quantifiers are deliberately
# EXCLUDED — dropping "not"/"no"/"never" flips meaning.
STOPWORDS = {
    "a", "an", "the", "of", "to", "in", "on", "at", "for", "with", "and",
    "or", "but", "is", "are", "was", "were", "be", "been", "being", "am",
    "this", "that", "these", "those", "it", "its", "as", "by", "from",
    "into", "about", "over", "then", "so", "than", "such", "very", "just",
    "also", "which", "who", "whom", "whose", "there", "here", "will", "would",
    "could", "should", "may", "might", "can", "do", "does", "did", "have",
    "has", "had", "i", "you", "he", "she", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "our", "their",
}


def compress(text: str) -> str:
    def keep(word):
        core = re.sub(r"[^\w']", "", word).lower()
        return core not in STOPWORDS or core == ""
    out = []
    for token in (text or "").split():
        if keep(token):
            out.append(token)
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def stats(text: str) -> dict:
    compressed = compress(text)
    orig_words = len((text or "").split())
    new_words = len(compressed.split())
    # ~4 chars/token heuristic for a reporting-only estimate (matches Clio).
    orig_tok = max(1, len(text or "") // 4)
    new_tok = max(1, len(compressed) // 4)
    return {
        "original_words": orig_words,
        "compressed_words": new_words,
        "word_reduction_pct": round(100 * (1 - new_words / max(1, orig_words)), 1),
        "est_token_reduction_pct": round(100 * (1 - new_tok / max(1, orig_tok)), 1),
        "compressed": compressed,
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--stats":
        print(json.dumps(stats(" ".join(args[1:])), indent=2))
    elif args:
        print(compress(" ".join(args)))
    else:
        print("usage: caveman.py [--stats] \"<text>\"", file=sys.stderr)
        sys.exit(2)
