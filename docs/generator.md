# The generator: weights → a proposed block focus grid, and activities inside it

Roadmap 2. A pure, deterministic rule that reads a finished weights file and proposes (a) a focus for every
(day key × focus block) cell — the `blockFocusGrid` FortKnight's Overview shows — so that the minutes each
category gets track its share, with the person's fixed activities, rest days, preferred blocks, energy peak
and the current season's focus honoured; and (b) the activities inside those cells: subject sessions sized
from the Focus-1 hours, one short daily activity per practice, one activity per meal at its slot (see
"Activities inside the cells" below). The rule lives in `scripts/fk_core/generator.py` and its exact port
`src/lib/shared/generator-rules.js` (`tests/test_generator.py` runs both on the same fixtures).

## Where it shows up
- **`weights.proposal`** — every weights file derived from answers carries the proposal (`docs/weights.md`):
  `{blockFocusGrid, seasonId, reasons, warnings, diff, activities, placedMinutes}`. `diff` compares it with the file's own `blockFocusGrid`
  (`changes[{dayKey, block, imported, proposed}]`, `counts{same, changed, added, removed}`). The assistant
  workspace therefore sees it — as of the day the profile was last derived (`seasonId` says which season);
  the app's pages recompute it live for the current date.
- **`/fortknight/` (Overview)** — *Your grid* / *Proposed grid* switch. The proposal is recomputed on the page for the
  season of the date in the resolver (so it never lags the stored one); cells that differ are outlined and
  carry their reason as a tooltip; *Why each cell* lists every reason and warning. **Use this grid** adopts it:
  the grid is written to `answers.blockFocusGrid` (the person's own grid, which wins over the applied import's —
  the import stays as it was), the profile is re-derived and saved; **Drop your grid** removes it again.
- **`/fortknight/` (Overview), below the grid** — a *Proposed grid* bar next to *Weights* and *Focus grid* (same date as the grid).
- **`/fortknight/questionnaire/`** — Save keeps an adopted grid (it rides with the answers, not with the form); applying a
  new import on an Assistant page says so when an adopted grid still wins over the import's grid.
- **`/fortknight/days/<dayKey>/`** — the proposed activities of that day, generated live for the person's own grid (or for
  the proposed grid when they have none — the note says which), listed in their blocks after the person's own
  items with a ` · proposed` suffix and their reason; the *Show proposed activities* checkbox hides them
  (remembered for the session).
- **`scripts/generate_grid.py WEIGHTS [--date] [--answers] [--overlay] [--table]`** — the same proposal from the
  CLI; `scripts/questionnaire_to_weights.py --date` picks the season the stored proposal is made for.

## Inputs (all from the weights file)
`blocks` (the focus blocks, in order; a thin file without `blocks` — the workbook baseline — falls back to the
data set's `blocks.json`), `wakingWindow.start`, `categories[*].share / preferredBlocks / sentiment`,
`flexibleShare`, `blockSplit.anchors` (imported fixed activities + standing appointments, with their `block`),
`restDays`, `energyPeak`, plus the caller's **season focus** list — the current season's `focus[]` from
`data/seasons.json` (a person's own year-split sections carry none yet, so for them the season term is 0).
`appointmentBlocks` are deliberately **not** an input: the workbook shows the appointment block does not
dictate a focus (week-1 midday is the appointment block and carries spirituality / cleaning).

## The rule
1. **Targets in minutes.** `total = Σ focus block durations × 14`; `target[c] = share × total`;
   `target[flexible] = flexibleShare × total`. Cells are unequal (the workbook's 180/240/180, a profile's cuts
   wherever they fell), so no cell counting — sequential apportionment by minutes.
2. **Pass 1 — pins**, in cell order (day-key order × block order): a `restDays` weekday → every cell
   `flexible` (*rest day*); otherwise the anchors on that day key that fall in a focus block are measured
   against the block (offsets from the waking window's start, so blocks and anchors that wrap midnight measure
   alike); if one category's anchors cover ≥ `anchorPinCoverage` (0.5) of the block the cell is pinned to it
   (*anchor: <ids> covers NN%*). Pooled anchors (no day key) and unscheduled-block anchors never pin.
3. **Pass 2 — fill** the remaining cells in the same order. For a cell of `m` minutes, candidates are the
   seven categories then `flexible`; a candidate is **eligible** while `target > 0` and
   `delivered + m ≤ target + overshootSlackCells × m` (0.5 → no category ends more than half a cell over
   its share, so every share lands within one cell). Score =
   `(target − delivered − m) / target` (relative deficit after taking the cell)
   `+ preferredBlockWeight × (n − i)/n` when the block is the i-th of the category's `n` `preferredBlocks`
   `+ energyPeakWeight` when the category is a *struggle* and this is the energy-peak block
   (`energyPeakBlock`: morning → first, midday → middle, evening → last, varies → none)
   `+ seasonFocusWeight × (k − j)/k` when the category is the j-th of the season's `k` focus entries
   `− alternationWeight` when the same block on the other variant of this weekday (`sun-a` ↔ `sun-b`) already
   carries it. Highest score wins; ties keep candidate order. When nobody is eligible the largest absolute
   deficit takes the cell (*over share*).
4. **Reasons.** One short line per cell: `rest day` | `anchor: <id> covers NN%` |
   `behind share (delivered/target min)` | `over share`, followed by the tags that fired — `preferred block`,
   `energy peak`, `season focus #j`, `alternates with <dayKey>` — joined by `; `.
5. **Warnings.** A share smaller than the smallest cell can carry (`(1 − slack) × smallest cell`) is
   *not scheduled*; rest days pushing `flexible` past its share; unknown ids in the season focus.

Edge cases: a one-block (`flexible`-keyed) day gives 14 cells, one focus per day (preferred blocks and
energy peak are no-ops, alternation still applies); all-zero shares (`flexibleShare` 1) → every cell flexible;
`meals` slots and `appointmentWeekdays` are untouched.

## Tunables — `data/questionnaire.json` → `generator`
| key | default | effect |
|---|---|---|
| `anchorPinCoverage` | 0.5 | fraction of a block one category's anchors must cover to pin the cell |
| `overshootSlackCells` | 0.5 | how far past its target (in cells) a category may still take a cell |
| `preferredBlockWeight` | 0.2 | bonus for the category's best preferred block (scaled down the list) |
| `energyPeakWeight` | 0.15 | bonus for a struggle category in the energy-peak block |
| `seasonFocusWeight` | 0.1 | bonus for the season's main focus (scaled down the list) |
| `alternationWeight` | 0.1 | penalty for repeating a focus in the same block on the twin day |
| `energyPeakBlock` | morning→first, midday→middle, evening→last, varies→null | which focus block the peak means |

The relative-deficit term moves by about one cell's share of a target (0.1–0.25) per cell taken, so the
weights above are of the same order: strong enough to place a category, never enough to break the eligibility
cap. Sanity check kept by the tests: generating from `examples/workbook/weights.baseline.json` gives back
its shares within one cell per category (26 of the 42 workbook cells come out identical).

## Activities inside the cells
`generate_activities(weights, grid, questionnaire, categories)` / `generateActivities(weights, grid, questionnaire,
{categories})` → `{activities, placedMinutes, warnings}` for any grid — the proposal's (stored as
`proposal.activities`) or the person's own (the day pages). Nothing here is timed to the minute except meals; a
session is block-scoped, like the workbook's untimed routines.

**Record:** `{id, title, kind: session | practice | meal, dayKey, block, priority, categories, subjectId | null,
timing: null | {estimatedStart, estimatedEnd, durationMinutes}, minutes, reason, source: "proposed"}`;
`id = proposed--<kind>--<slug>--<dayKey>--<block>[--n]` (slug = subject / practice id, `meal-<i>`).

**Rule (same order in both ports):**
0. Cells and capacity: `focus(day, block) = grid[day][block]` (missing = flexible); `capacity = block duration −
   minutes its anchors take` (imported fixed activities and standing appointments with a block, each once).
1. **Practices** (`weights.practices`, Focus 5): per day, in the first block whose focus is
   `spirituality-development`, else the first focus block — one untimed activity per practice, `practiceMinutes`
   (15), priority 2, reason `daily practice`. Rest days included (a daily habit).
2. **Meals** (`weights.meals`, Day and year): per day and meal, the first slot whose `mealSlotTimes` clock falls in a
   focus block (`block_key_for_time`, wrap-midnight aware) — a timed activity of `mealMinutes` (30), priority 2,
   categories `[meals]`, reason `meal slot <slot>`, titled `<Meal>: <dish>` when the Fork Knife menu (`weights.mealPlan`,
   `docs/meal-plan.md`) has a dish for that meal and day (`(leftovers)` on the second day); a meal none of whose
   slots lands in a focus block (or only `anytime`) is warned about once, not placed. The menu's prep and cook
   tasks are not proposed here — Fork Knife creates them as tasks.
3. **Targets**: `usable = Σ capacity of non-rest cells` after 1–2; per category `share × usable`, split among its
   non-peripheral subjects (categories.json order) by their range midpoints, rounded to the session grid
   (`sessionGridMinutes` 15). Sizing to the *usable* minutes (rather than to `minutesPerCycle`) keeps the targets
   honest about rest days, anchors, meals and practices; a category with a share but only peripheral subjects is
   warned about.
4. **Focus fill**: per focus cell (day order × block order, rest days skipped), the cell's capacity is split
   among the focus category's subjects **in proportion to their remaining need** (whole grid units, largest
   remainders first, ties in pool order) — one session per subject per cell, priority 3, reason
   `focus <C>: <placed>/<target> min`.
5. **Spillover**: flexible cells on non-rest days take the neediest subject of any category, at most
   `maxSessionMinutes` (120) per session (the same subject still neediest extends its session), priority 4, reason
   `spillover: <C> behind by <n> min`. Catching up is one of the three things a flexible block is for; the other
   two are seasonal and occasional work (the subjects on the `section` cadence, and those marked "not often" —
   `docs/questionnaire.md` → Cadence) and staying open for an appointment. A profile that declares less than its
   waking window has a real `flexibleShare`, so more flexible cells than spillover has anything to put in: those
   are left **empty on purpose**, and go to the person's assistant as open time rather than being filled with
   something invented.
6. **Warnings** (prefixed `activities:`): one line per category whose subjects did not all fit (`<C>: <n> of
   <target> min left for flexible time — too little to fill a cell of its own (<subject n>, …)`). That is a
   statement about where the minutes went, not a failure: a category whose subjects are mostly on a cadence
   (errands twice a fortnight, `docs/questionnaire.md` → Cadence) is too small to win whole cells and is done in
   flexible time instead. Also: meals outside the blocks, cells whose anchors leave less room
   than their practices and meals need (`over-committed by anchors: …` — they are still listed, a meal or a daily
   habit is not optional), categories without subjects, and `the weights carry no subjects` for a thin file (the
   workbook baseline places nothing).
`placedMinutes = {subjectId: {target, placed}}` is what the day-page reasons and a future *by proposed activities*
allocation view read.

**Activity tunables** (`generator`): `sessionGridMinutes 15`, `maxSessionMinutes 120`, `practiceMinutes 15`,
`mealMinutes 30`, `mealSlotTimes {early-morning 07:00, mid-morning 10:00, afternoon 13:00, evening 18:00,
late-evening 21:00, anytime null}`.

## Follow-ups
Season focus for a person's own sections (`docs/roadmap.md`), a goal ramp from `currentMinutesPerDay` to the
goal range, peripheral subjects as occasional tasks, `meals` slots as anchors for the block split, and editing
the proposal cell by cell before adopting it.
