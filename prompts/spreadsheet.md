---
deliverable: spreadsheet
route: "xlsx skill (~/.claude/skills/xlsx)"
---

# Intake — ask before building (one message, grouped)

**Required**
1. **Purpose** — what will this workbook do? (budget / tracker / dataset / financial model / dashboard / comparison)
2. **Data** — where does the data come from? (user provides, HERMES generates structure only, extract from files, research)
3. **Columns/fields** — what must each row capture? (or "propose a schema for me")
4. **Calculations** — totals, formulas, pivots, conditional formatting, charts?

**Optional**
5. Multiple sheets? What splits them?
6. Who else uses it — needs headers/docs/data-validation for non-experts?
7. Update cadence — one-off snapshot or a living document (then formulas > hardcoded values)?

# Templates

**T1 — Schema designer**
> Design a spreadsheet schema for [purpose]. Propose sheets, columns with types and validation rules, and the formulas/summary cells needed. Optimize for [one-off | ongoing] use by [user profile].

**T2 — Formula builder**
> For a sheet with columns [schema], write the exact formulas for: [calculations]. Use structured, copy-safe references and explain each in one line.

# Execution

1. **Schema** — T1; confirm with user before filling.
2. **Build** — invoke `xlsx` skill with schema + data + T2 formulas. Verify file exists.
3. **Log** — Mnemos + ReasoningBank per Apollo §2.
4. **Deliver** — path + what each sheet contains + any formula the user should know about.
