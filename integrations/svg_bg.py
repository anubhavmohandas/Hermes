#!/usr/bin/env python3
"""
integrations/svg_bg.py — Haikei-style SVG background generator.

Pattern source: haikei.app (web GUI generator for waves / blobs / peaks /
blurry gradients). Haikei has NO public API or CLI — it is a browser tool
(plus a Figma plugin), so HERMES can't call it. This file reimplements the
*shape families* fresh (no code copied, Invariant #4) so the build pipeline
can produce the same kind of asset deterministically, from the project's own
tokens, without a human clicking export.

Every generator is seeded — same seed + params = byte-identical SVG, so a
background can be regenerated after a palette change without drifting.

CLI:
    python3 integrations/svg_bg.py <kind> [--w 1440] [--h 560] [--seed 7]
        [--colors "#0b0d10,#4f8cff,#9b5cff"] [--layers 4] [--out bg.svg]
    python3 integrations/svg_bg.py list
kinds: waves, layered-waves, peaks, blob, blob-scene, blurry-gradient, circles

--colors: first = background fill, rest = shape colors (cycled/interpolated).
Omit --colors to pull color.bg + color.accent from ./tokens.json if present.
"""
import json
import math
import random
import sys
from pathlib import Path

KINDS = ["waves", "layered-waves", "peaks", "blob", "blob-scene",
         "blurry-gradient", "circles"]


# ---------- color helpers ----------
def _hex(c: str):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = _hex(a), _hex(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ra, rb))


def _ramp(colors, n):
    """n colors interpolated across the given stops (>=1 stop)."""
    if len(colors) == 1 or n == 1:
        return [colors[0]] * n
    out = []
    for i in range(n):
        pos = i / (n - 1) * (len(colors) - 1)
        j = min(int(pos), len(colors) - 2)
        out.append(_mix(colors[j], colors[j + 1], pos - j))
    return out


def _tokens_colors():
    p = Path("tokens.json")
    if p.exists():
        try:
            c = json.loads(p.read_text()).get("color", {})
            if c.get("bg") and c.get("accent"):
                return [c["bg"], c["accent"], _mix(c["accent"], c.get("fg", "#ffffff"), 0.35)]
        except (ValueError, AttributeError):
            pass
    return ["#0b0d10", "#4f8cff", "#9b5cff"]


# ---------- path helpers ----------
def _smooth(points, close=False):
    """Catmull-Rom -> cubic Bezier through points (open curve or closed loop)."""
    n = len(points)
    if close:
        get = lambda k: points[k % n]
        segs = range(n)
    else:
        get = lambda k: points[max(0, min(n - 1, k))]
        segs = range(n - 1)
    d = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
    for i in segs:
        p0, p1, p2, p3 = get(i - 1), get(i), get(i + 1), get(i + 2)
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d + (" Z" if close else "")


def _wave_path(rng, w, h, base_y, amp, n=6, smooth=True):
    pts = [(w * i / n, base_y + rng.uniform(-amp, amp)) for i in range(n + 1)]
    line = _smooth(pts) if smooth else "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return f"{line} L{w},{h} L0,{h} Z"


def _blob_path(rng, cx, cy, r, points=7, wobble=0.35):
    pts = []
    for i in range(points):
        a = 2 * math.pi * i / points
        rr = r * (1 + rng.uniform(-wobble, wobble))
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return _smooth(pts, close=True)


# ---------- generators ----------
def generate(kind, w=1440, h=560, seed=7, colors=None, layers=4):
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; choose from {KINDS}")
    rng = random.Random(seed)
    colors = colors or _tokens_colors()
    bg, shapes = colors[0], (colors[1:] or [colors[0]])
    body, defs = [], ""

    if kind == "waves":
        body.append(f'<path d="{_wave_path(rng, w, h, h * 0.6, h * 0.08)}" fill="{shapes[0]}"/>')
    elif kind in ("layered-waves", "peaks"):
        fills = _ramp(shapes, layers)
        for i in range(layers):
            y = h * (0.35 + 0.5 * i / max(layers - 1, 1))
            d = _wave_path(rng, w, h, y, h * 0.06, n=8 if kind == "peaks" else 6,
                           smooth=(kind != "peaks"))
            body.append(f'<path d="{d}" fill="{fills[i]}"/>')
    elif kind == "blob":
        body.append(f'<path d="{_blob_path(rng, w / 2, h / 2, min(w, h) * 0.32)}" fill="{shapes[0]}"/>')
    elif kind == "blob-scene":
        fills = _ramp(shapes, layers)
        for i in range(layers):
            cx, cy = rng.uniform(0, w), rng.uniform(0, h)
            body.append(f'<path d="{_blob_path(rng, cx, cy, min(w, h) * rng.uniform(0.18, 0.35))}" '
                        f'fill="{fills[i]}" opacity="0.9"/>')
    elif kind == "blurry-gradient":
        blur = min(w, h) * 0.18
        defs = (f'<defs><filter id="b" x="-50%" y="-50%" width="200%" height="200%">'
                f'<feGaussianBlur stdDeviation="{blur:.0f}"/></filter></defs>')
        fills = _ramp(shapes, layers)
        circles = "".join(
            f'<circle cx="{rng.uniform(0, w):.0f}" cy="{rng.uniform(0, h):.0f}" '
            f'r="{min(w, h) * rng.uniform(0.25, 0.45):.0f}" fill="{fills[i]}"/>'
            for i in range(layers))
        body.append(f'<g filter="url(#b)">{circles}</g>')
    elif kind == "circles":
        fills = _ramp(shapes, layers)
        for _ in range(layers * 6):
            body.append(f'<circle cx="{rng.uniform(0, w):.0f}" cy="{rng.uniform(0, h):.0f}" '
                        f'r="{rng.uniform(4, min(w, h) * 0.06):.0f}" '
                        f'fill="{rng.choice(fills)}" opacity="{rng.uniform(0.3, 0.9):.2f}"/>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" preserveAspectRatio="none" aria-hidden="true">'
            f'{defs}<rect width="{w}" height="{h}" fill="{bg}"/>{"".join(body)}</svg>\n')


def _arg(args, name, default, cast=str):
    if name in args:
        i = args.index(name)
        return cast(args[i + 1])
    return default


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if a else 2)
    if a[0] == "list":
        print(json.dumps({"kinds": KINDS, "api_required": False,
                          "note": "Haikei itself is GUI-only; this is the code-side equivalent"}, indent=2))
        sys.exit(0)
    cols = _arg(a, "--colors", None)
    svg = generate(a[0], w=_arg(a, "--w", 1440, int), h=_arg(a, "--h", 560, int),
                   seed=_arg(a, "--seed", 7, int), layers=_arg(a, "--layers", 4, int),
                   colors=[c.strip() for c in cols.split(",")] if cols else None)
    out = _arg(a, "--out", None)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(svg)
        print(json.dumps({"kind": a[0], "file": out, "bytes": len(svg)}))
    else:
        sys.stdout.write(svg)
