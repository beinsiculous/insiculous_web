# Fork Knife: the full chain (design; not built)

From a handful of questions to a fortnight that is planned, shopped for, prepped, cooked and already
on the agenda — the target flow end to end, stage by stage, with what exists today and what is
missing at each one.

> **Status: design, not contract.** `docs/meal-plan.md` and `data/schema/meal-plan.schema.json` are
> the shipped contracts and do **not** change until something here is actually built; they are
> published into people's assistant workspaces, so speculative design must never leak into them.
>
> This document is not published either — it is not in `WORKSPACE_STATIC_DOCUMENTS`
> (`src/lib/shared/workspace-docs.js`) and must not be added to it.

The concept is small enough to say in a sentence, which is exactly what makes it hard: the thesis is
in `docs/thesis.md` (Fork Knife — *plan the cooking, not the eating*).

## The chain

**1 Ask** → **2 Brief the agent** → **3 The agent interviews you back** → **4 It produces the menu,
recipes, prep, cooking, shopping** → **5 All of it lands in FortKnight's agenda.**

Stages 1, 2 and 5 substantially exist. Stage 3 does not exist at all. Stage 4 exists for the menu
and the prep/cooking tasks, and not for recipes, shopping schedule or shopping list.

---

## Stage 1 — Ask

**Target.** Questions about **location**, meals, **workload** and **time constraints**, alongside the
preferences already asked.

**Today.** The `meals` section of `data/questionnaire.json` (`face: "fork-knife"`) asks ten questions —
`meals`, `eaters`, `dietaryRules`, `allergiesAndDislikes`, `favouriteCuisines`, `favouriteDishes`,
`cookingSkill`, `foodBudget`, `kitchenKit`, `shoppingCadence` — with option lists under
`questionnaire.options` and defaults under `defaultAnswers`. The questionnaire *is* the settings
(`docs/app.md`); Fork Knife's page writes only `FORKKNIFE_ANSWER_KEYS`.

**Missing.**

- **Location.** Nothing asks it. It is the input that makes everything else concrete: what is in
  season, what a shop actually stocks, what "budget" means in real money, and — with FortKnight's
  seasons already computed per person — what time of year it currently is where you are.
- **Workload and time constraints.** Do **not** re-ask these. FortKnight already holds the answers:
  the waking window, the person's 2–5 blocks, the weights (`meals` is one of the seven categories,
  with its own share of the fortnight), the standing appointments and the rest days. Fork Knife should
  *read* them.

**Decisions to make.**

- How much location detail: a country, a region, a city, a climate? The least that makes the answers
  better, and nothing that turns a device-local profile into an identifying record.
- Where a shared answer lives when both faces want it. The existing rule — each page writes only its
  own answer keys — means a value read by both must have exactly one owner.
- Whether the `meals` category share is a **constraint** on the plan (the menu must fit the minutes
  the fortnight allots to food) or merely a **report** afterwards. The interesting version is the
  constraint.

## Stage 2 — Brief the agent

**Target.** The person's own assistant gets enough context to plan for *them* rather than for a
generic eater.

**Today.** This mostly works. `/profile/` generates the workspace file set and `mealPlanPrompt`
(`src/lib/shared/workspace-docs.js`) builds a prompt embedding the meals — each with its slots, prep
minutes and cook minutes — plus every answered preference, and points the assistant at
`meal-plan.md`. Free text is quoted, fence-stripped and capped. Contract: `docs/assistant-workspace.md`.

**Missing.** The new Stage 1 answers, and whatever Stage 3 needs the assistant to know about asking
questions back.

## Stage 3 — The agent interviews you back

**Target.** The assistant's **first** reply is a list of questions for the person — the things no
questionnaire can anticipate: what is already in the freezer, who is away next week, whether the
oven works, what nobody wants to eat again for a while.

**Today.** Nothing. `mealPlanPrompt` asks for the menu in one shot and ends *"end with exactly one
JSON code block"*, which actively discourages the assistant from asking anything first.

**This is the stage that makes the feature good**, and it is the one with no code behind it. Two
shapes:

1. **Prose interview.** The prompt tells the assistant to ask its questions in plain language before
   drafting anything. The person answers in the chat; nothing comes back to the app until the menu
   does. Costs almost nothing to build — a prompt change — and the answers are lost to the app.
2. **A question document.** The assistant returns a small validated document (`kind:
   "meal-plan-questions"`), Fork Knife renders it as a form, and the answers are saved to the profile
   and folded into the next prompt. Costs a schema, a classifier branch, a page and a round trip —
   and makes the interview repeatable, inspectable and part of the person's record.

Shape 2 fits the project's grain: the classifier (`classifyAssistantDocument`,
`src/lib/shared/workspace-docs.js:162`) already dispatches on `kind`/shape and already knows
`"meal-plan"`, so a new kind is a small, well-precedented addition. Shape 1 is the honest first
step if the interview turns out to need iteration before it needs machinery.

## Stage 4 — What comes out

**Target.** A menu **with recipe options**, a **meal-prep schedule**, a **cooking schedule**, a
**shopping schedule** and a **shopping list**.

**Today.**

- **Menu** — exists and is contracted. `docs/meal-plan.md` + `data/schema/meal-plan.schema.json`:
  `{schemaVersion, kind: "meal-plan", source, items[], notes}` where each item is
  `{meal, dish, days[1–2], leftoversMeal, notes}`. About eight dishes cover fourteen days; the second
  serving is never the next day and at most three days later, wrapping past the end of the fortnight;
  one dish per meal per day; leftovers may cross to an earlier meal, never a later one. Built by hand
  on Spoon Feed (`/forkknife/spoon-feed/`) or applied from the assistant.
- **Prep and cooking tasks** — exist, derived rather than authored: `scripts/fk_core/meal_plan.py` ↔
  `src/lib/shared/meal-plan.js` turn the menu plus each meal's `needsPrepped` / `needsCooked` /
  `prepMinutes` / `cookMinutes` into the tasks Fork Knife's Overview shows.

**Missing.**

- **Recipe options.** Nothing in the schema holds a recipe — `dish` is a string. "Options" implies
  more than one candidate per slot, which is a shape question, not just a field.
- **Shopping schedule and list.** No contract at all; `shoppingCadence` is asked and then used only
  as a line in the prompt. This is where location and budget finally pay off.

**Decisions to make.**

- **Recipes: referenced or inline?** A `recipes[]` array keyed by id, with menu items pointing at
  ids, keeps a dish that recurs from being written twice and lets several options hang off one slot.
  Inline is simpler and duplicates.
- **How much recipe?** Ingredients and quantities are needed for the shopping list to be derivable;
  method is what makes the document large. The list is the reason to hold ingredients at all.
- **Shopping list: derived or authored?** Derivable from recipes + quantities + eaters, the way tasks
  are already derived from the menu — which is the project's grain, keeps one source of truth, and
  means the assistant supplies ingredients rather than a list. Authored is easier and drifts.
- **Shopping schedule** should fall out of `shoppingCadence` + the fortnight, but it interacts with
  leftovers: a shop has to land before the first serving of everything it buys.

## Stage 5 — Landing in FortKnight

**Target.** All of it on the agenda: cook Tuesday, prep Sunday, shop Saturday morning.

**Today.** The path exists and is the one to reuse. Fork Knife's Overview already emits its prep and
cooking tasks as a **version 2 import document** that the person applies on the Assistant page
(`docs/importers.md`, `data/schema/import.schema.json` — `tasks`, `mealPlan`), which is how food work
reaches the day pages. `classifyAssistantDocument` routes the document by shape.

**Decisions to make.**

- **One document or several?** The chain's outputs are one plan, but they have different lifetimes: a
  menu is replanned each fortnight, a recipe is reusable, a shopping list is consumed once. Bundling
  everything into one import is simplest to apply and worst to re-edit.
- **Which parts become schedule?** Shopping and cooking are timed work and belong on the agenda.
  Recipes are reference material and probably should not be.
- **Re-application.** Applying a second plan over a first must replace the food tasks, not accumulate
  them — the existing importer semantics need checking against that before the chain doubles the
  volume of what it writes.

---

## Cross-cutting

**Versioning.** `meal-plan` is `schemaVersion 1` and shipped. Recipes and shopping are additive, so
the cheap route is optional fields on version 1 plus a new document kind for shopping; the honest
route, if the menu itself must change shape, is version 2 with the normalizer accepting both. Decide
before writing, not during.

**One source of truth.** Prep and cooking tasks are *derived* from the menu today. Keep that: every
new output should be derived from the smallest authored input that can produce it, and the assistant
should be asked for inputs (ingredients, quantities, timings) rather than for outputs it computes
badly.

**Delivery — getting files on and off a phone (open).** The whole flow assumes a person can move
files between the app and their assistant, which is awkward on a phone. Claude's **Cowork** is a
candidate answer, and a Cowork-centred flagship is one option on the table. The trade-off to weigh:
it would tie the assistant flow to one vendor, against the umbrella thesis's *bring your own model*
position (`docs/thesis.md`), and the app's current stance — no credentials, no LLM calls, anything
that validates against the schema is accepted — is what makes the file-shuffling honest in the first
place. **No design is committed to this.** Worth checking what Cowork actually offers for file in and
out on a phone before deciding anything; the same question applies to FortKnight (`docs/fortress.md`).

## Appendix — the map, as stated

The source for this document, lightly tidied (shorthand and typos cleaned; wording and meaning
otherwise untouched):

> Fork Knife is getting fleshed out next. The company, the game studio, and FortKnight all have big
> future maps, but Fork Knife is a simple concept. Simple but difficult. It will ask the user a series
> of questions about location, meals, workload, time constraints etc. that will build docs for an
> agent to **also** give the user a list of questions to answer before popping out a menu with recipe
> options, meal prep schedule, cooking schedule, shopping schedule and list. These can be plugged
> into FortKnight and added to your agenda. That is what I am going to work on next.
