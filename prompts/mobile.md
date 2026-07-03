---
deliverable: mobile-app
route: "skills/webdev/SKILL.md with --stack react-native (ui-ux-pro-max ships RN/Expo guidance)"
---

# Intake — ask before building (one message, grouped)

**Required**
1. **What does the app do?** — one line, plus the 1-3 core screens.
2. **Who uses it** — and on what? (iOS / Android / both → default Expo/React Native)
3. **Product & industry** — one line for the design-system search.
4. **Data** — local-only, or needs a backend/API? (backend is its own deliverable — scope it separately, stub it here)
5. **Navigation** — tabs / stack / drawer, or "propose it".

**Optional**
6. Design direction — adjectives or reference apps.
7. Offline behavior, notifications, auth — needed in v1?
8. Ship target — Expo Go preview is the default deliverable; app-store builds are out of scope for a first pass (say so).

# Templates

**T1 — App blueprint**
> Act as a senior mobile product designer. Blueprint a [platform] app: [description]. Define screens with purpose, navigation model, state that must persist, and the design direction ([adjectives]). Optimize for first-session clarity — a new user must understand it in 30 seconds.

**T2 — Design system query (React Native)**
> python3 ~/.claude/skills/ui-ux-pro-max/scripts/search.py "[keywords]" --stack react-native

**T3 — Screen builder**
> Build the [screen] screen in React Native (Expo). Design system: [T2 output]. Navigation: [model]. Must handle: loading, empty, and error states — not just the happy path.

# Execution

1. **Blueprint** — T1; confirm screens + navigation before code.
2. **Design system** — T2 for RN-specific UX (list performance, navigation patterns, touch targets) + palette/typography.
3. **Scaffold** — Expo app, screen per T3, navigation wired, tokens from `integrations/webdev.py tokens` (JSON mirror works for RN styles).
4. **Verify** — it must start (`npx expo start` dry-check / bundle compiles). Never deliver code that doesn't build.
5. **Log** — Mnemos + ReasoningBank per Apollo §2.
6. **Deliver** — folder, run instructions (Expo Go QR flow), screen map, honest list of what's stubbed.
