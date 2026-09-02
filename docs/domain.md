# Domain: how FortKnight thinks about time

## The fortnight
Life repeats on a **14-day cycle**. Each day has a **day key**: weekday plus a variant letter,
and the letter alternates *every day*, so the second week is the mirror of the first:

| index | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| key | sun-a | mon-b | tue-a | wed-b | thu-a | fri-b | sat-a | sun-b | mon-a | tue-b | wed-a | thu-b | fri-a | sat-b |
| week | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |

Labels: `sun-a` = "Sunday A" = `Sun_A` (the short form the workbook uses inside meal keys).

Each day has a **main focus** (week 1: A-days CLEANING, B-days WORKING; week 2: A-days
FLEXIBLE, B-days MEALS) and a focus per block (below).

## Blocks
Every day is cut into five blocks. Only the middle three carry a focus and hold activities;
the outer two are sleep/wind-down and only carry meal hints.

| block | time | duration | meal primary / secondary |
|---|---|---|---|
| too-early | 00:00–08:00 | 480 | leftovers-dessert / breakfast |
| early | 08:00–11:00 | 180 | breakfast / brunch |
| midday | 11:00–15:00 | 240 | brunch / snack |
| late | 15:00–18:00 | 180 | snack / dinner |
| too-late | 18:00–24:00 | 360 | dinner / leftovers-dessert |

The **focus-carrying window** is therefore 08:00–18:00 = 600 minutes/day = **8400 minutes per
fortnight**. Allocations and weights are expressed against that window.

**Appointment block** — the block held open for appointments: week 1 = `midday`, week 2 = `early`.

These five blocks are the *baseline* profile's. A questionnaire profile has 2–5 blocks of its own:
one **unscheduled** block (wind-down + sleep + wake-up, default 22:00–06:00), the complement of
that profile's answered waking window, plus 1–4 focus blocks — one per category that stands out in the
answers, cut around fixed activities (`docs/questionnaire.md`). Flexible blocks are open scope.

## Categories and subjects
Seven categories are the units everything is weighted in: `meals`, `cleaning`, `working`,
`spirituality-development`, `friends-family`, `health`, `operations`. **The set is closed** — a
category is a stone, and a fort chooses which stones it has, never what one is (the working set's
`docs/megaseed/categories.md`, 2026-09-02). Each has subjects (e.g. `laundry` → cleaning,
`pet-care` → friends-family); **subjects are open** — a fort's slabs list its own — and the 41 in
`data/categories.json` are the shipped default that the questionnaire and the baseline weights are
keyed on.
`flexible` is a pseudo-focus meaning "deliberately unassigned"; it is not a category. It is not a leftover
either: `flexibleShare` is the part of the waking window the seven categories did not claim (`docs/weights.md`
rule 3) — the fortnight's open time, where rest days, seasonal and occasional work, and anything not yet
scheduled live. A subject on the `section` cadence, and one marked "not often", declare nothing precisely so
that this time stays free for them.

## Seasons — the Norse wheel, flipped for Arizona
The year is five seasons. Each starts on a Sunday chosen by a **rule** (so any year can be
computed), each has a focus order (four categories, most important first), and each restarts
the fortnight on its own start day key. A start rule is a small structured object evaluated by
`fk_core/dates.py` `start_date_for_rule` (JavaScript twin `src/lib/shared/fortknight-rules.js`):
`{kind, …, offsetDays, snap}` — kinds `fixed-date` (month + day), `nth-weekday` (month + weekday +
occurrence 1–4 / −1 = last), `easter`, `solar` (equinox / solstice), `new-moon` (the Nth new moon of
the year), `manual` (dates typed per year in `knownStarts`); then `+ offsetDays`, then an optional
`snap` to a weekday on-or-after / on-or-before. The words live beside it in `startDescription`.
A person's own year split (`docs/questionnaire.md`, Rhythm Q2) becomes seasons of exactly this
shape, so their sections drive date → day-key resolution the same way.

| season | rough months | start rule | 2026 | starts on | mode |
|---|---|---|---|---|---|
| Ostara | Mar–Apr | 2nd Sunday of March (DST starts): `nth-weekday` 3 / sunday / 2 | 2026-03-08 | sun-b | outdoor |
| Fimbulsumar | Apr–Sep | Easter Sunday: `easter` | 2026-04-05 | sun-b | **indoor** |
| Spooky Season | Sep–Nov | Sunday before Labor Day: `nth-weekday` 9 / monday / 1, snap sunday on-or-before | 2026-09-06 | sun-a | mixed |
| Christmas | Nov–Jan | 1st Sunday of November (DST ends): `nth-weekday` 11 / sunday / 1 | 2026-11-01 | sun-a | outdoor |
| Hogmanay | Jan–Mar | first Sunday after Christmas: `fixed-date` 12/26, snap sunday on-or-after | 2026-12-27 | sun-a | outdoor |

The wheel has *outside-time* and *inside-time*. In the North the harsh season is winter; in
Arizona it is **Fimbulsumar** (the great summer), so the outdoor/indoor pattern is
flip-flopped. Each season carries an `outdoorWindow.uvAbove4` (start/end of the daily window when UV index
exceeds 4). It is the guide for outside-time vs inside-time on a given day of the season. The
workbook left these blank; fill them in as they are measured.

## Activities
One record per activity per day key per block — in the workbook example set (`examples/workbook/`)
and in a person's import document; the neutral canonical `data/` has none. Fields that matter:
- `priority` 1 (fixed, most important: church, piano lessons) … 5 (optional outings: zoo, mall).
- `flexibility` `no | some | yes | null` — can it move?
- `timing` for timed activities: `estimatedStart` → `travelPrepComplete` → `timeStart` →
  `timeFinished` → `estimatedEnd`, where **estimatedEnd = timeFinished + (travelPrepComplete − estimatedStart)**
  (the same prep/travel allowance is added back at the end). `durationMinutes` = finish − start,
  `prepMinutes` = travelPrepComplete − estimatedStart. Untimed routines (meal prep, cleaning,
  laundry, teaching) have `timing: null` and are scoped to their block.
- `detail` parses the free-text "Link/Tasks" column: `meal-prep` (meal references), `url`, or `text`.

## Meal keys and menus
A menu belongs to a season (menus live in a sample set or a person's import; the neutral `data/` has none). Each meal has a slot (`brunch | snack | dinner`) and a **meal key**
listing the day keys that share the dish: `sun-a+tue-a` (canonical form: kebab day keys sorted
in cycle order, joined by `+`; the workbook wrote `Sun_A+Tue_A`). Meal-prep activities point at
these same keys ("Snack Fri_A+Sun_A & Dinner Sun_B+Wed_A" → two `mealRefs`). Inverting the keys
gives the per-day menu (`build/derived/menuByDay.json`). A leading `*` in the workbook meant
"cook extra — leftovers become an ingredient later" → `cookExtra: true`.

## Weights (the north star)
A **weights** file says what share of the 8400-minute window each category should receive,
plus which blocks it prefers. The historical baseline weights are computed from the workbook example's
block-focus grid (`docs/weights.md`); the questionnaire produces the same shape from a person's answers.
