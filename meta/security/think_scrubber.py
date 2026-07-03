#!/usr/bin/env python3
"""
think_scrubber.py — streaming think-block scrubber (Phase 3D, pattern P20).

Pattern source (reimplemented fresh, no code copied): CC_SRC_PATTERNS.md P20
— strip model reasoning blocks from streamed output with a STATE MACHINE,
not per-delta regex. Regex-per-chunk misses tags split across chunk
boundaries ("<th" in one delta, "ink>" in the next) and re-scanning the
whole accumulated buffer per delta is O(n²) on long streams.

Why scrub at all: Tier 2/3 models (DeepSeek-R1-style local reasoning models
on Ollama, some API models) emit <think>…</think> blocks. Reasoning text is
(a) not the answer, (b) token bloat if re-ingested by downstream steps, and
(c) occasionally leaks prompt internals — so it never reaches logs, Mnemos,
or the terminal.

The state machine holds back only the longest possible tag-prefix suffix of
each emitted chunk (bounded carry, streaming-safe). Tags are case-insensitive.
Unclosed blocks at end-of-stream stay scrubbed (fail closed) — flush() says
so rather than dumping half a reasoning block.

Usage:
    s = ThinkScrubber()
    for chunk in stream:  out += s.feed(chunk)
    out += s.flush()

CLI (whole-text mode, e.g. scrubbing a saved transcript):
    python3 think_scrubber.py "<text>"       # or:  ... | python3 think_scrubber.py -
"""
import sys

DEFAULT_TAGS = ("think", "thinking", "reasoning", "reflection")


class ThinkScrubber:
    OUTSIDE, INSIDE = 0, 1

    def __init__(self, tags=DEFAULT_TAGS):
        self.open_tags = tuple(f"<{t}>" for t in tags)
        self.close_tags = tuple(f"</{t}>" for t in tags)
        self._max_tag = max(len(t) for t in self.open_tags + self.close_tags)
        self.state = self.OUTSIDE
        self._carry = ""          # unemitted tail that could start a tag
        self._active_close = None  # the close tag matching the open we're inside
        self.blocks_scrubbed = 0

    def _find_tag(self, text: str, tags):
        """Earliest (index, tag) of any of `tags` in text, else (-1, None)."""
        best_i, best_tag = -1, None
        low = text.lower()
        for tag in tags:
            i = low.find(tag)
            if i != -1 and (best_i == -1 or i < best_i):
                best_i, best_tag = i, tag
        return best_i, best_tag

    def _tag_prefix_len(self, text: str, tags):
        """Length of the longest suffix of text that is a strict prefix of
        any tag — the only part that must be carried into the next chunk."""
        low = text.lower()
        for size in range(min(self._max_tag - 1, len(low)), 0, -1):
            suffix = low[-size:]
            if any(tag.startswith(suffix) for tag in tags):
                return size
        return 0

    def feed(self, chunk: str) -> str:
        buf = self._carry + (chunk or "")
        self._carry = ""
        out = []
        while buf:
            if self.state == self.OUTSIDE:
                i, tag = self._find_tag(buf, self.open_tags)
                if i == -1:
                    keep = self._tag_prefix_len(buf, self.open_tags)
                    if keep:
                        out.append(buf[:-keep])
                        self._carry = buf[-keep:]
                    else:
                        out.append(buf)
                    buf = ""
                else:
                    out.append(buf[:i])
                    self._active_close = f"</{tag[1:]}"  # "<think>" -> "</think>"
                    buf = buf[i + len(tag):]
                    self.state = self.INSIDE
            else:  # INSIDE — emit nothing until the matching close tag
                i, _ = self._find_tag(buf, (self._active_close,))
                if i == -1:
                    keep = self._tag_prefix_len(buf, (self._active_close,))
                    self._carry = buf[-keep:] if keep else ""
                    buf = ""
                else:
                    buf = buf[i + len(self._active_close):]
                    self.state = self.OUTSIDE
                    self._active_close = None
                    self.blocks_scrubbed += 1
        return "".join(out)

    def flush(self) -> str:
        """End of stream. Outside a block, any held tag-prefix was a false
        alarm — emit it. Inside a block, the content stays scrubbed (fail
        closed) and the truncation is named instead of leaked."""
        carry, self._carry = self._carry, ""
        if self.state == self.OUTSIDE:
            return carry
        self.state = self.OUTSIDE
        self._active_close = None
        self.blocks_scrubbed += 1
        return "[think-block truncated at end of stream — scrubbed]"


def scrub_text(text: str, tags=DEFAULT_TAGS) -> str:
    s = ThinkScrubber(tags)
    return s.feed(text) + s.flush()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: think_scrubber.py \"<text>\" | -   (- reads stdin)", file=sys.stderr)
        sys.exit(2)
    source = sys.stdin.read() if sys.argv[1] == "-" else sys.argv[1]
    sys.stdout.write(scrub_text(source))
