# Workbook → JSON mapping (the `examples/workbook/` sample set)

`source/FortKnight.xlsx` (7 sheets) was imported once by `scripts/xlsx_to_json.py`. The result is the
**workbook example set** under `examples/workbook/` (activities, the days grid, the Spooky Season menu,
the baseline weights), laid over the person-neutral `data/` with `--overlay examples/workbook`; the shared
vocabulary files it produced (seasons, blocks, categories, meta) live in `data/`. Every record keeps `raw`
(all cells, keyed by header) and `sourceRow`. The owner's own copy of this schedule, as an import document,
is `source/import.my-activities.json`.

| sheet | column | JSON |
|---|---|---|
| Seasons | Season | `seasons[].name`, `id = slug` |
| | Georgian Equivalent | `gregorianRange` (sic — Gregorian) |
| | Duration | `durationWeeks{min,max}` |
| | Season Start - Sunday | `startRule` (structured: `nth-weekday` 3/sunday/2, `easter`, `nth-weekday` 9/monday/1 + snap sunday on-or-before, `nth-weekday` 11/sunday/1, `fixed-date` 12/26 + snap sunday on-or-after) + `startDescription` (the words) |
| | 2026 (serial date) | ignored — recomputed into `knownStarts["2026"]` from the rule |
| | 2026 Start Day | `startDayKey` |
| | Hours UV > 4 | `outdoorWindow.uvAbove4` (empty → `null`) — the daily UV>4 window, the guide for outside time |
| | Main/Secondary/Tertiary/Quaternary Focus | `focus[]` (category keys, in order) |
| Days | Day Key | `days{dayKey}` with `label`, `shortKey`, `index`, `week` |
| | Main Focus | `mainFocus` (+ `mainFocusLabel` raw) |
| | Early/Midday/Late Block's Focus | `blockFocus{early,midday,late}` (+ labels) |
| | Appointment Block | empty in sheet → filled by rule: week 1 `midday`, week 2 `early` |
| Blocks | Block Description / Start / End | `blocks{key}.label/start/end` (`MIDNIGHT` → `00:00`/`24:00`) |
| | Meal Primary / Secondary | `mealPrimary`, `mealSecondary` |
| Schedule | Description | `activities[].title` |
| | Priority | `priority` (int) |
| | Day Key / Block | `dayKey`, `block` |
| | Estimated Start, Travel/Prep Complete, Time Start, Time Finished, Estimated End | `timing.*` as `HH:MM`; `estimatedEndSource` = `formula` when the cell held `=J+(H-D)`, `literal` otherwise |
| | Flexibility | `flexibility` lower-cased (`null` when blank/"null") |
| | Category | `categories[]` (`Operations/Health` → two keys) |
| | Link/Tasks | `detail{raw, kind, mealRefs|url|text}` |
| Menu | (all) | not imported — it is a formula view of Spooky Season; was rebuilt as `derived/menuByDay.json` and checked by `tests/test_build.py`, both removed 2026-08-30 with the creation chain |
| Subjects | Subjects / Category | `subjects{key}`, `categories{key}.subjects[]` |
| Spooky Season | # / Meal / Meal Key / Menu | `menus/spooky-season.json` `meals[]` (`number`, `slot`, `mealKey`, `menu`, `cookExtra` from leading `*`) |

## Known quirks (and what was done)
- Ostara's 2026 serial (46086 = 2026-03-05, a Thursday) is a typo; the rule (2nd Sunday of March = 2026-03-08) is correct and is what `knownStarts` records.
- Meal keys with trailing tabs (`Wed_B\t`, `Fri_B+Sun_B\t`, `Mon_A\t`, `Tue_A+Thu_A\t`) → whitespace stripped, days sorted into cycle order.
- `Estimated End` is a literal (not the formula) in rows 3, 10, 13, 41, 47 → `estimatedEndSource: "literal"`.
- "Open for Appointments" on Tuesday A sits in `early`, but week 1's appointment block is `midday` → validate.py emits a warning (kept as-is; decide later).
- Friday A "Date Night Babysitter" is filed under `late` but runs 18:00–21:30 (into `too-late`) — timed activities are not clipped to their block.
- Sheet "Menu" cell for Wednesday B brunch is `FLEXIBLE`; Saturday B / Monday B dinner is `FLEXIBLE` — kept verbatim.
