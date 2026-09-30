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

- **Use for:** structural UI — inputs, dialogs, tables, cards, sidebars,
  pricing/hero blocks, charts, dashboards. ~1,178 registry items
  (verified 2026-09-30).
- **Find the slug** (don't guess — a wrong slug returns the site's HTML
  and the CLI fails):
  `curl -s https://registry.watermelon.sh/registry.json | python3 -c "import sys,json;[print(i['name'],'-',i.get('description','')[:70]) for i in json.load(sys.stdin)['items'] if '<term>' in i['name']]"`
- **Prefer `<name>-base`** variants — upstream labels them "theme-ready";
  they're the ones to re-token.
- **Install (verified live 2026-09-30):**
  `npx shadcn@latest add "https://registry.watermelon.sh/r/<name>.json"`
  — note the `/r/`. Lands in `components/watermelon/`. Needs a
  `components.json` (`npx shadcn@latest init`). Its `utils` dependency
  may rewrite `lib/utils.ts` to `export { cn } from "cn"` (shadcn's own
  `cn` package, drop-in for clsx+tailwind-merge — legit, but it's a diff:
  mention it). Non-interactive runs hang on the overwrite prompt; pass
  `--overwrite` only when `lib/utils.ts` is the stock `cn()`.
- **Deps vary per item** — check `dependencies` in the item JSON before
  installing. Across the registry: `motion` (390 items), `framer-motion`
  (75), plus icon libs `lucide-react`, `react-icons`, `@hugeicons/*`,
  `@tabler/icons-react`. MIT.
- **After install:** re-point colors at our tokens (step 2). Shipped
  defaults are Watermelon's palette — leaving them is an anti-slop fail.

## 2. motion-primitives — the motion layer

- **Use for:** text effects (text-effect, text-shimmer, text-morph),
  animated-group, in-view reveals, glow-effect, magnetic, carousel,
  morphing dialog. It animates things; it isn't a component kit.
- **Install (verified live 2026-09-30):**
  `npx motion-primitives@latest add <name>` → writes
  `components/motion-primitives/<name>.tsx` and installs `motion` itself.
  `npx motion-primitives@latest list` shows names. Needs `@/lib/utils`
  with `cn()` and the `@/*` path alias. CLI is v0.1.0, last published
  2025-03 — if it breaks, copy from https://motion-primitives.com/docs/<name>.
- **Status:** upstream says beta. Pin `motion` in package.json.
- **Every use still passes `animation-craft/SKILL.md`** — a registry
  component doesn't exempt it from the frequency/purpose/easing questions.
  Text-shimmer on a nav link seen 50×/day is still wrong.

### Bundle hygiene — say it, don't hide it
- **Motion:** motion-primitives and most Watermelon items import
  `motion/react`. ~75 Watermelon items still import `framer-motion` (same
  library, old name) → two copies in the bundle. Rewrite those imports to
  `motion/react` and drop framer-motion; if one breaks on the swap, keep
  both and note the cost in delivery.
- **Icons:** Watermelon items pull four different icon libraries. Pick one
  per project (default `lucide-react`, which motion-primitives also uses)
  and swap icons in installed components rather than shipping 3–4 icon
  packages.

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
