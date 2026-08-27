# Roadmap

Why these choices and what each surface argues: `docs/thesis.md`.

**Scope.** This file tracks the planner — the two faces in this repository. Insiculous 2D and the
games are separate repositories and are tracked there; the game-studio section at the foot records
only what touches beinsiculous.com.

Done (this pass): workbook → canonical JSON, schemas, validator, builder, allocations/baseline
weights, date resolver, the web app, questionnaire-as-settings, assistant workspace (files for the
person's own AI workspace + apply-back), docs, tests.

**Shipping status.** The face apps are built on the `fortknightdev` and `forknifedev` branches and
ship when each merges into `main`; until then the face routes on the live site are
`FaceInDevelopment` placeholders (see `docs/app.md`, "Deployment status"). "The web app" above is
done as code on those branches, not yet on production.

Next, roughly in order:
1. **Questionnaire** → `weights.<id>.json` — done for the draft questions (`docs/questionnaire.md`,
   `/fortknight/questionnaire/` in the Astro app, `scripts/questionnaire_to_weights.py`). Open: naming
   decisions, the unscheduled-block vs fixed-blocks question, uploads (→ importers), Fortress
   multi-user model (done since: named settings profiles per device, one active — `docs/app.md`
   → User settings; still open: sharing a profile between devices without a server). Done since: computable
   section start rules + week start (a person's year split is their own seasons; `/`, `/days/` and
   `resolve_date.py --answers` resolve by them). Follow-ups: rules for the vague preset markers
   (semesters, most of the Norse wheel — an assistant can infer them), season focus/menus for a
   person's seasons, and re-snapping stored rules when `weekStart` changes. Done since: `/` renders
   from settings (the person's blocks + the block focus grid they imported), Agenda scope
   (Focus 6). Done since (empty baseline): `data/` is person-neutral (no activities, menus or focus
   grid — the workbook lives on as the `examples/workbook/` overlay), the import document is applied on the Assistant page
   (`build/derived/defaultImport.json` is the empty example), `/days/<dayKey>/` and the Overview (`/`)
   render from the active profile (imported fixed activities per day, standing appointments, the
   import's `meals` as the menu line; weights + imported grid). Done since (2026-08-17): the site has two faces sharing one profile — FortKnight under `/fortknight/`, **ForkKnife** under `/forkknife/` with its own Overview (menu grid + tasks), Spoon Feed (the menu editor), Questionnaire (meals + meal preferences) and Assistant page (a copyable menu prompt built from the answers, `meal-plan.md`, a template) — and the shared `/profile/` (`docs/app.md`, `docs/meal-plan.md`). Follow-ups: shopping lists from the menu; season menus as a source for the plan.
2. **Generator**: weights (+ imported fixed activities + season) → proposed `blockFocusGrid` and activities; validate; diff against the imported grid. Done since (grid half, `docs/generator.md`): `fk_core/generator.py` / `src/lib/shared/generator-rules.js` propose the grid, `weights.proposal` carries it with reasons + diff, `/` shows *Your grid / Proposed grid* and adopts it into `answers.blockFocusGrid`, `scripts/generate_grid.py`. Done since (activities half): `generate_activities` / `generateActivities` propose subject sessions, practices and meals inside the cells (`proposal.activities`, `placedMinutes`; the day pages show them live). Open: season focus for a person's own sections, a goal ramp from `currentMinutesPerDay`, peripheral subjects as occasional tasks, editing a proposal cell by cell, `meals` slots as anchors for the block split.
3. **ForkKnife's full chain** (`docs/forkknife-chain.md`) — **the next thing being built.** Questions
   (location; workload and time constraints *read from* FortKnight rather than re-asked) → a brief for
   the person's own assistant → **the assistant interviews them back** (the one stage with nothing
   behind it today: `mealPlanPrompt` asks for the menu in a single shot) → menu with recipe options,
   meal-prep schedule, cooking schedule, shopping schedule and shopping list → applied into
   FortKnight's agenda through the existing version-2 import document. This promotes the old
   one-line "shopping lists from the menu" follow-up into a designed chain. Open shape decisions
   (recipes referenced vs inline, shopping list derived vs authored, one document or several) are in
   that doc; `docs/meal-plan.md` and `meal-plan.schema.json` stay the shipped contracts and do not
   change until a piece of this is actually built.
4. **Season menus** for Ostara, Fimbulsumar, Christmas, Hogmanay (one file each in `data/menus/`), and filling `outdoorWindow.uvAbove4`.
5. **Importers** (`scripts/importers/`, `src/lib/shared/importers/`, contract in `docs/importers.md` + `data/schema/import.schema.json`): an Import page that turns `.xlsx` / `.ics` into an import document with deterministic parsers (free text and photos go through the person's assistant workspace); Google Calendar (user OAuth, read). *Apply from assistant* already accepts the document, and the Build page lists what it brought in. Then **exporters** to push plans to a calendar.
6. **Assistant workspace follow-ups** (`docs/assistant-workspace.md`): `scripts/export_workspace.py` (stdlib) writing the same file set from `data/` + `build/` + a settings file, with a parity test against `src/lib/shared/workspace-docs.js`; a zip only if a workspace turns out to need one. Done since: the import document is written for the person (version 2: readable commitments, tasks, skipped, review — `docs/importers.md`) and a read-only review of what landed shows after Apply; still open: editing that review before applying.
7. **Native clients** (iOS/Android) reading the same bundle and settings schema and producing the same assistant-workspace file set.
8. **Forts and the Fortress** (`docs/fortress.md`) — a real login; per-person attribution of category
   minutes inside a household (**fort**) and across a community of them (**fortress**); the four roles
   (Knight, Royal, Champion, Commander); the bulletin boards and shared calendars, where the Fortress
   public board is the only social-media surface in the project. Recorded as **unresolved**: a login is
   the first time this project would hold anyone's data on a server, against the no-backend claim in
   `docs/thesis.md`, and the three options (identity only / shared fort record / full sync) are laid
   out there rather than decided. Startup Q1 — `groupSize`, "Groups stay on one device for now — one
   profile per person" — is the seam a fort replaces.
9. Track the "Open for Appointments (Tuesday A, early)" vs week-1 appointment block = midday question with the owner.

## Open, not tied to an item

- **Getting files on and off a phone (Cowork).** The assistant flow assumes a person can move files
  between the app and their AI workspace, which is awkward on a phone. Claude's Cowork is a candidate
  answer and a Cowork-centred flagship is one option on the table — weighed against the
  bring-your-own-model position in `docs/thesis.md`, since it would tie the flow to one vendor.
  Nothing is designed around it. See `docs/forkknife-chain.md` (Delivery) and `docs/fortress.md`.

## The game studio (tracked in its own repositories)

- **Web export.** WebAssembly builds embedded on `/games/`; the embed slots on this site stay
  placeholders until the engine ships it.
- **The two tracks and the art policy** (`docs/thesis.md` is the source of the wording). The games
  listed on this site are free and use AI art. The games we **sell** are not on this site at all —
  each has its own repository and ships on Steam and/or Android and iOS — and they carry no AI art.
  Maintenance condition: the blanket sentence on `/games/` is true only while *every* game listed
  there uses AI art; the first one that does not makes it false, and per-game labelling has to ship in
  the same change.
- **Store links.** When the first paid game ships, this site needs somewhere to point at it — the
  games page is currently built around on-site listings only.
