# The meal plan (ForkKnife): the fortnight menu and its prep / cooking tasks

**ForkKnife** is the site's second face (`docs/app.md`): its own Overview, **Spoon Feed**, Questionnaire and Assistant
pages under `/forkknife/`, sharing the profile with FortKnight. Its **questionnaire** (the `face: "forkknife"` section of
`data/questionnaire.json`, "Your meals") is its settings: the meals question — a person's meals (Breakfast, Dinner,
Snack by default; 2–5), when each is eaten (1–2 times of day, `meals.meals[].slots`), whether a menu item of that meal
*needs prepping* and/or *cooking* and how long that takes — followed by the **meal preferences** the assistant prompt
embeds (`eaters`, `dietaryRules`, `allergiesAndDislikes`, `favouriteCuisines`, `favouriteDishes`, `cookingSkill`,
`foodBudget`, `kitchenKit`, `shoppingCadence`; option lists in `questionnaire.options`, defaults in
`defaultAnswers`, kept whole under `weights.questionnaire.answers` — nothing here moves shares). The menu itself is not on that page:
it is built on **Spoon Feed** (`/forkknife/spoon-feed/`, and by the same editor on FortKnight's Build page,
`/fortknight/build/`) — for each meal, the dishes and the day(s) they are eaten across the fortnight — by hand, or by
applying a **meal-plan document** (this contract) on ForkKnife's Assistant page, whose step 1 hands the person a **prompt**
(`mealPlanPrompt`, `docs/assistant-workspace.md`) built from those answers, this contract and a template. Save keeps
it all with the profile (`answers.mealPlan` → `weights.mealPlan`; every page saves only its own answer keys over the
profile as stored at that moment — Spoon Feed writes `mealPlan` alone, Build writes it with the commitments and tasks,
and ForkKnife's questionnaire writes `FORKKNIFE_ANSWER_KEYS`, carrying the menu through so that renaming a meal
retags its dishes and dropping a meal drops them). ForkKnife's **Overview** shows the menu as the
14-day grid and the **meal-prep and cooking tasks** the menu implies, as an import document (version 2) the person
pastes into *Apply from assistant*, step 2 — so the tasks enter the profile the way everything else does. Rule and
schemas: `data/schema/meal-plan.schema.json`, `data/schema/import.schema.json` (`tasks`, `mealPlan`),
`scripts/fk_core/meal_plan.py` ↔ `src/lib/shared/meal-plan.js`.

## The shape of a menu
- A meal covers the 14 day keys with about **8 dishes**: 6 eaten twice (the second day is **leftovers**) and 2
  eaten once. The editor shows the coverage per meal ("8 dishes · 14/14 days") and the days still open.
- A dish's **second serving is never the next day and at most three days after the first**, and the fortnight
  wraps: after Saturday B the allowed days are Monday B, Tuesday A, Wednesday B. (`allowed_second_days`: first
  + 2, + 3, + 4 mod 14.)
- **Leftovers may cross meals**: a dish eaten at an afternoon / evening / late-evening meal may return as an
  early-morning / mid-morning / afternoon meal (dinner on Sunday A → breakfast on Tuesday A), the same day rules
  applying — `leftoversMeal` names that meal (id `dinner--sun-a--breakfast--tue-a`). A morning meal's leftovers
  do not move on to a later meal.
- **One dish per meal per day** — a leftovers serving counts for the meal that eats it.
- Item id = `<meal slug>--<first day>[--<second day>]`, e.g. `dinner--sun-a--wed-b` (shown as "Dinner · Sunday A
  + Wednesday B"): whatever is dinner on Sunday A is already made for Wednesday B.

## The document (`meal-plan.schema.json`)
```json
{
  "schemaVersion": 1,
  "kind": "meal-plan",
  "source": {"kind": "assistant", "description": "Autumn menu, first draft"},
  "items": [
    {"meal": "Breakfast", "dish": "Overnight oats", "days": ["Sunday A", "Tuesday A"]},
    {"meal": "Dinner", "dish": "Lentil soup", "days": ["sun-a", "wed-b"], "notes": "double the batch"},
    {"meal": "Dinner", "dish": "Tacos", "days": ["Saturday B", "Monday B"], "leftoversMeal": "Breakfast"},
    {"meal": "Dinner", "dish": "Roast chicken", "days": ["Monday A"]},
    {"meal": "Dinner", "dish": "Cheese and crackers", "days": ["Friday A"], "needsPrepped": false, "needsCooked": false}
  ]
}
```
- `meal` — the meal's name as in the questionnaire (matched by slug: "Dinner", "dinner" and "DINNER" are the same
  meal); an unknown name is a problem.
- `days` — the first serving, then optionally the leftovers day: day keys (`sun-a` … `sat-b`) or names
  (`Sunday A`); the second day must be an allowed one (above).
- `leftoversMeal` — optional: the meal that eats the leftovers when it is not the same meal (name or slug; the
  cross-meal rule above applies).
- `notes` — optional free text (shown on the ForkKnife list).
- `needsPrepped` / `needsCooked` — optional, this **dish's** own answer where it differs from its meal's:
  `false` means this dish needs no prepping / no cooking, so no Prep / Cook task is made for it (the editor's
  *no prep needed* and *no cooking needed* checkboxes); `true` means "as the meal says". Absent or `null` follows
  the meal, which is every dish that has never been told otherwise. A dish cannot opt *in* to a step its meal does
  not have — the meal decides whether the step exists and how many minutes it takes, the dish only opts out.
- `source` and top-level `notes` are optional provenance.

Applying (the Assistant page, step 2 — it recognises `kind: "meal-plan"`; ForkKnife only downloads the template): every item is
normalised (`{id, meal (slug), dish, days (keys), notes}`), problems are listed one per item and nothing of a
problematic item lands; valid items **merge by id** into the profile's plan (same id replaces, the rest is kept).
The profile is re-derived and saved.

## The tasks document (Create tasks)
`tasks_from_meal_plan` / `tasksFromMealPlan` turn the menu into import-document tasks, one line per meal need:
- a meal that **needs cooking** → `Cook <dish> (<Meal>)` on the first serving's weekday, `when` = the meal's first
  time-of-day slot as a task word (early/mid-morning → morning, afternoon, evening, late-evening → night, anytime),
  `lasts` = the meal's `cookMinutes`;
- a meal that **needs prepping** → `Prep <dish> (<Meal>)` on the weekday **before** the first serving (Saturday B
  before Sunday A — the fortnight wraps), `when: "evening"`, `lasts` = `prepMinutes`;
- **a dish that opted out gets neither**: `needsCooked: false` on the item drops its Cook task, `needsPrepped: false`
  its Prep task, and the matching `review` line goes with it, so the review and the tasks can never disagree;
- every task `repeats: "every other week from <date>"` where the date is the next calendar date of that day key by
  the person's own seasons (`personDayKeyResolver`), so the app's every-other-week cadence lands it on the right
  A/B week; `category: "meals"`; leftover days get nothing.
The document (`forkknife_import_document`) is a version-2 import document: `source {kind: "forkknife"}`,
`commitments: []`, the `tasks`, a readable `review`, and **`mealPlan`** (the menu itself) — applying it on the
Assistant page adds the tasks (deduped on title + time of day + weekdays, so re-applying is idempotent) and merges
the menu into the profile's meal plan. ForkKnife shows it with *Copy* / *Download* (`meal-tasks.import.json`)
and a link to the Assistant page.

## What reads the menu
- **Spoon Feed** (`/forkknife/spoon-feed/`) and **Build** (`/fortknight/build/`) — where it is edited by hand: the
  same editor on both, one section per meal with its coverage, its dishes — each with the *no prep needed* /
  *no cooking needed* checkboxes its meal's steps earn it — and one entry row (dish, first day, leftovers day, *Add*).
- **ForkKnife's Overview** (`/forkknife/`) — the 14-day menu grid (one line per meal per day, `menuForDay`) and the tasks.
- **Day pages** (`/fortknight/days/<dayKey>/`) — the menu line: "Breakfast: Overnight oats · Dinner: Lentil soup
  (leftovers) · Snack: —" (`dayPlan().menu`); the applied tasks show in their blocks (` · task`).
- **The generator** (`docs/generator.md`, activities): each proposed meal activity is titled with its dish
  (`Dinner: Lentil soup`, `(leftovers)` on the second day); prep and cook are *not* proposed — they are the tasks
  ForkKnife creates.
- **The assistant workspace** publishes this document and its schema, so an assistant can draft a menu from the
  person's meals and preferences (ForkKnife's assistant page hands them the prompt), a recipe list or a shopping
  habit, and hand it back as a meal-plan document (applied on either Assistant page, `kind: "meal-plan"`).

## Not yet
Shopping lists, cook-extra chains (a dish as an ingredient of a later one), season menus (`data/menus/`) as a
source for the plan, and slot-aware placement of prep tasks (right before the meal, not just the evening before).
