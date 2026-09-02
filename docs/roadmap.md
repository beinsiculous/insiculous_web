# Roadmap

Why these choices and what each surface argues: `docs/thesis.md`.

**Scope.** This file tracks only what is specific to *this repository* — FortKnight's web surface
and the parked Fork Knife chain's documents, and the studio pages. The Fort Knight plan itself
lives in the working set (below).
Insiculous 2D and the games are separate repositories and are tracked there; the game-studio section
at the foot records only what touches beinsiculous.com.

Done (this pass): workbook → canonical JSON, schemas, validator, builder, allocations/baseline
weights, date resolver, the web app, questionnaire-as-settings, assistant workspace (files for the
person's own AI workspace + apply-back), docs, tests.

**Shipping status.** `main` is production. FortKnight's keep-fed pages are live — the Overview
(`/fortknight/`), Keep (`/fortknight/keep/`) and the fourteen day pages
(`/fortknight/days/<dayKey>/`), all reading a visitor-loaded keep — as are the achievements boards:
the studio's `/achievements/`, listing every achievement the site knows, and the face's
`/fortknight/achievements/`, the active profile's unlocked fortnight achievements. **The face is display-only as of 2026-08-30** (`docs/megaseed/display-only-face.md` in the working
set): `/fortknight/{build,questionnaire,assistant,ask}/` were deleted outright rather than left as
placeholders, along with the builder JavaScript, six Python CLIs, half of `fk_core` and the
committed bundle — all preserved at `creation-chain-parked`. The `/forkknife/` routes had gone on
2026-08-28. The nav is now six pills, one per Name Drop stone with a page, and three of them 404
until issues #18, #19 and #20 land — so `dev` → `main` is held until they do. The face
pages built on `fortknightdev` and `forknifedev` belong to the back-burnered creation chain, and
those branches are its playgrounds — it no longer ships by merging (re-ruled 2026-08-28; the folded
roadmap in the working set carries the ruling). Keep-fed replacements are built fresh in the `main`
lineage. Both branches are local-only as of 2026-08-29: deleted from origin and kept off it by a
`pre-push` hook, they exist on the maintainer's machine alone. The annotated tag
`creation-chain-parked` names the same commit on origin, so the parked work survives a fresh clone
even though the branches do not. Ten files were deleted from `main` with the chain —
`ApplyFromAssistant.astro`, `MealPlanEditor.astro`, `meal-plan-editor.js`, `forkknife.js` and the
`/forkknife/` pages — and each is recoverable with `git show creation-chain-parked:PATH`.

**Fort Knight is planned in the working set, not here.** The apps, the phone app **Fort Knight**
(Keep until 2026-08-27, Focus Key until 2026-08-28, now Fort Knight), and the keep that joins
them are one system with one plan:
`insiculous/docs/roadmap-fortnight-apps.md` in the admin repo. That file was folded together on
2026-08-27, **re-ordered around the keep** — responding to the schedule that exists comes before
authoring new ones — and on 2026-08-28 given a project spine.

**Fort Knight is the system, not an app** (ruled 2026-08-28). `/fortknight/` on this site is the
system's own web face, and through the current phase it is the only agenda surface there is. The work
runs in gated projects, in order; the two that concern this repository are:

1. **Project Mega Seed — the current project, in Operation MVP** (2026-09-02, the working set's
   `docs/megaseed/mvp.md`). Build keeps to flesh out the receiver, which is this site — the phone
   app is parked until Operation Phoney Bologna: the Keep
   format gets a public spec and machine schema, both canonical *here* because a person hand-making a
   keep cannot see the private repo. Nothing new consumes the format until it is written down.
2. **Project Ant Hill.** Reverse-engineer a keep builder from the hand-made keeps. The creation chain
   below belongs to it. **It is gated**: nothing in it starts before Mega Keep is done, so the
   per-item conditions that used to say "returns when" are now ordering inside that project.

Later projects exist and are planned in the working set.

What that means for the items this file used to number 1–9:

- **Items 1, 2, 4, 5 and 6** — questionnaire → weights, the generator, season menus, importers and
  exporters, and assistant-workspace follow-ups — are **Project Ant Hill** in the folded roadmap.
  Their contracts (`docs/questionnaire.md`, `docs/generator.md`, `docs/importers.md`,
  `docs/weights.md`, `docs/assistant-workspace.md`) are unchanged and still shipped; nothing is deleted.
- **Item 8, Forts and the Fortress** — no longer part of that queue. It was never keep-creation work,
  and it is planned separately in the working set. `docs/fortress.md` is unchanged and still says at
  its head that none of it exists.
- **Item 3, Fork Knife's full chain** (`docs/fork-knife-chain.md`) — **no longer "the next thing being
  built."** Its stage 3 does not exist at all, and it authors a menu from nothing while a real menu
  sits unread in the keep. What comes first is carrying the workbook's menu across in the Keep
  keep and rendering it under `/fortknight/` — the `/forkknife/` routes that design assumed are
  removed.
- **Item 7, "native clients reading the same bundle"** — **obsolete, not deferred**, and now doubly
  so: the phone app renders its own keep, and the bundle itself was deleted on 2026-08-30. The two
  meet at the keep, and there is no bundle for anything to read.
- **Item 9**, the "Open for Appointments (Tuesday A, early)" vs week-1-midday question, is a data
  question for the owner and stays open.

## What is web-specific, and stays here

- **The keep-fed pages** are live on `main`. `/fortknight/keep` renders a keep the
  visitor loads from their own device, resolving nothing and never uploading it; the Overview
  (`/fortknight/`) keeps its thesis front-door content as the no-keep state — its primary action is
  **Load your keep** — and renders a compact fortnight grid once a keep is stored; the fourteen
  `/fortknight/days/<dayKey>/` pages render the keep's blocks, meals and appointments by day key,
  falling back to the load-your-keep message. Keep is in the face nav (`src/lib/faces.js`), and
  the rendering is factored into `src/lib/keep-view.js` with a positional season palette. All of
  it is documented in `docs/app.md`.
- **The face branches are playgrounds (re-ruled 2026-08-28).** They belong to the back-burnered
  creation chain and are not absorbed or merged; keep-fed pages are built fresh in the `main`
  lineage. The earlier rule here — absorb `main` before keep-fed work — guarded a merge that no
  longer happens. `keep.astro`, `src/lib/keep.js`, `src/lib/keep-store.js`,
  `src/lib/keep-view.js` and `tests/fixtures/keep.sample.json` exist only on `main` and stay
  the live copies.
- **Achievements.** Shipped on this branch: three types, two stores. The games write one key each
  (`beinsiculous.games.<slug>.achievements`, the engine's save file byte for byte); the site writes
  its own insiculous and fortknight unlocks into one store, `beinsiculous.achievements`, with the
  registry in `src/lib/achievements.js` — initial achievements `player` (opened `/games/`) and
  `moved-in` (loaded a keep). The studio's `/achievements/` (nav entry after Games) lists
  every achievement the site knows: the registry entries render locked and unlocked with their
  descriptions, unlocked above locked within each group, and game achievements render per game as
  unlocked-only — the games own their full lists in-game, and the site does not duplicate engine
  data. `/fortknight/achievements/` narrows to the active profile's unlocked fortnight achievements
  and joined the face nav (six pills); `/games/` caps its grid at 75vh with scroll at multi-column
  widths (≥40rem) and carries a game-achievements board under it; `/profile/`'s panel shows all
  three types in a scroll box, and both scroll regions are keyboard-reachable. A visitor with
  achievements and no profile is offered one — the naming dialog opens once ever, and `/` and
  `/fortknight/` carry Create-a-profile buttons.
- **The `sun-b` starts for `ostara` and `fimbulsumar`** in `data/seasons.json` disagree with Focus
  Key's `sun-a` ruling. Porting it touches `seasons.json`, `docs/domain.md` and the test
  expectations here — which is why it is deferred and why every keep-fed page looks up rather than
  resolves.

## Open, not tied to an item

- **Getting files on and off a phone (Cowork).** The assistant flow assumes a person can move files
  between the app and their AI workspace, which is awkward on a phone. Claude's Cowork is a candidate
  answer and a Cowork-centred flagship is one option on the table — weighed against the
  bring-your-own-model position in `docs/thesis.md`, since it would tie the flow to one vendor.
  Nothing is designed around it. See `docs/fork-knife-chain.md` (Delivery) and `docs/fortress.md`.

## The game studio (tracked in its own repositories)

- **Web export.** Shipped — all six games are playable in the browser (WebGPU) through the embeds
  on `/games/`, and browser persistence for achievements has started: the deployed pong bundle
  already writes `beinsiculous.games.pong.achievements`, which the boards on `/achievements/`,
  `/games/` and `/profile/` read (`/fortknight/achievements/` narrows to the site's fortnight
  achievements). What remains is engine-side and tracked over
  there: the other five games writing their keys, high scores, and gesture-gated audio.
- **The browser editor.** The milestone behind web export: the engine's editor compiled to
  WebAssembly and served as a playground — open a tab, build a scene, press play, export the
  project. Tracked in the engine repository; when it lands, this site needs a route and an embed
  shape for it (the convention in `README.md` covers a game, not an editor).
- **The two tracks and the art policy** (`docs/thesis.md` is the source of the wording). The games
  listed on this site are free and use AI art. The games we **sell** are not on this site at all —
  each has its own repository and ships on Steam and/or Android and iOS — and they carry no AI art.
  Maintenance condition: the blanket sentence on `/games/` is true only while *every* game listed
  there uses AI art; the first one that does not makes it false, and per-game labelling has to ship in
  the same change.
- **Store links.** When the first paid game ships, this site needs somewhere to point at it — the
  games page is currently built around on-site listings only.
