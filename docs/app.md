# The app (frontend-only)

There is no backend. A client (web today; iOS/Android later) ships with `build/fortknight.bundle.json`
and stores everything user-specific on the device. The web frontend, the data, the Python tooling and
the canonical JS modules are all in **this** repository (`insiculous_web` — beinsiculous.com).
(The zero-install legacy viewer was removed on 2026-08-16; the two faces moved onto beinsiculous.com
on 2026-08-17, and the FortKnight repository that had stayed canonical for the data was folded in
here on 2026-08-18 — one project, one repo, no sync step.)

**Deployment status.** On production (`main`), FortKnight's seed-fed pages are live: the Overview
(`/fortknight/`), **Keep** (`/fortknight/keep/`) and the fourteen day pages
(`/fortknight/days/<dayKey>/`), all reading a keep the visitor loads from their own device
(next section), plus **Achievements** (`/fortknight/achievements/`), which reads the site's
achievement store instead of the seed and shows the active profile's unlocked fortnight
achievements. The studio side gains `/achievements/`, the every-achievement board (below).
`/fortknight/build/`, `/fortknight/questionnaire/` and `/fortknight/assistant/`
remain `src/components/FaceInDevelopment.astro` placeholders, and Fork Knife's routes
(`/forkknife/*`) were removed from the site on 2026-08-28 — its menu rendering will land under
`/fortknight/` when the seed carries menu rows. The face branches `fortknightdev` and
`forknifedev` were re-ruled the back-burnered creation chain's playgrounds on 2026-08-28 — never
absorbed, never merged; seed-fed pages are built fresh in the `main` lineage (`docs/roadmap.md`).
The profile-driven body below stays as-is: it is the contract that chain was built against, and it
applies again if the chain returns from the back burner.

## The seed-fed pages: Overview, Keep and the day pages

The live face routes are neither placeholders nor built from a profile. They render a **Keep
seed**: a small file the private **Fortress Key** phone app exports
(`focuskey/src/lib/keep.js`), carrying fourteen day keys with their meals, appointments and
block shapes, plus a season card and a year wheel.

**The format is written down.** `docs/keep-format.md` is its specification, written for a person
making a keep by hand in a text editor, and `data/schema/keep.schema.json` is the machine schema.
Both are canonical here rather than in the private app repository, because a hand-maker cannot see
that one. This section describes what the pages do with a keep; the format's own rules — the
fourteen canonical day keys, what a keep should omit, why adding a field is not a version bump —
live in the spec and are not restated here.

- **Three pages, one seed.** `/fortknight/keep/` draws the whole fortnight — fourteen day panels,
  the season card and the year wheel — and sits in the face nav (`src/lib/faces.js`). With no seed
  stored, `/fortknight/` keeps its thesis front-door content and its primary action is **Load your
  seed** (to `/fortknight/keep/`); with a seed stored it renders a compact fortnight grid linking
  to the day pages. Each `/fortknight/days/<dayKey>/` page renders that day key's blocks, meals and
  appointments, falling back to the load-your-seed message. The rendering is factored into
  `src/lib/keep-view.js` — season colours come from a **positional palette** (position pinned to
  first appearance in `year.slices`), never keyed to a household's season ids — and the stored-seed
  boot logic is shared by all three pages.

- **The visitor loads their own file.** It is kept in `localStorage` under
  `beinsiculous.keep` (`src/lib/keep-store.js`), deleted from `/profile/`, and **never
  uploaded**. It is stored under its own key, separate from the profile, so neither document can
  migrate into the other.
- **The pages resolve nothing.** The seed arrives pre-joined by day key. This is deliberate rather
  than lazy: Fortress Key anchors every season on `sun-a` and has transition weeks, while
  `fk_core/dates.py` and `src/lib/shared/fortknight-rules.js` still evaluate the archived `sun-b`
  starts for Ostara and Fimbulsumar — so **running this repository's date evaluator over a Keep
  seed would be wrong for half the year.** `src/lib/keep.js` validates and the pages draw.
- **Validation is tolerant within a major version.** Unknown fields are ignored and only a *higher*
  `meta.version` is refused, because the two halves ship on different cadences and the person holding
  the phone cannot redeploy the website. Fortress Key's side of that bargain: the version bumps only for
  a breaking change, so adding a field is not a bump.
- **A keep is somebody's real schedule and must never be committed here.**
  `scripts/fk_core/no_schedules.py` enforces it, `validate.py` runs it, and the exact-path
  exemptions are `tests/fixtures/keep.sample.json` — invented, and loaded by `a11y-check.mjs` so axe
  audits a page with fourteen real panels instead of an empty file picker — and
  `tests/fixtures/keep.other-household.json`, a second invented household the rendering tests use for
  the year wheel's positional colours.

The earlier gaps are closed: Keep is in the face nav, the season colours are positional rather
than keyed to Jesse's season ids, and the face branches no longer matter to these pages —
`fortknightdev` and `forknifedev` were re-ruled the creation chain's playgrounds on 2026-08-28,
never absorbed or merged, and **seed-fed pages are built fresh in the `main` lineage** (see
`docs/roadmap.md`).

## The site
beinsiculous.com is one Astro 7 build, deployed to Cloudflare as a static-assets Worker. It carries two surfaces
that deliberately look like two different websites:
the **Be Insiculous studio** (`/`, `/games/`, `/achievements/`, `/devlog/`, `/engine/` — its own `BaseLayout.astro`),
and the FortKnight planner face under `FaceLayout.astro`, with its own skin.

Multi-page, no UI framework. `npm install` once, then:
- `npm run dev` / `npm run build` / `npm run preview`; `npm run data` (= `validate.py` then `build.py`)
  after any change under `data/`, and `npm run verify` for everything CI gates on.
- **One copy of everything.** `build/fortknight.bundle.json` is generated by `scripts/build.py` and
  committed; the static pages import it directly and `src/pages/bundle.json.js` re-serves it at
  `/bundle.json` for the pages that fetch it on the client, so the served bundle can never drift from
  the rendered one. The assistant-workspace documents (`WORKSPACE_STATIC_DOCUMENTS` in
  `src/lib/shared/workspace-docs.js`) are imported straight from `docs/` and `data/schema/` by
  `src/lib/workspace-static-texts.js`. The canonical JS modules live in `src/lib/shared/` — the same
  files `tests/helpers.py` drives through node to check them against their Python twins.
- **One face live, one profile** (`src/lib/faces.js`, `FaceLayout.astro`): **FortKnight** under `/fortknight/`
  (🏰🛡️: the fortnight schedule) is the live face, with the six-page menu **Overview · Keep ·
  Achievements · Build · Questionnaire · Assistant** — Achievements boarding the active profile's
  unlocked fortnight achievements. **Fork Knife** under `/forkknife/` (🍴: the fortnight menu) had its routes removed on
  2026-08-28, and everything about it in this bullet — and the profile-driven FortKnight pages in the next two —
  is the parked creation chain's design, kept here as its contract. That design gave each face the same
  four-page menu **Overview · <its building page> · Questionnaire · Assistant**, where the building page is the one
  that adds things by hand and is named for its face — Fork Knife's **Spoon Feed** (`/forkknife/spoon-feed/`) and
  FortKnight's **Build** (`/fortknight/build/`), both declared as `FACES[face].build` in `src/lib/faces.js` and
  assembled by `faceNav()`; the shared **Profile** page at `/profile/`. `/` is the
  Be Insiculous studio home, not a face. The header's switcher sits left of the brand: the **studio button** (💧,
  `STUDIO.logo` in `src/lib/faces.js`) back out to the studio site. Every page takes a
  `face` prop (`fortknight` | `fork-knife` | null on Profile), and the face decides the page's skin and tab icon
  (`FACES[face].theme` / `.favicon`) — so the face and the studio read as two different websites. Profile
  belongs to neither, so it takes the studio's: `DEFAULT_THEME` is a third theme id, `studio`, whose skin lives
  in the site's own `src/styles/studio-skin.css` (`themes.css` is mirrored from this repo and knows only the one
  face), and its chrome is the studio's too — the `be_insiculous` wordmark, a `STUDIO_NAV` of Games ·
  Achievements · FortKnight,
  the studio `beinsiculous.jpg` tab icon, and no emoji switcher, those two links already going everywhere it went. Both faces read and write the same on-device profile (one localStorage, one `settings.weightsProfiles`) —
  each face's questionnaire is its settings, and each of the four writing pages saves only its own answer keys over
  the profile *as stored at save time* (`pickAnswers` in `weights-rules.js` over the key sets named in the site's
  `src/lib/answer-keys.js`: Spoon Feed owns `mealPlan`, Build owns `mealPlan` + `standingAppointments` + `tasks`,
  Fork Knife's questionnaire owns `FORKKNIFE_ANSWER_KEYS`, FortKnight's owns the rest), so none wipes another's,
  whatever tab or page saved last. Once a profile is saved on the device the top right shows the **profile dropdown** (every saved
  profile, the active unsaved one marked, and *New profile…*: switching makes that profile active and reloads the
  page, *New profile…* prompts for a name and opens the current face's Questionnaire — `data-questionnaire-href`;
  `FaceLayout.astro` re-renders it on the `fortknight:settings-saved` event that Save and Apply dispatch, and a page with
  unsaved edits can veto a switch by cancelling `fortknight:profile-switch`) and a **⚙ Profile** link. Old URLs keep
  working through meta-refresh stubs: `/fortknight/settings/` → `/profile/`,
  `/fortknight/allocations/` and `/fortknight/fortnight/` → `/fortknight/`, `/fortknight/ask/` → `/fortknight/assistant/`.
- FortKnight pages (the parked design — the live Overview and day pages are the seed-fed ones of the previous section): `/fortknight/` **Overview** — the fortnight grid + date resolver (navigates to the resolved day) and, below it,
  time by category (bars rendered from the active profile by `src/lib/shared/allocations-rules.js` — the "Weights"
  view always, the "Focus grid" view once the profile has a grid, "Proposed grid" for the generator's proposal
  recomputed for the resolver's date) — **rendered from the
  person's settings**: the prerendered cards carry the bundle's days only as no-JS /
  pre-hydration fallback (day keys and `—` on the neutral data; a `<noscript>` note says so); the client replaces every card's focus line
  and chips from the active profile's weights (`activeWeights(settings)`; or, on a fresh device / a save from before this version,
  weights derived on device from the saved answers or the typical-person defaults —
  `userWeightsFromAnswers`): one chip per focus block of the person's day (a `flexible` block shows
  no header), the focus from `weights.blockFocusGrid` (the person's own grid — an adopted proposal — or the
  import applied on the Assistant page; `—` until either exists), `•` on standing appointments and imported
  appointment blocks, an "appointments" tag on the appointment weekdays, and a day-focus line when one focus
  leads the day outright. A **Your grid / Proposed grid** switch shows the generator's proposal
  (`docs/generator.md`, recomputed on the page for the season of the resolver's date; differing cells outlined,
  reason in the tooltip, *Why each cell* lists them all with the warnings); **Use this grid** writes it to
  `answers.blockFocusGrid`, re-derives and saves the active profile; **Drop your grid** removes it again;
  `/fortknight/days/<dayKey>/` (14 day pages: a prerendered shell — label, week, weekday — and a body rendered
  from the active profile by `src/lib/shared/day-plan.js`: the person's blocks with the imported focus and
  appointment block, the generator's proposed activities for that day (`docs/generator.md`, generated live for
  the person's own grid — or the proposed grid when they have none, the note says which — listed with a
  ` · proposed` suffix; *Show proposed activities* hides them for the session), the imported fixed activities of that day key (placed by their `block`, else by
  start time, else listed "outside your blocks"), the standing appointments landing on it, the Fork Knife menu line
  and the menu line from the import's `meals`; "no import applied yet" otherwise), `/fortknight/questionnaire/` — **the questionnaire is the answers**:
  the form rendered from `bundle.questionnaire` — the sections without a `face` (Startup, Your day and year,
  Your week, Focus, About you; typical-person defaults, one collapsible row per
  category whose slider scales its subjects, live share + block-split preview, Startup Q2 no longer holds the
  commitments and tasks editors — they are the Build page's — but still counts what the profile has and links to the
  two ways in, by hand on `/fortknight/build/` or uploaded on the Assistant page, and still shows what that page
  applied (`docs/importers.md`)); each question renders through
  `components/QuestionField.astro` (the wrapper + the simple kinds `number`, `multi-select`, `single-select`, `text`,
  `meals`; the page's bespoke kinds go in as its slot; `src/lib/question-fields.js` reads/populates the simple kinds), a profile line above the form naming the active profile and whether it is saved (several
  saved answer sets, one active — "User settings" below; switching lives in the nav dropdown); a settings file is applied via the Assistant page (*Apply from assistant*); a stored
  cycle-anchor override is shown with a *Clear it* link only while one exists — it bends the date
  resolver, not the questionnaire's derivation; Save derives the active profile's weights file
  (`settings.weightsProfiles[activeWeightsId]`), Download gives `weights.<id>.json`, Reset touches only this page's
  answers; `/fortknight/assistant/` — *Apply from assistant* in two steps — 1: get the JSON from your assistant (the
  spreadsheet guide + a copyable prompt), 2: `components/ApplyFromAssistant.astro` (shared with Fork Knife's assistant
  page: paste it and Apply — an import document, a meal-plan document, a weights or a settings file — then read the
  review; the component fetches the bundle itself, `data-face` picks its links) — the component is deleted on `main`
  with the rest of the chain and now lives only on the parked `fortknightdev`/`forknifedev` playground branches; `/fortknight/build/` — **Build**, the
  page that puts things into a profile by hand: the commitments that anchor the day's blocks and the tasks that land
  on the day pages (one entry row each, *Add* commits it into a compact read-only list, *Edit* only reveals remove),
  and the same fortnight-menu editor Spoon Feed carries. Save writes `standingAppointments`, `tasks` and `mealPlan`
  over the stored profile and re-derives, which is what turns the commitments back into `blockSplit.anchors`.
- Fork Knife pages (the parked design — these routes are removed from the live site) (`docs/meal-plan.md`): `/forkknife/` **Overview** — the fortnight menu as the 14-day grid
  (`components/MenuDayCard.astro`: one line per meal per day from `menuForDay`, leftovers marked, rotated to the
  person's week start; each card links to the FortKnight day page), the coverage per meal, and **the meal-prep and
  cooking tasks** the menu implies as an import document (Copy / Download; every other week from the next date of each day)
  to paste into the Assistant page, step 2; `/forkknife/spoon-feed/` — **Spoon Feed**, the **fortnight menu** editor:
  per meal the dishes and the day(s) they are eaten (first serving + an allowed leftovers day: never the next
  day, at most three later, the fortnight wraps; leftovers of an afternoon/evening meal may become an earlier meal —
  the leftovers dropdown offers "as Breakfast"; one dish per meal per day — servings already in the plan leave the
  dropdowns; coverage per meal). One implementation, the site's `src/lib/meal-plan-editor.js` +
  `components/MealPlanEditor.astro`, which FortKnight's Build page renders too — both deleted on
  `main` with the rest of the chain and now living only on the parked `fortknightdev`/`forknifedev`
  playground branches; Save writes only `mealPlan`.
  `/forkknife/questionnaire/` — **Fork Knife's questionnaire is its settings**:
  the `face: "fork-knife"` section of `bundle.questionnaire` (the meals question — names, when each is eaten (1–2 times
  of day), prepping/cooking + minutes — and the meal preferences: eaters, dietary rules, allergies and dislikes,
  cuisines, favourite dishes, cooking skill, budget, kitchen kit, shopping cadence). The menu is Spoon Feed's, but
  this page still carries it: renaming a meal retags its dishes and lowering the meal count drops the dropped meal's
  dishes with a note — applied at save time to the plan **as stored right then**, never a load-time snapshot, so a
  save here cannot undo a dish added on Spoon Feed meanwhile. Save writes `meals`, the preferences and that carried
  `mealPlan` over the stored profile (the day pages' menu line, the generator's meal titles);
  `/forkknife/assistant/` — step 1: **Copy the prompt**
  (`mealPlanPrompt` in `workspace-docs.js`: the person's meals with slots and minutes plus every answered preference —
  option labels, free text quoted with fences stripped — asking for a meal-plan document), the `meal-plan.md` contract
  row and the **template** (the document shape with the person's meals filled in); step 2: the shared Apply.
- Static hosting: the face is a path under `beinsiculous.com/`, sharing the origin with the Be Insiculous
  studio pages; one `dist/` tree carries all of it and is deployed as a static-assets Cloudflare Worker
  (`wrangler.toml`) by the site repo's GitHub Actions workflow on every push to its `main` — type-check and build
  first, so a broken build cannot ship; `npm run deploy` there is the gated manual equivalent. Profiles survive every such move because localStorage is origin-scoped. `withBase()`
  (`src/lib/paths.js`) still routes every in-app URL through Astro's `BASE_URL`, so a sub-path build stays possible.
- Settings live in one localStorage file (`fortknight.user-settings`). The face's skin: **fort-knight** — the
  treehouse on the left, the knight by the campfire on the right, a generated composite of two Unsplash photographs
  in `public/app/images/`, dark. (The **fork-knife** skin — the butcher's-block flat-lay — went with the routes.)
  Credits in `public/app/images/README.md`. FortKnight also
  swaps the three mouse cursors (wooden arrow / sword / shield).
- Theme identities (fonts, textures, palettes) live in one `public/app/shared/themes.css`, linked by
  `FaceLayout.astro`; the skin uses a system font stack, so nothing is vendored under `public/app/fonts/`
  today, but a theme can vendor a webfont by dropping it there and referencing it as `url(../fonts/…)`.
  The cursor `url()`s live in `src/styles/faces.css` instead, because they resolve relative to
  `src/styles/`.

## Shared modules (`src/lib/shared/`)
Plain ES modules with no build step (the root `package.json` marks the repository `"type": "module"`,
so node imports them directly — `tests/helpers.py` drives them that way): `fortknight-rules.js` (the JavaScript port of
`fk_core/dates.py` — keep them in sync), `weights-rules.js` (of `fk_core/weights.py`), `import-document.js`
+ `clock.js` (of `fk_core/import_document.py`), `astronomy.js`, `user-settings.js`, `workspace-docs.js`,
`day-plan.js`, `allocations-rules.js`, `allocation-bars.js`, `import-review.js`, `download.js`; plus
`themes.css` (at `public/app/shared/`, linked by `FaceLayout.astro`) and `cursors/` (at
`src/styles/cursors/`, inlined by Vite from `faces.css`). Each of these is the only copy — edit it in place.

## User settings (`data/schema/user-settings.schema.json`)
```json
{
  "schemaVersion": 3,
  "theme": "fort-knight",
  "epochOverride": null,
  "timezone": null,
  "activeSeasonId": null,
  "weightsProfiles": {"lucky-garden-poet": {"id": "lucky-garden-poet", "questionnaire": {"answers": {}}, "…": "…"}},
  "activeWeightsId": "lucky-garden-poet",
  "hidden": [],
  "overrides": {},
  "added": [],
  "dayNotes": {}
}
```
`weightsProfiles` are the **profiles** this device keeps — one saved set of answers each (a person
on a shared device, or one person's alternative), keyed by weights id (`weights.schema.json`; each
profile's `id` equals its key, kebab-case, immutable once created); `activeWeightsId` names the one
in use — FortKnight's Overview, the assistant workspace and *Apply from assistant* all read and write
that one (`activeWeights(settings)` in `src/lib/shared/weights-rules.js`; null while a freshly created
profile has not been saved). The questionnaire answers ride inside each profile at
`questionnaire.answers` and are the source of truth — the app re-derives the weights from them on
every save/import. Device extras (`epochOverride`, `timezone`, …) are device-wide, not per profile.
Nothing secret lives in the file, so export is never redacted.

A device with no saved profile shows a generated `[Adjective]-[Noun]-[Title]` name —
`lucky-garden-poet` — instead of a shared placeholder: the tables live in
`src/lib/shared/profile-names.js`, the name is rolled once and kept under the
`fortknight.default-profile-id` key, and `loadSettings` applies it wherever nothing is saved and the
active id is still the bare fallback. That covers a device that has never visited, a version 2 record
whose `weights` was null, and the reload after the last profile is deleted — so an existing device
sitting on an unsaved `username` picks up a generated name on its next load too. `DEFAULT_WEIGHTS_ID`
stays `username` as the deterministic fallback for an unnamed imported file, which keeps
`migrateSettings` pure.

Naming happens in one dialog (`src/lib/profile-name-dialog.js`, the site's only `<dialog>`): a name box, a
**Regenerate** button that rolls another generated name, and a confirm button. It is used by both
questionnaires, Build, Spoon Feed, Apply from assistant, *New profile…* and *Duplicate as…*. **Cancel appears
only where it would mean something** — the create paths, where nothing exists until a name comes back. After
a save the profile is already written, so there is nothing to cancel and the button is absent; Escape closes
the dialog and keeps the generated name. A name already in use keeps the dialog open with the reason, rather
than closing and reporting it elsewhere. `showModal()` supplies the focus trap, Escape and focus restore.

The nav's profile dropdown (shown once a profile is saved) switches profiles and creates new ones
(*New…*, an unsaved slot showing typical defaults until the questionnaire is saved — the id survives page
loads); the first Save of an unsaved profile (the generated default included) opens the naming dialog; the
Profile page renames (the name field first on the page: the id changes with it — `renameProfile` moves the
saved answers under the new id, the active id follows), with *Regenerate* beside it dropping a fresh
generated name into that field, which Rename then takes. It also copies (*Duplicate as…*) and deletes the
active one (the last one included — the
device is then back to a blank, unsaved default) — operations in `src/lib/shared/user-settings.js`; leaving the
questionnaire with unsaved edits triggers the browser's leave-page prompt. Names are slugified into ids
(`slugifyId`).

Migration (`migrateSettings()` in `src/lib/shared/user-settings.js`, on load and on import): version 1
files (`weightsProfiles` + `activeWeightsId`, an `aiProvider` block with an API key) keep all their
profiles and lose the AI block; version 2 files (a single `weights`) become one profile under its
id (`username` when unnamed — the deterministic fallback, not the generated name). Every profile key is
normalised to a kebab-case id; a missing `activeWeightsId`
falls back to the first profile (one that names no saved profile is kept — a profile started and not saved yet). The migrated record is written back at once and
the pre-migration record (minus the AI block) is kept under its own key,
`fortknight.user-settings.v<N>-backup` (never reused across versions); on the v2 → v3 step the
profiles that the earlier v1 → v2 collapse parked in the v1 backup are added back when their id is
free — lossless, and the person can delete them. Newer-than-known records are read through, never
rewritten.
Resolution order
when rendering: bundle → `epochOverride` (else season-anchored: the person's own seasons from the
saved answers — `personCalendarFromSettings()` in `src/lib/shared/weights-rules.js`, their year split +
week start — when one of them has started by that date, else FortKnight's seasons; the resolver
reports `seasonSource`) → `hidden` / `overrides` / `added` activities → `dayNotes` for the concrete
date. The bundle is never mutated. The fortnight grid on `/` starts on the person's week-start
weekday (a display rotation, `dayKeyOrderStartingOn`; the canonical day-key order never changes).
