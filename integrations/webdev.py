#!/usr/bin/env python3
"""
integrations/webdev.py — webdev scaffolding (Stage 5, opt-in).

Pattern source (reimplemented fresh, no code copied): the v1 blueprint's
"webdev/ (React/Next.js gen, design tokens)". Per HERMES_GOAL_Start_to_End.md
Stage 5, this is opt-in breadth, not critical path. Scope kept honest: it
scaffolds a minimal static component + a design-tokens file from a spec —
deterministic templating, NOT a full framework generator (that would be
copied code, Invariant #4). The fallback is that it needs no toolchain at
all: it emits plain files you can drop into any React/Next project.

Design tokens are emitted as CSS custom properties AND a JSON mirror, so the
same tokens drive CSS and JS without a build step (the "design tokens"
half of the blueprint item).

CLI:
    python3 integrations/webdev.py component Button --out <dir>
    python3 integrations/webdev.py tokens --out <dir>
    python3 integrations/webdev.py status
"""
import json
import re
import sys
from pathlib import Path

DEFAULT_TOKENS = {
    "color": {"bg": "#0b0d10", "fg": "#e8eaed", "accent": "#4f8cff",
              "muted": "#8a9099", "danger": "#ff5c5c"},
    "space": {"xs": "4px", "sm": "8px", "md": "16px", "lg": "24px", "xl": "40px"},
    "radius": {"sm": "4px", "md": "8px", "lg": "16px"},
    "font": {"sans": "system-ui, sans-serif", "mono": "ui-monospace, monospace"},
}


def _pascal(name: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[^a-zA-Z0-9]+", name) if p) or "Component"


def component(name: str) -> dict:
    comp = _pascal(name)
    tsx = (f"export interface {comp}Props {{\n"
           f"  label: string;\n  onClick?: () => void;\n}}\n\n"
           f"export function {comp}({{ label, onClick }}: {comp}Props) {{\n"
           f"  return (\n"
           f"    <button className=\"{name.lower()}\" onClick={{onClick}}>\n"
           f"      {{label}}\n"
           f"    </button>\n"
           f"  );\n}}\n")
    css = (f".{name.lower()} {{\n"
           f"  background: var(--color-accent);\n"
           f"  color: var(--color-fg);\n"
           f"  padding: var(--space-sm) var(--space-md);\n"
           f"  border-radius: var(--radius-md);\n"
           f"  border: none;\n  cursor: pointer;\n}}\n")
    return {f"{comp}.tsx": tsx, f"{comp}.css": css}


def tokens_css(tokens=None) -> str:
    tokens = tokens or DEFAULT_TOKENS
    lines = [":root {"]
    for group, vals in tokens.items():
        for k, v in vals.items():
            lines.append(f"  --{group}-{k}: {v};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def scaffold_component(name: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fname, content in component(name).items():
        (out_dir / fname).write_text(content)
        written.append(str(out_dir / fname))
    return {"scaffolded": _pascal(name), "files": written}


def scaffold_tokens(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "tokens.css").write_text(tokens_css())
    (out_dir / "tokens.json").write_text(json.dumps(DEFAULT_TOKENS, indent=2))
    return {"files": [str(out_dir / "tokens.css"), str(out_dir / "tokens.json")]}


def status():
    return {"generators": ["component (React/TSX + CSS)", "tokens (CSS vars + JSON)"],
            "toolchain_required": False,
            "note": "deterministic templating — drop output into any React/Next project"}


if __name__ == "__main__":
    args = sys.argv[1:]
    out = Path(".")
    if "--out" in args:
        i = args.index("--out")
        out = Path(args[i + 1])
        args = args[:i] + args[i + 2:]
    if args and args[0] == "component" and len(args) >= 2:
        print(json.dumps(scaffold_component(args[1], out), indent=2))
    elif args and args[0] == "tokens":
        print(json.dumps(scaffold_tokens(out), indent=2))
    elif args and args[0] == "status":
        print(json.dumps(status(), indent=2))
    else:
        print("usage: webdev.py component <Name> --out <dir> | tokens --out <dir> | status",
              file=sys.stderr)
        sys.exit(2)
