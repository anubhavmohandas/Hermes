# webdev/component-sources — where UI pieces come from

Called by `skills/webdev/SKILL.md` steps 3–4. Decides, per section, whether
a component is **installed from a registry**, **generated as an asset**, or
**hand-built**. Hand-built is the fallback, not the default — a maintained,
MIT-licensed registry component beats a freehand one on edge states.

Sources are installed into the *user's project* via their own CLI (not
vendored into HERMES), so Invariant #4 (no copied code in HERMES) holds.

## Stack gate — check first

| Stack from intake | Watermelon UI | motion-primitives | Haikei-style SVG |
|---|---|---|---|
| React / Next.js + Tailwind v4 | yes | yes | yes |
| React without Tailwind | no — say so, hand-build | no | yes |
| Plain HTML/CSS/JS | no | no (use CSS per animation-craft) | yes |
| React Native / Expo | no (web-only DOM) | no | yes (react-native-svg) |

Both registries assume `cn()` in `lib/utils.ts` (clsx + tailwind-merge) —
`npx shadcn@latest init` creates it. Don't hand-roll a second one.

## 1. Watermelon UI — base components, blocks, dashboards

- **Use for:** structural UI — inputs, dialogs, tables, sidebars, tabs,
  charts (Recharts), and full-page blocks/dashboards. 260+ components.
- **Install (per component):**
  `npx shadcn@latest add "https://registry.watermelon.sh/<name>.json"`
  — name = the slug on https://ui.watermelon.sh. Check the slug on the
  site before running; don't guess (a 404 JSON fails the CLI).
- **Deps it pulls:** Radix UI, framer-motion, Recharts, Tailwind v4,
  React 18+ (19 recommended). MIT.
- **After install:** re-point its colors at our tokens (step 2) — shipped
  defaults are Watermelon's palette, not the project's. Leaving them is an
  anti-slop fail in step 5.

## 2. motion-primitives — the motion layer

- **Use for:** text effects (text-effect, text-shimmer, text-morph),
  animated-group, in-view reveals, glow-effect, magnetic, carousel,
  dialog/morphing transitions. It animates things; it isn't a component kit.
- **Install:** prerequisites `npm i motion lucide-react` + `cn()`. Then
  copy the component from its docs page (https://motion-primitives.com/docs/<name>)
  into `components/motion-primitives/`. A CLI (`npx motion-primitives@latest add <name>`)
  exists on npm — unverified by HERMES; if it errors, fall back to
  copy-from-docs, don't debug the CLI.
- **Status:** upstream says beta — APIs shift. Pin `motion` version in
  package.json.
- **Every use still passes `animation-craft/SKILL.md`** — a registry
  component doesn't exempt it from the frequency/purpose/easing questions.
  Text-shimmer on a nav link seen 50×/day is still wrong.

### Dependency conflict — say it, don't hide it
Watermelon imports `framer-motion`; motion-primitives imports `motion`
(`motion/react`). Same library, renamed. Mixing both = two copies in the
bundle. Default: rewrite Watermelon's `from "framer-motion"` imports to
`from "motion/react"` after install and drop framer-motion. If a component
breaks on that swap, keep both and note the bundle cost in delivery.

## 3. Haikei-style backgrounds — SVG assets

Haikei (haikei.app) is GUI-only — no API, no CLI. HERMES can't call it.
Code-side equivalent: `integrations/svg_bg.py`, same shape families,
seeded + token-driven.

```
python3 integrations/svg_bg.py list
python3 integrations/svg_bg.py layered-waves --w 1440 --h 320 --seed 7 \
    --colors "<bg>,<accent>,<accent2>" --layers 4 --out public/bg/hero-waves.svg
```
kinds: `waves`, `layered-waves`, `peaks`, `blob`, `blob-scene`,
`blurry-gradient`, `circles`. No `--colors` → reads `./tokens.json`.

- **Use for:** section dividers (waves/peaks), hero backdrops
  (blurry-gradient, blob-scene), empty-state art (blob).
- **Rules:** `aria-hidden` (already emitted), served as a file/`<img>` or
  CSS `background-image`, never inline 50KB of path data in JSX. Record the
  seed in a comment next to usage so it's reproducible.
- **Anti-slop:** a purple-blue blurry gradient behind a centered hero is
  *the* generic-AI tell (step 5 checklist). Use backgrounds when the scene
  sentence (step 1) calls for them, in the project's palette.
- If the user wants a hand-tuned Haikei export, they export from
  haikei.app and drop it in `public/bg/` — note which files were manual.

## Decision order per section

1. Is there a Watermelon block/component that fits the section's job? →
   install, re-token.
2. Does it need motion? → animation-craft decides *if*; motion-primitives
   supplies *how* if a primitive fits, else hand-write with `motion`.
3. Does it need decorative background/divider? → `svg_bg.py`.
4. Nothing fits → hand-build with tokens (existing step 3/4 path).

Log which source each section used in the delivery notes ("Hero: WM
`hero-01` + MP `text-effect` + svg_bg blurry-gradient seed 12").
