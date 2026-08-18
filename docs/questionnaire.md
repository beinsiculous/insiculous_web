# Questionnaire

The startup questionnaire turns a person's answers into a **weights** file (`docs/weights.md`) —
how much of the fortnight each category should get. This document is the record of the questions
as the owner drafted them, how each answer lands in the weights contract, and the open questions.

- Question definitions, slider bounds and derivation constants: `data/questionnaire.json`
  (`data/schema/questionnaire.schema.json`). The app renders from that file; do not hard-code
  questions elsewhere.
- Derivation rule: `scripts/fk_core/weights.py` (Python) and `src/lib/shared/weights-rules.js`
  (JavaScript, canonical for the app). `tests/test_weights.py` runs both on
  `tests/fixtures/questionnaire-answers.sample.json` and asserts identical output.
- CLI: `python3 scripts/questionnaire_to_weights.py answers.json --id <id> [--out data/weights.<id>.json]`
  (or `--defaults` for the slider defaults). Any `data/weights.*.json` is validated by
  `validate.py`; only `weights.baseline.json` is bundled.
- App: `/fortknight/questionnaire/` in the Astro app renders the sections without a `face`; ForkKnife's questionnaire
  (`/forkknife/questionnaire/`) renders the `face: "forkknife"` section — the meals question and the meal preferences.
  Neither questionnaire holds an editor for the *content* any more: the fortnight menu is built on Spoon Feed
  (`/forkknife/spoon-feed/`, `docs/meal-plan.md`) and the commitments and tasks on Build (`/fortknight/build/`, which
  carries the menu editor too); `/profile/` holds the profile actions and the workspace downloads. Each
  questionnaire *is* its face's settings; all four pages write the same profile, each only its own answer keys
  (`FORKKNIFE_ANSWER_KEYS` for ForkKnife's questionnaire, `mealPlan` for Spoon Feed, `mealPlan` +
  `standingAppointments` + `tasks` for Build, the rest for FortKnight's), over the profile as stored at save time. Named profiles per device, one active (`docs/app.md` → User settings): Save derives
  the active profile's weights (`settings.weightsProfiles[activeWeightsId]`, default id
  `username` by default, answers inside at `questionnaire.answers`); Download gives `weights.<id>.json`. An
  assistant in the person's own workspace can hand back a weights file or an import document
  (`docs/assistant-workspace.md`; an agenda it drafts is an import document — `docs/llm-guide.md`).

## Sections as rendered (`questionnaire.json` order; numbering restarts per section)

| section | questions | what it settles |
|---|---|---|
| **Startup** | 1 group size · 2 existing systems — a count of the commitments (standing appointments incl. work/school hours) and tasks the profile holds, what the Assistant page applied, and links to the two ways in (by hand on the Build page, or uploaded on the Assistant page) | who this is for; the person's commitments (anchors the blocks are cut around) and tasks (day pages) |
| **Your day and year** | 1 waking window · 2 week start · 3 year split | the waking window (the agenda's scope), the day the fortnight restarts on, the person's own seasons |
| **Your week** | 1 appointment weekdays · 2 rest days | where appointments go, which days stay light |
| **Focus** | 1 hours per subject · 2 struggle/enjoy · 3 hand off · 4 must do personally · 5 practices · 6 agenda scope | how the waking window is shared between categories and how many focus blocks a day earns |
| **About you** | 1 energy peak · 2 free-text context | what an assistant needs to turn the weights into an actual agenda; no share effect |
| **Your meals** (`face: "forkknife"` — ForkKnife's questionnaire) | 1 meals (names, times of day, prep/cook) · 2 eaters · 3 dietary rules · 4 allergies and dislikes · 5 cuisines · 6 favourite dishes · 7 cooking skill · 8 food budget · 9 kitchen kit · 10 shopping cadence | the meals the menu and the generator use; the preferences ForkKnife's assistant prompt embeds (`docs/meal-plan.md`); no share effect |

The draft below is the owner's wording in its original order ("Other settings questions" became
the first question of *Your day and year* and the last of *Focus*); the mapping table further down
uses the rendered labels.

## The draft (owner's wording, kept verbatim)

# Startup Questions

### 1. How many people are in your group?

>[IF: group is more than 14 people]

>[THEN: FORTRESS SYSTEM: Each Fortress has 1-7 forts and each fort has 1-14 members. Each Fort has a Cham, and each account has an admin]

>[ELSE: Admin has a single team Fort no leaders]

### 2. Do you already use a calendar, task list, reminder and or budget system?

***

    *upload docs, pics, and description here*

***

**The rest of the questions have preset defaults. Rearrange your settings now or later in the settings menu**

***
***

# Focus Questions

***

## Focus Categories
**Slide the bar for each subject to select a time range.**

If you do not want a subject included in your agenda, mark it "not often" and it will be considered a peripheral subject. A few peripheral tasks may still show up and will be marked as peripheral in your agenda. All periphery settings can be found in the categories section of the settings menu.

### 1. How long can you spend on each in a single day?

| Cleaning | not often | hrs/day |  more |
|---|---|---|---|
| Laundry | [ ] | .25–3 | [ ] |
| Decoration | [ ] | 0–2 | [ ] |
| Dishes | [ ] | .25–1.5 | [ ] |
| Organization | [ ] | 0–1 | [ ] |
| Packing | [ ] | 0–1.5 | [ ] |
| Sensitization | [ ] | .25–2 | [ ] |

| Friends & Family |  not often | hrs/day |  more |
|---|---|---|---|
| Calendar organization | [ ] | 0–1 | [ ] |
| Dating | [ ] | 0.25–8 | [ ] |
| Event/party/get-together planning | [ ] | 0–0.5 | [ ] |
| Pet care | [ ] | 0–1 | [ ] |

| Health |  not often | hrs/day |  more |
|---|---|---|---|
| Appointments | [ ] | 0–3 | [ ] |
| Exercise | [ ] | 0.5–1.25 | [ ] |
| Hygiene | [ ] | 0.5–1 | [ ] |
| Journal | [ ] | 0–0.5 | [ ] |
| Leisure/Rest | [ ] | 1–12 | [ ] |
| Medical provisioning | [ ] | 0–0.75 | [ ] |
| Therapies | [ ] | 0–1 | [ ] |
| Treatments | [ ] | 0–12 | [ ] |

| Meals | not often | hrs/day |  more |
|---|---|---|---|
| Cooking | [ ] | .5–2 | [ ] |
| Planning | [ ] | 0–.75 | [ ] |
| Preparation | [ ] | 0-2 | [ ] |
| Food provisioning | [ ] | 0–4 | [ ] |

| Operations |  not often | hrs/day |  more |
|---|---|---|---|
| Budgeting | [ ] | 0–1.5 | [ ] |
| Errands | [ ] | 0–3 | [ ] |
| Financial and life planning | [ ] | 0–1.5 | [ ] |
| Maintenance | [ ] | 0–6 | [ ] |
| Product/service research | [ ] | 0–1.5 | [ ] |
| Provisioning | [ ] | 0–2 | [ ] |
| Stewardship | [ ] | 0–6 | [ ] |

| Spirituality & Development |  not often | hrs/day |  more |
|---|---|---|---|
| Coaching/mentoring | [ ] | 0–3 | [ ] |
| Conferences/courses | [ ] | 0–6 | [ ] |
| Creative study or expression | [ ] | 0–6 | [ ] |
| Solo learning/research/study | [ ] | 0–6 | [ ] |
| Seeking council/advisement | [ ] | 0–3 | [ ] |
| Teaching/tutoring | [ ] | 0–6 | [ ] |

| Work |  not often | hrs/day |  more |
|---|---|---|---|
| Billable hours | [ ] | 0–12 | [ ] |
| Public relations management | [ ] | 0–3 | [ ] |
| Networking | [ ] | 0–3 | [ ] |
| Transportation/commute | [ ] | 0–2 | [ ] |
| Volunteering | [ ] | 0–10 | [ ] |

***

### 2. Which subjects would you like to spend more time on?

| Focus | [x] |
|---|---|
| cleaning | [ ] |
| friends & family | [ ] |
| health | [ ] |
| meals | [ ] |
| operations | [ ] |
| spirituality & development | [x] |
| work | [ ] |

***

### 3. Mark which categories you struggle with, and which you enjoy.
Do not mark any subjects you have a neutral relationship with.

| [struggle with] | Focus | [enjoy] |
|---|---|---|
| [x] | cleaning | [ ] |
| [ ] | friends & family | [x] |
| [ ] | health | [ ] |
| [ ] | meals | [ ] |
| [x] | operations | [ ] |
| [ ] | spirituality & development | [ ] |
| [ ] | work | [x] |

***

## Vacation or Emergency
**During an active emergency (sick days, out of town, etc), a grieving or transition period, a time of struggle (health, financial, emotional, etc.), crunch time, or recovery:**

### 4. Which categories you can easily hand off to someone else? (delegate, defer, pause, pay for, take a sabbatical from, etc.)

| Focus | [x] |
|---|---|
| cleaning | [ ] |
| friends & family | [ ] |
| health | [ ] |
| meals | [x] |
| operations | [ ] |
| spirituality & development | [ ] |
| work | [ ] |

***

### 5. Mark 1-3 categories you have to do personally, even under duress.

| Focus | [x] |
|---|---|
| cleaning | [ ] |
| friends & family | [ ] |
| health | [x] |
| meals | [ ] |
| operations | [x] |
| spirituality & development | [ ] |
| work | [x] |

***
***

# Other Settings Questions

### 1. How much time do you need for your unscheduled block?
wind down ritual + sleep + wake up ritual

6-10 hrs - default 8

(Since 2026-08-16 the question is asked the other way round, as the **waking window** — a double slider
on a 42-hour track from midnight, 10–18 hours between the thumbs, "When are you awake?"; the unscheduled
block is its complement. Same rule underneath.)

### 2. Do you want your day to include subjects or just categories?
Option 1: Subjects — detailed, task-oriented agenda. Option 2: Categories — wide-scope focus where
individual tasks are implied. Option 2 is the default, and when selected a block is added to the
day. Any schedule with only 2 blocks (scheduled and unscheduled) has only a flexible and an
unscheduled block, and flexible is not displayed as the block header.

***

***
***

### Second batch (owner's wording, kept verbatim)

1) How many meals do you eat in a day and when do you eat them?
Between 2 and 5 meals; pick 1 or 2 for each meal: early-morning mid-morning, afternoon, evening, late-evening, anytime
2) How do you like to split your year?
2 sections: semesters (school, off-season), 4 sections: quarters (financial quarters, classic 4 seasons), between 3 and 13 sections: months/seasons/custom (Gregorian calendar, lunar calendar, Norse wheel, religious calendar, astrological calendar)
3) Do you have any standing appointments each week/month?
lessons, therapies, meetings, etc.
4) What weekday (s) do you like to schedule appointments on?
5) Mark which of the following practices you participate in or would like to participate in:
yoga, meditation, prayer, actively listening to your own thoughts or emotions, quieting of the mind, religious practices, introspection, surrender
6) Do you already use a calendar, task list, reminder and or budget system?

(6 is Startup Q2 and is not asked twice. 1–2 live in "Your day and year", 3 is the Build page's
commitments editor, which Startup Q2 links to, 4 in "Your week", 5 at the end of the Focus questions.)

### Third batch (owner's wording, kept verbatim)

1) On which day of the week do you start your week? — default Sunday. (Your day and year 3, right
before the year split; it is the day the fortnight restarts on. Custom year-split sections "start with"
computable rules like the seasons — the person picks per section whether it opens on week A or B;
presets get rules too but are not customizable, and their vague markers stay blank for now.)

## How each answer lands in the weights file

| question | answers key | weights field | notes |
|---|---|---|---|
| Startup 1 group size | `startup.groupSize` | `questionnaire.answers.startup` (raw only) | Fortress/Fort/Cham is a future multi-user concept; nothing in the data model represents it yet |
| Startup 2 existing systems — commitments | `standingAppointments[{title, weekdays[], start, durationMinutes, category, cadence{kind,…}}]` (edited on the **Build page**, `/fortknight/build/`: one entry row; *Add* commits into a read-only list, *Edit* only reveals remove — or appended by an import document applied on the Assistant page; Startup 2 only counts them) | `standingAppointments` **and** `blockSplit.anchors` (`source: "standing-appointment"`) | cadences: `weekly` (every listed weekday, both weeks), `every-other-week` + `firstDate` (the week that date resolves to; both weeks + warning when no resolver), `monthly-nth-weekday` + `nth`, `monthly-date` + `dayOfMonth`, `one-off` + `date` (pooled, no day key); they snap cuts and vote for the chosen category's `preferredBlocks` |
| Startup 2 existing systems — tasks | `tasks[{title, weekdays[], cadence, timeOfDay, durationMinutes, category}]` (same entry-row + list pattern on the **Build page**, or appended by an applied import document; Startup 2 only counts them) | `tasks` | a day but no clock time; placed on the day pages by `timeOfDay` (`morning 09:00 · midday 12:00 · afternoon 15:00 · evening 19:00 · night 21:00 · anytime` = listed without a block); never anchors, no share effect |
| Startup 2 existing systems — applied import (the one part of Q2 still *on* the questionnaire) | `startup.importJson` (the raw text of the document applied on the Assistant page) and `startup.import` (that document as pasted, or `null`; *Forget the applied import* clears both) | `blockSplit.anchors` (`source: "import"`, from `import.fixedActivities`), `blockFocusGrid` (`import.blockFocusGrid` restricted to this profile's focus blocks — what `/fortknight/` shows unless the person adopted a proposal, `answers.blockFocusGrid`, which wins), `appointmentBlocks` | contract in `docs/importers.md` (version 2 is written for the person to read; the review of what landed shows on both pages); the owner's document is `source/import.my-activities.json`; the workbook example set yields one via `build.py --overlay examples/workbook`; the Import page that produces other documents is roadmap 4 |
| Day and year 1 waking window | `wakingWindow {start, end}` (HH:MM; end before start = it passes midnight) | `wakingWindow {start, end, minutesPerDay, minutesPerCycle}`, `unscheduledBlock {start, end, minutes}` (its complement), `blocks`, `blockSplit` | default 06:00–22:00 (`questionnaire.wakingWindow.default`); length bounded by `wakingWindow.minutes` (10–18 h, `answersProblem` rejects other lengths); the form is a double slider on a 42 h track from midnight (`wakingWindow.track`) so any window fits, thumbs snap to `minutes.step` (15); the unscheduled block (wind-down + sleep + wake-up, long enough to swallow breakfast/dinner routines that need no scheduling) is whatever is left; see "Block split" |
| Your meals 1 meals (ForkKnife) | `meals {perDay, meals[{name, slots[], needsPrepped, needsCooked, prepMinutes, cookMinutes}]}` | `meals` (defaults filled: `mealsWithDefaults`) | 2–5 named meals (names must be distinct once slugified — they key the ForkKnife menu; renaming retags the menu, dropping a meal drops its dishes), 1–2 slots each (`options.mealSlots`, ticked in the same row), whether a menu item needs prepping and/or cooking and how long (`questionnaire.mealPrep` slider 0–180 step 15); defaults Breakfast early-morning cooked 30, Dinner evening prepped 15 + cooked 45, Snack afternoon prepped 15; the menu those meals key is built on Spoon Feed, `/forkknife/spoon-feed/` (`docs/meal-plan.md`), and this page carries it through a save so the retag and the drop happen |
| Your meals 2–10 preferences (ForkKnife) | `eaters` (integer ≥ 1), `dietaryRules[]`, `allergiesAndDislikes` (text), `favouriteCuisines[]`, `favouriteDishes` (text), `cookingSkill`, `foodBudget`, `kitchenKit[]`, `shoppingCadence` | `questionnaire.answers.*` only (kept whole) | option lists `options.dietaryRules / cuisines / cookingSkills / foodBudgets / kitchenKit / shoppingCadences`; defaults 1, [], "", [], "", comfortable, moderate, [], weekly; a missing key means the default (profiles from before ForkKnife's questionnaire); `answersProblem` (`mealPreferencesProblem`) rejects unknown option ids and non-integer eaters; `validate.py` checks every select question's list exists and its default is a member; no share effect — they only feed `mealPlanPrompt` (`docs/assistant-workspace.md`) |
| Day and year 2 week start | `weekStart` | `weekStart` | one of `options.weekdays` (default `sunday`); the weekday sections snap to by default, the weekday half of every section's start day key (`<weekday>-<startVariant>`), and the first column of the fortnight grid |
| Day and year 3 year split | `yearSplit {scheme, sectionLabel, sections[{title, kind?, gregorianEquivalent?, durationWeeks?{min,max}, start{marker, description, rule?}, startVariant?, knownStarts?}]}` | `yearSplit` | each scheme (`options.yearSplitSchemes`) has a one-sentence `blurb`, shown under the option only while it is selected (the question carries no note); picking a preset takes its sections from `template` without showing them (they stay in the answers), **only Custom opens the section editor, and it starts from FortKnight's own five seasons** (`templateFrom: "seasons"` → `year_split_from_seasons()` / `yearSplitFromSeasons()` map `data/seasons.json`); `sectionLabel` = what a section is called (season, era, term…); markers: `date`, `rule`, `holiday`, `weather`, `manual` (`options.sectionMarkers`); 2–13 sections; default quarters (Q1–Q4). This is the seed for a profile's own seasons — the generator will turn it into `seasons.json`-shaped seasons later; **each section's `start.rule` is a computable start** (see "Section start rules" below): presets carry rules only where the marker is exact (quarters/months = the 1st, astrological dates, equinox/solstice, the Nth new moon), vague ones stay `null`; `startVariant` (`a`/`b`, default a) + `weekStart` give the section's start day key; `knownStarts {year: date}` are the typed starts of `manual` sections. The person's sections become their own `seasons.json`-shaped seasons (`seasons_from_year_split` / `seasonsFromYearSplit`) and drive date resolution on `/`, `/days/` and in the CLI |
| Your week 1 appointment weekdays | `appointmentWeekdays[]` | `appointmentWeekdays` | empty = any day |
| Your week 2 rest days | `restDays[]` | `restDays` | weekday ids (`options.weekdays`); empty = every day alike; no share effect — the generator pins those days' cells to `flexible` and proposes no sessions on them (`docs/generator.md`) |
| Focus 1 hours per subject | `subjectTime[subject] = {minutesPerDay:{min,max}, peripheral, more, goal, everyday, cadence?, daysPerPeriod?, specificDaysNote?, notOftenNote?, currentMinutesPerDay?}` | `subjects[subject].{minutesPerDay, peripheral, goal, currentMinutesPerDay, everyday, cadence, daysPerPeriod, specificDaysNote, notOftenNote}` and, summed, `categories[*].share` | slider bounds in `questionnaire.subjectSliders`, integer minutes on a 5-minute grid; **everyday** (the default) contributes the range midpoint, and unticking it asks how often instead — see "Cadence" below; "not often" = `peripheral`; "more" raises the ceiling to `moreMax` (twice the normal ceiling, capped at 24 h); **goal** = wanted in the schedule but not done at that level yet — the form then asks for the current actual; shares use the goal range; the generator's proposed sessions size each subject by its range midpoint within its category (`docs/generator.md`); the ramp from current to goal is open |
| Focus 2 want more | — (superseded by the goal toggle; not asked) | `categories[*].wantMore` = any subject of the category has `goal: true`; ×`wantMoreMultiplier` (1.25) on that category's raw minutes | the draft's Q2 stays above for the record |
| Focus 3 struggle / enjoy | `sentiment{category: struggle|enjoy}` | `categories[*].sentiment` (`neutral` when unmarked) | mutually exclusive per category |
| Focus 4 hand off | `delegable[]` | `categories[*].delegable` | for the generator's emergency / vacation mode |
| Focus 5 must do personally | `essential[]` | `categories[*].essential` | 1–3 expected (`questionnaire.essentialCategories`); the app blocks saving outside that, `validate.py` warns |
| Focus 5 practices | `practices[]` | `practices` | ids in `options.practices`; no share effect — the generator proposes one short daily activity per practice (`docs/generator.md`) |
| Focus 6 agenda scope | `agendaScope` (`subjects` \| `categories`, default `categories`) | `agendaScope`, `blockSplit.agendaScope`, and one more focus block when `categories` | ids in `options.agendaScopes`; `categories` = wide-scope blocks where tasks are implied → the default day has three focus blocks (early, midday, late — the workbook's keys); `subjects` = only the blocks the standouts earn (none → one `flexible` block, shown without a header) |
| About you 1 energy peak | `energyPeak` (`morning` \| `midday` \| `evening` \| `varies`, default `varies`) | `energyPeak` | ids in `options.energyPeaks`; tells an assistant/generator which block carries the demanding focus; no share effect |
| About you 2 context | `context` (free text, default `""`) | `context` | household, shift patterns, recovery, what alternates between week A and B — anything the sliders cannot say; travels only in the workspace files; no share effect |

Every answers object is kept whole under `questionnaire.answers` (the same idea as `raw` on
imported records): structured fields sit beside it, never instead of it.

### Typical-person defaults (`questionnaire.json`)
The form must be skimmable and submittable untouched, so it opens as a *typical person*:
- every subject slider starts at `subjectSliders[*].default` (inside its bounds), and
  `peripheralByDefault` pre-ticks "not often" for atypical subjects (decoration, packing,
  networking, volunteering, conferences, seeking council, teaching, event planning, pet care,
  journaling, medical provisioning, therapies, treatments, product research, stewardship);
- **the typical person fits inside their own day.** `cadenceByDefault` unticks "everyday" for the 21
  subjects nobody does daily, so the day declares **846 of its 960 minutes (88%)** and opens with
  **1 h 54 min flexible** rather than the 113% it used to declare (everything then scaled down to fit
  and nothing was ever left over). Durations were not trimmed to get there — only frequencies, at
  roughly the rate time-use surveys find people doing each thing:

  | | days a fortnight |
  |---|---|
  | meals | planning 2 · preparation 7 · food provisioning 2 (cooking stays daily) |
  | cleaning | laundry 3 · organization 3 · sanitization 4 (dishes stays daily) |
  | working | **billable hours 10** · commute 10 · PR 5 |
  | spirituality & development | coaching/mentoring 4 · creative study 4 · solo learning 5 |
  | friends & family | dating 4 · extracurricular organisation 2 (relationship management stays daily) |
  | health | exercise 4 · appointments 2 (hygiene and leisure/rest stay daily) |
  | operations | errands 4 · maintenance 2 · provisioning 2 · budgeting 1 · financial & life planning **every section**, 2 days |

  `billable-hours` went the other way: `0–480` every day was a 28-hour week, so it is now `420–540`
  on 10 days a fortnight — a real 40-hour week, and the commute rides the same ten days. `leisure-rest`
  (120–240 daily) is deliberately untouched: it already sits below what surveys report for leisure, and
  trimming rest to make room would have misrepresented the day. `food-provisioning` at 2 days a
  fortnight matches the `shoppingCadence: "weekly"` default the same file carries;
- `defaultAnswers` pre-ticks category boxes — `sentiment: {working: struggle, friends-family: enjoy}`,
  `delegable: [meals]`, `essential: [health, working]` — so Save passes the 1–3 rule untouched;
  `agendaScope: categories`, so the untouched day is unscheduled + early/midday/late; `restDays: [saturday]`,
  `appointmentWeekdays: [wednesday]`, `practices: [listening-to-thoughts-emotions]`,
  `energyPeak: varies`, `context: ""`; no import
  is applied (`startup.import: null`), so `blockFocusGrid` is `{}` and FortKnight's Overview shows
  the person's blocks without a focus until an import document is applied.
`default_answers()` / `defaultAnswers()` in both ports read these; retune the numbers in data.
Every subject has a `description` in `categories.json`; the form shows it as a tooltip on the
subject name (category names get a tooltip listing their subjects).

### Cadence (Focus 1)
The slider always means **one day**: *how long can you spend on this in a single day*. What changes is how many
days. A subject is in exactly one of four states:

| state | asks | contributes to its category |
|---|---|---|
| **everyday** (default, `everyday: true`) | the slider | the range midpoint |
| **every fortnight** (`cadence: "fortnight"`) | the slider + `daysPerPeriod` (1–13) + an optional `specificDaysNote` | `midpoint × daysPerPeriod ÷ 14` |
| **every section** (`cadence: "section"` — the person's own year-split unit, labelled with their `sectionLabel`) | the slider + `daysPerPeriod` (1–`sectionDays`−1) + an optional `specificDaysNote` | nothing |
| **not often** (`peripheral: true`) | an optional `notOftenNote` | nothing |

A section is the year shared evenly between the person's sections (`section_days_from_year_split` /
`sectionDaysFromYearSplit`; 365.25 ÷ 4 = 91 days for quarters). Sections' own `durationWeeks` are a rough label
from their scheme — gregorian-months says four weeks for a 30-day month — so the year is divided instead.

The two states that contribute nothing are the point of the feature, not a gap in it: shares are what was
*declared* (rule 3 in `docs/weights.md`), so minutes a person moves off "everyday" are not handed to the other
categories — they stay in `flexibleShare`, the fortnight's open time, which is where seasonal and occasional
work actually gets done. Both notes are free text for the person's assistant, capped at 300 characters
(`SUBJECT_NOTE_MAX_LENGTH`); nothing but the workspace files reads them. `answersProblem` (the app's save gate)
checks the cadence id, the day count against its period, and the note length.

### Category sliders (UI only)
Each category is one visible row — not often · least–most range · more — with its subjects
collapsed beneath. The category range is the **sum of its non-peripheral subjects**: dragging a
category thumb redistributes the new total over those subjects in proportion to their current
values (evenly when all are zero), snapped to each subject's step, clamped to its bounds, with
any rounding remainder going to the subject with the most room; dragging a subject recomputes
the category thumbs. The category "not often"/"more" boxes tick every subject's and show
indeterminate when subjects disagree. The answers file is unchanged — subjects stay the truth.

### Answers file
```json
{
  "startup": {"groupSize": 1, "importJson": "", "import": null},
  "agendaScope": "categories",
  "subjectTime": {"laundry": {"minutesPerDay": {"min": 15, "max": 60}, "peripheral": false, "more": false, "goal": false},
                  "exercise": {"minutesPerDay": {"min": 30, "max": 30}, "peripheral": false, "more": false, "goal": true, "currentMinutesPerDay": 0}, "…": {}},
  "sentiment": {"cleaning": "struggle", "working": "enjoy"},
  "delegable": ["meals"],
  "essential": ["health", "operations", "working"],
  "wakingWindow": {"start": "06:00", "end": "22:00"},
  "meals": {"perDay": 3, "meals": [{"slots": ["early-morning"]}, {"slots": ["afternoon"]}, {"slots": ["evening"]}]},
  "yearSplit": {"scheme": "custom", "sectionLabel": "era", "sections": [
    {"title": "Planting", "kind": "spring", "gregorianEquivalent": "Mar – May", "durationWeeks": {"min": 10, "max": 12},
     "start": {"marker": "date", "description": "mid-April", "rule": {"kind": "fixed-date", "month": 4, "day": 15, "offsetDays": 0, "snap": {"weekday": "monday", "direction": "on-or-after"}}}, "startVariant": "a"},
    {"title": "Harvest", "kind": "autumn", "durationWeeks": {"min": 8, "max": 9},
     "start": {"marker": "holiday", "description": "Labor Day", "rule": {"kind": "nth-weekday", "month": 9, "weekday": "monday", "occurrence": 1, "offsetDays": 0, "snap": {"weekday": "monday", "direction": "on-or-before"}}}, "startVariant": "a"},
    {"title": "Rest", "kind": "winter", "start": {"marker": "manual", "description": "when the garden is put to bed", "rule": {"kind": "manual", "offsetDays": 0, "snap": null}}, "startVariant": "b", "knownStarts": {"2026": "2026-11-15"}}]},
  "weekStart": "monday",
  "standingAppointments": [{"title": "Therapy", "weekdays": ["tuesday", "thursday"], "start": "16:00", "durationMinutes": 30, "category": "health", "cadence": {"kind": "weekly"}}],
  "appointmentWeekdays": ["tuesday", "thursday"],
  "practices": ["meditation"]
}
```
Subjects missing from `subjectTime` take their slider defaults (full range, not peripheral).
`tests/fixtures/questionnaire-answers.sample.json` is a complete example.

### The rule (one place per language)
1. Each subject contributes the midpoint of its minutes-per-day range; a peripheral subject contributes 0.
2. A category's raw minutes = the sum of its subjects, × `wantMoreMultiplier` when any of its subjects is a goal.
3. `share = raw / total`, rounded half-up to 4 places — the questionnaire assigns the whole waking
   window; there is no flexible input. The weights file's `flexibleShare` is only the rounding
   remainder (`1 − Σ share`, clamped at 0), and 1 when every subject is peripheral (all shares 0).
4. **Waking window** = the answered `wakingWindow` (default 06:00–22:00, 960 min/day, 13440 per fortnight;
   it may wrap midnight); the unscheduled block is its complement (22:00–06:00, 480 min).
   `minutesPerCycle = share × minutesPerCycle`.
5. **Block split** (constants in `questionnaire.blockSplit`): a day has 2–5 blocks — the unscheduled
   block plus 1–4 focus blocks. Categories whose share is ≥ `standoutMultiplier` (1.25) × the mean
   share of the non-peripheral categories each earn a focus block (best first); Agenda scope
   `categories` (Focus 6, the default) adds one more; the count is capped at `maxFocusBlocks`.
   When none stands out under `subjects` the day stays 2 blocks: `unscheduled` + `flexible` (a
   *block key* — not the `flexible` pseudo-focus of `categories.json` — and the UI shows that
   block without a header). Focus block keys by count: 1 `flexible`; 2 `early, late`;
   3 `early, midday, late`; 4 `early, midday, afternoon, late`.
6. **Cuts** start from an even split of the waking window and snap onto a `cutGridMinutes` (5)
   grid within ± `cutSearchMinutes` (90). **Anchors** are the applied import document's
   `fixedActivities` (`priority 1` or `flexibility "no"`, timed; `source: "import"`) plus the
   profile's standing appointments, pooled across the fortnight — a data set's own activities
   never anchor a person's split (only an applied import document does); a candidate
   cut costs `distance in minutes + straddlePenalty (60) × anchors it falls inside − edgeBonus (30)
   × anchor edges it lands on` — all three terms are minutes, so `cutGridMinutes` can be made finer
   without re-tuning the penalties. Straddling is allowed (soft penalty) as long as the activity is in scope; an
   anchor that starts inside the unscheduled block, or runs into it, is reported in
   `blockSplit.warnings`. Flexible blocks carry no constraints (open scope).
7. Anchors then vote for `preferredBlocks`: the block an anchor starts in counts once for each
   of its categories; blocks are ordered by votes (ties keep block order). Flags and ranges pass through.
8. **The grid**: the person's own `answers.blockFocusGrid` (a proposal adopted on `/`) or, without one,
   the applied import's `blockFocusGrid` is copied into the weights' `blockFocusGrid` for the block keys
   this profile has (unmatched keys are dropped with one `blockSplit.warnings` entry, unknown focus values
   cell by cell) — `{}` when neither exists; the import's `appointmentBlocks` pass through. This is what
   `/` shows as *Your grid*.
9. **The proposal**: the generator (`docs/generator.md`, constants in `questionnaire.generator`) reads the
   finished weights and the season the caller names and writes `proposal` — its own grid, a reason per
   cell, warnings and the diff against `blockFocusGrid`; `/` shows it as *Proposed grid* and can adopt it.

### Section start rules
Every year-split section may carry `start.rule` — the same structured start rule the workbook
seasons use (`docs/domain.md`), evaluated by `fk_core/dates.py` `start_date_for_rule` and its
JavaScript twin: `{kind, …, offsetDays, snap}`.

| kind | fields | base date for a year |
|---|---|---|
| `fixed-date` | `month`, `day` | that date (Feb 29 in a common year → no start that year) |
| `nth-weekday` | `month`, `weekday`, `occurrence` 1–4 or −1 (last) | e.g. 2nd Sunday of March |
| `easter` | — | Easter Sunday (Gregorian computus) |
| `solar` | `term` (`spring-equinox`, `summer-solstice`, `autumn-equinox`, `winter-solstice`) | Meeus ch. 27, UTC date |
| `new-moon` | `index` 1–13 | the Nth new moon of the calendar year (Meeus ch. 49, UTC date; a 12-moon year has no 13th → no start) |
| `manual` | — | `knownStarts[year]` typed by the person (no entry → no start that year) |

Then `+ offsetDays` (−366…366), then `snap`: `null` = the exact date, or `{weekday, direction}` =
that weekday on-or-after / on-or-before. The snap weekday is always the person's `weekStart`: the
form reads it live and the derivation (`weights_from_answers` / `weightsFromAnswers`,
`seasons_for_answers` / `seasonsForAnswers`) rewrites `snap.weekday` to `weekStart` so a stored rule
can never go stale after the week start changes; a new custom section defaults to *on or after* and
can be switched to *on or before* or no snap. A section without a resolvable start in a year (no rule, or the kind gives nothing) simply
does not restart the fortnight that year — the previous section continues; if none of a person's
sections has started by a date, the workbook seasons resolve it (`seasonSource: "workbook"`).
Two sections starting on the same date: the later one in the list wins.

A start that is not on the week-start weekday (no snap, or a manual date) keeps calendar weekdays
aligned with day-key weekdays: the fortnight is anchored on the start day key's weekday on or before
the start (a Wednesday start with `mon-a` makes that Wednesday `wed-a`), never "Monday A" on a
Wednesday. Snap is the tool for "restart my fortnight on my week start".

`fk_core/astronomy.py` / `src/lib/shared/astronomy.js` hold the Meeus formulas at day precision (ΔT by the
Espenak/Meeus 2005–2050 polynomial for every year); both ports match exactly over 1950–2100 and a
table of published dates is pinned in `tests/test_dates.py`.

## Naming: `categories.json` always wins
Decided by the owner: subject ids **and** labels come from `data/categories.json`; the draft's
wording (Sensitization, Journal, Calendar organization) is superseded, and `relationship-management`
is part of Friends & Family (bounds 0–2 h). Ids stay immutable; edit labels in `categories.json`.

## Open questions
- **Baseline vs profile blocks.** The baseline data keeps its fixed five blocks (08:00–18:00 focus
  window, `docs/domain.md`); a questionnaire profile carries its own `blocks` and `wakingWindow`.
  The generator (`docs/generator.md`) turns a profile's blocks + shares + `preferredBlocks` + anchors
  into per-day focus; proposed activities inside the cells are the open half of roadmap 2.
- **Block keys vs imports.** An imported grid only lands fully when its block keys match the
  profile's (the workbook's early/midday/late = the default `categories` day); a `subjects` day
  or a fourth block leaves cells empty in *Your grid* on `/`; the *Proposed grid* fills every cell of the
  profile's own blocks and can be adopted.
- **Fortress system** (groups > 14; forts, Chams, admins) needs its own data model before the
  startup question can do more than record a number.
- **Import page** (roadmap 4): produces the import document the Assistant page applies — `docs/importers.md`.
- **"more" ceiling** is a first guess (2× the normal ceiling, capped at a day); tune per subject in
  `data/questionnaire.json` if it feels wrong.
