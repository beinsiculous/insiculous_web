# Roadmap

Done (this pass): workbook → canonical JSON, schemas, validator, builder, allocations/baseline
weights, date resolver, the web app, questionnaire-as-settings, assistant workspace (files for the
person's own AI workspace + apply-back), docs, tests.

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
3. **Season menus** for Ostara, Fimbulsumar, Christmas, Hogmanay (one file each in `data/menus/`), and filling `outdoorWindow.uvAbove4`.
4. **Importers** (`scripts/importers/`, `src/lib/shared/importers/`, contract in `docs/importers.md` + `data/schema/import.schema.json`): an Import page that turns `.xlsx` / `.ics` into an import document with deterministic parsers (free text and photos go through the person's assistant workspace); Google Calendar (user OAuth, read). *Apply from assistant* already accepts the document, and the Build page lists what it brought in. Then **exporters** to push plans to a calendar.
5. **Assistant workspace follow-ups** (`docs/assistant-workspace.md`): `scripts/export_workspace.py` (stdlib) writing the same file set from `data/` + `build/` + a settings file, with a parity test against `src/lib/shared/workspace-docs.js`; a zip only if a workspace turns out to need one. Done since: the import document is written for the person (version 2: readable commitments, tasks, skipped, review — `docs/importers.md`) and a read-only review of what landed shows after Apply; still open: editing that review before applying.
6. **Native clients** (iOS/Android) reading the same bundle and settings schema and producing the same assistant-workspace file set.
7. Track the "Open for Appointments (Tuesday A, early)" vs week-1 appointment block = midday question with the owner.
