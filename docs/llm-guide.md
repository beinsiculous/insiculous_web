# Guide for assistants working on FortKnight data

You are editing a person's real schedule. Be precise and conservative.

1. **Only edit `data/`.** Never `build/` (generated) or `source/` (archive).
2. **Keep `raw`.** When changing a structured field, leave `raw` and `sourceRow` untouched; if the change is new information, add it to the structured fields only.
3. **Use canonical keys** — day keys `sun-a…sat-b`, block keys, category keys, `HH:MM` times. Never invent a new key without also updating `fk_core/keys.py`, the schema, and `docs/data-model.md`.
4. **Ids are immutable.** New activity → new id (`slug(title)--dayKey--block`).
5. **After every change:** `python3 scripts/validate.py` then `python3 scripts/build.py`. Report warnings to the user; do not silence them.
6. **Explain in domain terms** — "moved Laundry from Monday B early to midday (week 2 appointment block is early)" — and cite `docs/domain.md` when a rule applies.
7. **Menus** (when a person carries them, in a menu file or their import document's `meals`): every day needs exactly one brunch, snack, dinner. When you move a dish, update the meal key *and* any meal-prep `mealRefs` that pointed at it.
8. **Weights:** treat `weights.*.json` as the contract; propose schedule changes as changes to weights first when the user is talking about balance ("more family time"), and as activity edits when they are talking about specifics ("piano moved to 4pm").
9. **There are no credentials.** FortKnight holds no API keys and calls no provider; never ask for keys. What you were given is one person's private schedule — keep it inside their workspace.

## Replying from an assistant workspace
When the person gave you the workspace file set (`docs/assistant-workspace.md`), answer in plain
prose and, whenever you propose a change they should apply, add **exactly one** fenced JSON document
of one of these kinds — the app's *Apply from assistant* box takes it:
- **Weights file** (`weights.schema.json`) — for balance ("more family time"): start from their
  `weights.<id>.json` (their active profile), change `questionnaire.answers` (see `questionnaire.md`
  → Answers file), keep `id` as it is — the app applies the file to the profile of that id (a new id
  creates a new profile). The app re-derives the shares and blocks from the answers on the device,
  so editing `categories.*.share` alone changes nothing — change the answers.
- **Meal-plan document** (`meal-plan.schema.json`, `meal-plan.md`) — for their menu: `kind: "meal-plan"`,
  `items` of `{meal (their meal's name), dish, days: [first serving, leftovers day?]}` — day keys or names;
  the leftovers day is never the next day and at most three days later (the fortnight wraps).
- **Import document** (`import.schema.json`, `importers.md`) — for the commitments they describe or
  show you (text, a photo of a planner, a calendar export, their Google Calendar): `schemaVersion: 2`,
  `source.kind`, then **one readable record per commitment** (`title`, `repeats` in words such as
  "every week" / "monthly on the 2nd tuesday" / "once on 2026-10-14", `weekdays`, `start` "2:00 PM",
  `lasts` "1 h 30 min", `category`, `from`), untimed chores under `tasks` (with a `when` word),
  **everything you saw and left out under `skipped` with the reason**, and a `review` summary
  (what you scanned, counts found/imported/skipped, every guess). Unknown durations default to
  60 minutes, unknown categories to `health` — say so in `review`. The person will read this JSON
  to check their list is right and complete before applying it: write it for them. Given a
  spreadsheet (or a calendar export), follow `import-from-spreadsheet.md` step by step.
- **User-settings file** (`user-settings.schema.json`) — only for device extras such as the cycle
  anchor (`epochOverride`); `schemaVersion: 3`. Weights inside it are re-derived from its answers.
Never emit more than one document per reply, and say in prose what applying it will change.

## Building the person an agenda
When they ask you to draft their fortnight (not just rebalance it), the answer is an **import
document** too — `schemaVersion: 2`, `source.kind: "other"` and a `source.description` saying it is
your draft, carrying the machine sections beside (or instead of) the readable lists:
- `blockFocusGrid`: one focus (a category key or `flexible`) per day key and per focus block, using
  exactly the block keys in their `weights.<id>.json` → `blocks` (their day may have 1–4 focus
  blocks, not the workbook's three). Read the shares and `standoutCategories` for how often each
  category should lead; the person's `restDays`, `energyPeak` (demanding categories in the sharp
  block, light ones elsewhere), `sentiment` (struggles early in the waking window, enjoyed things as
  the reward after), `essential`/`delegable`, `appointmentWeekdays`, `standingAppointments`,
  `meals` slots and their free-text `context` for where. Alternate what should alternate between
  week A (`*-a` day keys) and week B (`*-b`); `upcomingDates` in `fortknight-data.json` tells you
  which real dates each day key falls on.
- `flexible` cells and the periodic backlog: a cell whose focus is `flexible` is open on purpose, not a gap
  you should fill with more of the daily rhythm. Its time is what `flexibleShare` reserves — rest days,
  catching up, staying free for an appointment, and the work that does not happen every day. That backlog is
  in `weights.<id>.json` → `subjects`: an entry with `everyday: false` and `cadence: "section"` happens on
  `daysPerPeriod` days of each section of their year, and one with `peripheral: true` is rarer still. Both
  declare no daily minutes on purpose, so neither shows in any category's share — read their
  `specificDaysNote` and `notOftenNote` (the person's own words: "Every other weekend", "When it breaks") and
  put them in flexible cells, in the section they belong to. A subject with `cadence: "fortnight"` is
  different: it *is* in the shares, on `daysPerPeriod` of the fortnight's fourteen days, so place it on that
  many days rather than every day.
- `fixedActivities`: only timed things that must anchor a day (work or school hours, a lesson) —
  activity shape from `data-model.md`, `priority: 1` or `flexibility: "no"`; everything else is
  focus, not a fixed activity.
- `notes`: every assumption you made, one line each.
Balance ("more family time") still goes through the weights file; the agenda goes through the import
document, and applying it replaces the previously applied one.
