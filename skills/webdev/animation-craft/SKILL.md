---
name: hermes-webdev-animation-craft
description: "HERMES webdev sub-skill — motion/animation implementation craft. Invoked internally by skills/webdev/SKILL.md during section-building (step 4) and QA (step 5). Not Apollo-routed, not user-invocable. Encodes when to animate, easing/duration rules, spring vs. transition choice, transform-only performance discipline, and a mandatory Before/After/Why review table. Adapted from Emil Kowalski's public design-engineering skill (emilkowalski/skill) — canned marketing intro removed, frontmatter renamed to fit HERMES conventions. Attribution: https://emilkowal.ski/skill."
allowed-tools: Read
user-invocable: false
---

# webdev/animation-craft — motion implementation discipline

Called by `skills/webdev/SKILL.md`, never by Apollo directly. This is the
layer below design-system selection: `ui-ux-pro-max` / `frontend-design` /
`theme-factory` decide *what* the interface should look like; this skill
decides *how a specific motion should behave* once that's settled — easing,
duration, spring vs. transition, and what NOT to animate.

Source: adapted from Emil Kowalski's public skill (Sonner, Vaul author),
https://emilkowal.ski/skill. Per Invariant #4 this is vendored as rules and
attributed, not silently repackaged as HERMES's own research.

## When webdev calls this

- **Step 4 (Sections with real copy):** any interactive element (buttons,
  dropdowns, modals, toasts, drag/gesture surfaces) gets its animation
  decisions run through the framework below before code is written.
- **Step 5 (QA before delivering):** run the Review Checklist against the
  built sections. Report findings as a Before/After/Why table — never as a
  bulleted "Before: ... After: ..." list.

## Animation Decision Framework

Before writing any animation, answer in order:

**1. Should this animate at all?**

| Frequency | Decision |
|---|---|
| 100+ times/day (keyboard shortcuts, command palette toggle) | No animation. Ever. |
| Tens of times/day (hover, list navigation) | Remove or drastically reduce |
| Occasional (modals, drawers, toasts) | Standard animation |
| Rare/first-time (onboarding, empty-state delight) | Can add flourish |

Never animate keyboard-initiated actions — repeated hundreds of times a
day, animation makes them feel slow and disconnected.

**2. What's the purpose?** Valid answers: spatial consistency (toast enters/
exits from the same direction it swipes), state indication, explanation,
feedback (press feedback confirms the interface heard the user), or
preventing a jarring appear/disappear. "It looks cool" is not a valid
answer for anything seen often.

**3. Easing** — entering/exiting → `ease-out`. Moving/morphing on-screen →
`ease-in-out`. Hover/color change → `ease`. Constant motion (marquee,
progress) → `linear`. Default → `ease-out`. **Never `ease-in`** on UI —
it delays the initial movement, which is the moment the user is watching
most closely, and makes the same duration feel slower.

Use custom curves, not bare CSS easings — they're too weak to feel
intentional:

```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1); /* iOS-like, from Ionic */
```

**4. Duration** — button press: 100-160ms. Tooltips/small popovers:
125-200ms. Dropdowns/selects: 150-250ms. Modals/drawers: 200-500ms.
Marketing/explanatory: can run longer. **Stay under 300ms for UI.** A
faster spinner and a shorter dropdown both read as "more responsive" at
identical actual load time — perceived performance is part of the spec,
not a nice-to-have.

## Springs vs. transitions

Use springs (`useSpring`, or `{ type: "spring", duration, bounce }`) for:
drag with momentum, "alive" elements (Dynamic-Island-style), interruptible
gestures, decorative mouse-tracking. Springs retain velocity when
interrupted; CSS keyframes restart from zero — this is why springs are the
right call for anything the user might change mid-motion. Keep bounce
0.1–0.3; avoid it in dashboards and data-dense product UI.

Use CSS **transitions**, not keyframes, for anything triggered rapidly
(toasts stacking, toggles). Transitions retarget smoothly mid-flight;
keyframes snap back to zero.

## Component rules (apply during step 4)

- **Press feedback:** `transform: scale(0.97)` on `:active`, 160ms
  `ease-out`. Every pressable element, not just buttons.
- **Never animate entry from `scale(0)`.** Nothing in the real world
  appears from nothing. Start at `scale(0.9–0.95)` + `opacity: 0`.
- **Popovers scale from their trigger**, not from center
  (`transform-origin: var(--radix-popover-content-transform-origin)` or
  equivalent). **Modals are the exception** — no trigger anchor, keep
  `transform-origin: center`.
- **Tooltips:** delay before the first one opens (prevents accidental
  activation); once one tooltip is open, adjacent tooltips open instantly,
  no delay, no animation.
- **Gesture dismissal:** don't gate on distance alone — compute velocity
  (`Math.abs(dragDistance) / elapsedTime`); dismiss if velocity > ~0.11
  even if the drag distance was short. Apply damping past natural drag
  boundaries instead of a hard stop. Capture pointer events once dragging
  starts; ignore additional touch points after drag begins.
- **Stagger** list/grid entrances 30–80ms apart — longer reads as slow,
  simultaneous reads as un-crafted. Never block interaction on stagger.
- **Asymmetric timing:** slow where the user is deciding (hold-to-delete:
  2s linear), fast where the system responds (release: 200ms ease-out).
- **Crossfades that look "off"** despite correct easing/duration: add
  `filter: blur(2px)` during the transition (cap ~20px, expensive in
  Safari) — it hides the moment of two overlapping states.

## Performance (non-negotiable)

- **Animate only `transform` and `opacity`.** They skip layout and paint.
  `padding`/`margin`/`height`/`width` animations trigger full layout —
  reject these in review.
- **Don't drive per-frame values through CSS custom properties on a
  parent** — that recalculates style for every child. Set `transform`
  directly on the animating element instead.
- **Framer Motion / Motion's `x`/`y`/`scale` shorthand is NOT
  hardware-accelerated** — it runs on the main thread via
  `requestAnimationFrame` and drops frames under load. Use the full
  `transform` string (`animate={{ transform: "translateX(100px)" }}`) for
  anything that must stay smooth while the page is busy loading/painting.
- Prefer CSS transitions/animations for predetermined motion (off main
  thread, survives page-load jank); use JS only for dynamic/interruptible
  motion.

## Accessibility (non-negotiable)

```css
@media (prefers-reduced-motion: reduce) {
  .element { animation: fade 0.2s ease; /* opacity/color only, no transform */ }
}
```

Reduced motion means less and gentler, not zero — keep opacity/color
transitions that aid comprehension, drop movement/position animation.

```css
@media (hover: hover) and (pointer: fine) {
  .element:hover { transform: scale(1.05); }
}
```

Gate all hover animation behind this query — touch devices fire `:hover`
on tap and will otherwise show false-positive animation.

## Review Format (mandatory during step 5 QA)

Report findings as a markdown table, one row per issue — never a
"Before: / After:" list:

| Before | After | Why |
| --- | --- | --- |
| `transition: all 300ms` | `transition: transform 200ms ease-out` | Specify exact properties; `all` animates layout properties too |
| `transform: scale(0)` entry | `transform: scale(0.95); opacity: 0` | Nothing disappears/reappears from nothing |
| `ease-in` on dropdown | `ease-out` or custom curve | `ease-in` delays the moment the user is watching most |
| No `:active` state | `transform: scale(0.97)` on `:active` | Pressable elements must confirm the press |
| `transform-origin: center` on popover | Trigger-anchored origin (modals exempt) | Popovers should scale from where they were summoned |

## Review Checklist

| Issue | Fix |
|---|---|
| `transition: all` | Specify exact properties |
| `scale(0)` entry | `scale(0.95)` + `opacity: 0` |
| `ease-in` on UI element | `ease-out` or custom curve |
| `transform-origin: center` on popover | Trigger location (modals exempt) |
| Animation on keyboard-triggered action | Remove entirely |
| Duration > 300ms on UI element | Reduce to 150–250ms |
| Hover animation, no media query | Add `@media (hover: hover) and (pointer: fine)` |
| Keyframes on rapidly-triggered element | Switch to CSS transitions |
| Framer/Motion `x`/`y` under load | Use full `transform` string |
| Same enter/exit speed | Exit faster than enter |
| All list items appear at once | Stagger 30–80ms |

## Honest limits

- This skill governs motion craft only. It does not choose the design
  system, palette, or component library — that's `ui-ux-pro-max` /
  `frontend-design` / `theme-factory`, run first.
- Dashboards and data-dense product UI should default to less motion than
  the durations above suggest as a ceiling, not a target — when in doubt,
  faster and quieter beats "polished."
- If a project's stack lacks CSS `@starting-style` support, fall back to
  the `data-mounted` attribute + `useEffect` pattern rather than skipping
  enter animation.
