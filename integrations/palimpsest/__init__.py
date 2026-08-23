"""
integrations/palimpsest/ — HERMES's AI-watermark / provenance-metadata
stripper. Extracted patterns from a third-party watermark-removal project,
reimplemented fresh per HERMES's no-copied-code policy (see SKILL.md §9),
and renamed on integration — same convention as Apollo, Mnemos, Clio,
Laconic, Occam. "Palimpsest": a manuscript scraped clean of earlier
writing so the surface can be reused — the literal shape of what this
module does to a file's provenance layer.

Mode control (flag file, /palimpsest command, hook wiring) lives in
meta/palimpsest.py, one directory up — mirroring where meta/laconic.py and
meta/occam.py sit relative to their own supporting code. This package is
the mechanical engine meta/palimpsest.py calls; it has no opinion about
when it runs.

See format_route.py for the single entry point (`clean_path`), and each
submodule's own docstring for exactly what is and is not covered.
"""

from format_route import classify, clean_path, is_denylisted  # noqa: F401
from text_unicode import clean_text, inspect_text  # noqa: F401

__all__ = ["classify", "clean_path", "is_denylisted", "clean_text", "inspect_text"]
