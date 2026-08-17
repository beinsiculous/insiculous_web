# Weights — the questionnaire contract

**Goal:** a questionnaire the user fills out produces a `weights` JSON that says how the
fortnight should be apportioned across the seven categories. The generator (`docs/generator.md`) turns
weights into a concrete schedule; today the baseline weights (`examples/workbook/weights.baseline.json`)
describe the workbook sample schedule, and a person's weights carry the block focus grid they *imported*
(applied on the Assistant page), restricted to their own blocks; that is what `/fortknight/` renders.

## Shape (`data/schema/weights.schema.json`)
```json
{
  "schemaVersion": 1,
  "id": "baseline",
  "source": "baseline | questionnaire | manual",
  "cycleLengthDays": 14,
  "wakingWindow": {"start": "08:00", "end": "18:00", "minutesPerDay": 600, "minutesPerCycle": 8400},
  "categories": {
    "meals":    {"share": 0.2357, "minutesPerCycle": 1980, "preferredBlocks": ["early", "late", "midday"]},
    "cleaning": {"share": 0.2357, "minutesPerCycle": 1980, "preferredBlocks": ["late", "midday"]},
    "...": {}
  },
  "subjects": {"laundry": {"minutesPerDay": {"min": 15, "max": 60}, "peripheral": false, "goal": false, "currentMinutesPerDay": null}, "...": {}},
  "flexibleShare": 0,
  "unscheduledBlock": {"start": "22:00", "end": "06:00", "minutes": 480},
  "blocks": [{"key": "unscheduled", "start": "22:00", "end": "06:00", "durationMinutes": 480, "carriesFocus": false},
             {"key": "early", "start": "06:00", "end": "14:00", "durationMinutes": 480, "carriesFocus": true}, {"...": {}}],
  "blockSplit": {"standoutCategories": ["working", "spirituality-development"], "focusBlockCount": 3, "agendaScope": "categories", "anchors": [], "warnings": []},
  "agendaScope": "categories",
  "blockFocusGrid": {"sun-a": {"early": "meals", "midday": "spirituality-development", "late": "cleaning"}, "...": {}},
  "appointmentBlocks": {"sun-a": "midday", "...": "..."},
  "questionnaire": {"version": 1, "answeredAt": "2026-08-15", "answers": {}},
  "notes": []
}
```
- `share` — fraction of the `wakingWindow` (baseline: early+midday+late = 8400 min per fortnight; questionnaire profiles: the answered waking window, e.g. 13440). Category shares + `flexibleShare` sum to 1 (`flexibleShare` is the workbook's flexible focus blocks in the baseline; for questionnaire profiles it is not an input, only the rounding remainder).
- `preferredBlocks` — blocks ordered by how much of the category's time they carry (a hint for a generator); keys must be focus blocks of this file's `blocks` (baseline: early/midday/late).
- `blockFocusGrid` — optional; when present it is a fully-resolved answer (a focus per day and focus block) rather than only proportions. Baseline: the workbook's 14 × early/midday/late cells. Questionnaire profiles: the person's own grid (`answers.blockFocusGrid` — a proposal they adopted on `/fortknight/`) or else the applied import document's grid, restricted to the profile's focus blocks (`{}` when neither exists; unmatched block keys are reported in `blockSplit.warnings`), plus `appointmentBlocks` `{dayKey: blockKey}` from the import.
- `meals` — `{perDay, meals[{name, slots[], needsPrepped, needsCooked, prepMinutes, cookMinutes}]}` (the questionnaire's meals, defaults filled); `mealPlan` — `{items[{id, meal (name slug), dish, days[1–2], notes}]}`, the ForkKnife menu (`docs/meal-plan.md`).
- `proposal` — the generator's proposal for this profile (`docs/generator.md`): `{blockFocusGrid, seasonId, reasons{dayKey: {block: why}}, warnings[], diff{changes[], counts{same, changed, added, removed}}, activities[], placedMinutes{subjectId: {target, placed}}}` — `activities` and `placedMinutes` are optional (absent on files derived before the activities half shipped; the app re-derives such a profile instead of using it as saved) and are the sessions / practices / meals proposed inside the proposed grid's cells (`{id, title, kind, dayKey, block, priority, categories, subjectId, timing|null, minutes, reason, source: "proposed"}`) — made from the fields above for the season the file was derived for (`seasonId`; `null` when none), `diff` against `blockFocusGrid`. Stored at derivation time (Questionnaire save, adopt/drop on the Overview, apply on an Assistant page) — so a downloaded weights file or the assistant workspace carries the proposal for the season of *that* day; the Overview recomputes it live for the resolver's date, and a consumer of the file that wants today's should do the same (`scripts/generate_grid.py`).
- Questionnaire-only fields (all optional, so the baseline still validates): per category
  `wantMore` (derived: a subject of the category is a goal), `sentiment` (`struggle | neutral | enjoy`), `delegable`, `essential`; top-level
  `subjects` (per-subject minutes-per-day range + `peripheral` + `goal`/`currentMinutesPerDay`), `unscheduledBlock`, `blocks`
  (this profile's 2–5 block day), `blockSplit` (why; `agendaScope`; anchors carry `source`: `import` for the applied import's fixed activities, `standing-appointment`), `agendaScope` (`subjects | categories`), `meals`, `yearSplit`
  (sections with `start.rule` / `startVariant` / `knownStarts` — the person's own seasons, `docs/questionnaire.md`
  "Section start rules"), `weekStart` (the weekday the person's week and fortnight start on, default `sunday`),
  `standingAppointments`, `appointmentWeekdays`, `practices`, the agenda context an assistant or
  generator reads but shares ignore — `restDays` (weekday ids), `energyPeak`
  (`morning | midday | evening | varies`), `context` (free text) — and `questionnaire` (the raw
  answers the file was derived from). See `docs/questionnaire.md`.

## How the baseline was computed (`scripts/analyze_allocations.py --overlay examples/workbook`)
Two views, both in `build/derived/allocations.json` (all flexible / zero on the neutral canonical data —
the app computes a person's own from their weights with `app/shared/allocations-rules.js`):
1. **byBlockFocus** — each early/midday/late block gives its full duration to its focus. This is the *intent* of the schedule and is what the baseline weights export.
2. **byActivities** — timed activities count `durationMinutes + prepMinutes`; untimed activities split the block's remaining minutes evenly; multi-category activities split evenly. This is what is *actually written down* and is useful for spotting gaps (e.g. "working" has focus time but no activities).

Both roll up `byCategory`, `byDay`, `byBlock`, `byCategoryAndBlock` and give `shareByCategory`.

## How the questionnaire maps onto this
`docs/questionnaire.md` holds the questions and the mapping table. In short: per-subject
minutes-per-day ranges (midpoints, peripheral subjects count 0) sum into category raw minutes,
`wantMore` multiplies, and category shares split the waking window proportionally (no flexible reserve);
the answered waking window sets the scope (its complement is the unscheduled block) and the standout categories + fixed activities set
the profile's block split; sentiment / delegable / essential flags pass through for the generator. The rule lives in
`fk_core/weights.py` and its JavaScript twin `app/shared/weights-rules.js`; the CLI is
`scripts/questionnaire_to_weights.py`, the UI is `/fortknight/questionnaire/` in the Astro app (the questionnaire is FortKnight's settings; ForkKnife's meals + preferences on `/forkknife/questionnaire/`). Output
validates against `weights.schema.json`, and `validate.py` also checks every `data/weights.*.json`
for known category/subject keys, `preferredBlocks` that exist in the profile's blocks, block
durations that add up to a day, shares that add up to 1, and a sane essential count.
