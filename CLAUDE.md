# beinsiculous.com — agent guide

One repository, two surfaces of one site (`docs/app.md`): the **Be Insiculous** studio (`/`,
`/games/`, `/achievements/`, `/devlog/`, `/engine/`) and the planner face **FortKnight** (`/fortknight/`), with the
shared profile at `/profile/`. The second face, **Fork Knife** (`/forkknife/`), was removed from the
live site on 2026-08-28; its chain stays as design documents (`docs/meal-plan.md`,
`docs/fork-knife-chain.md`), and its menu views land under `/fortknight/forkknife/` when that page
is built (`beinsiculous/insiculous_web#18`).

**The face is display-only** (ruled 2026-08-30, `docs/megaseed/display-only-face.md` in the working
set). It reads a keep the visitor loads and renders it; nothing on this site builds one. The
creation chain that did — the Build, Questionnaire and Assistant pages, the builder JavaScript, the
Python builder CLIs and the committed bundle — left `main` on 2026-08-30 and is preserved at the
annotated tag `creation-chain-parked`. Read that ruling and `docs/megaseed/name-drop.md` (the
current vocabulary) before trusting any older description of how a schedule gets made.

The planner is *data first*: a set of JSON files plus companion Markdown docs. An Astro build
renders the site with no backend. No server ever holds user data or AI credentials.

Read `docs/domain.md` before touching data — the vocabulary (day keys, blocks, seasons,
focus, weights) is specific to this project.

## Source of truth, in order
1. `data/*.json` — canonical and **person-neutral**: the vocabulary (categories, the neutral five-block
   day, day keys, seasons, questionnaire, schemas) and *nobody's* schedule — `activities` is empty,
   `menus/` is empty, `days.json` carries no focus. A fresh device starts blank. **Edit these** for
   vocabulary/rules; never put a person's schedule here.
2. `examples/workbook/` — *the workbook* — a proper noun here, meaning the archived single `FortKnight.xlsx` of August 2026 and never a slab (the working set's `docs/megaseed/name-drop.md`, *The word "workbook"*) — as a **sample data set** (64 activities, the block focus
   grid, the Spooky Season menu, the baseline weights), laid over `data/` with `--overlay examples/workbook`
   and used by `validate.py` and the tests. Every record keeps its spreadsheet text under `raw`
   (+ `sourceRow`). The CLIs that also read it are gone; `validate.py` is the only one left that takes
   `--overlay`.
3. `src/` — the site. `src/lib/keep*.js` read and draw a loaded keep; `src/lib/shared/*.js` is what
   survived the creation chain's removal — `clock.js`, `astronomy.js` and `fortknight-rules.js`
   (each with a Python twin in `scripts/fk_core/`), plus `user-settings.js` and `profile-names.js`,
   which have none.

**There is no `build/` step and no bundle.** `scripts/build.py` and `build/fortknight.bundle.json`
were deleted on 2026-08-30, and with them the only path from `data/` to a rendered page — verified:
nothing under `src/` reads `data/`. So `data/` is now a validated vocabulary that ships nowhere, and
`npm run data` no longer exists. Editing `data/` changes what `validate.py` checks and nothing a
visitor sees.

This repository is **public** and holds nobody's schedule. The archived `FortKnight.xlsx` and the
owner's own import document live outside it, in `source/` (gitignored). A person's schedule reaches
this site one way only: as a keep the visitor loads into their own browser, kept in `localStorage`
and never uploaded. Never through `data/`.

## Commands (stdlib Python 3 and Node 24 — `npm ci` is the only install)
```
python3 scripts/validate.py                       # schemas + referential rules + the schedule sweep; exit 1 on error
python3 scripts/validate.py --overlay examples/workbook           # the same on the workbook sample set
python3 -m unittest discover tests                # test suite (also `npm run test:data`)
npm run dev                                       # the site: / (studio) + /fortknight/ + /profile/
npm run validate                                  # validate.py alone
npm run verify                                    # what CI gates the deploy on: validate + tests + check + build + a11y + the layout gate
```
**Six CLIs and `npm run data` are gone** (2026-08-30): `build.py`, `questionnaire_to_weights.py`,
`generate_grid.py`, `analyze_allocations.py`, `xlsx_to_json.py` and `resolve_date.py`, along with the
`fk_core` half only they reached (`generator.py`, `allocations.py`, `derive.py`, `xlsx.py`,
`parse.py`). They are preserved at `creation-chain-parked`. Any doc, comment or habit that tells you
to run one is stale — say so rather than reviving it.

The edit loop is now just: change `data/` → `npm run validate` → tests. Nothing to regenerate and
nothing to commit alongside.
Every push to `main` (production) or `dev` (staging) deploys (`.github/workflows/deploy.yml`):
validate → tests → `astro check` → build → axe-core over every page → the layout gate
(`LARGE_TEXT=1 npm run shots`) → `wrangler deploy` → a request to the live domain.

## Coding conventions (apply to Python, JavaScript, and JSON field names)
- **Human-readable names, no abbreviations.** `estimatedStartTime`, not `estStart`; `dayKey`, not `dk`; `durationMinutes`, not `dur`. Loop variables included (`activity`, not `a`).
- **DRY** — shared logic lives in `scripts/fk_core/` (Python) or `src/lib/shared/*.js` (plain ES modules with no build step, driven by the tests through node); never copy a rule (day-key order, season rules, time parsing) into a second place. **Three twin pairs survive** the creation chain's removal: `clock.js`/`timeconv.py`, `astronomy.js`/`astronomy.py`, `fortknight-rules.js`/`dates.py`. The file headers name each pair. Change one, change the other — and note that **nothing exercises the clock pair any more** (`beinsiculous/insiculous_web#10` owns that gap), so its parity is currently a promise rather than a check. Every other "mirrored by" claim you meet in `docs/` refers to a JavaScript file that no longer exists.
- **KISS** — the simplest thing that works; stdlib only in Python; `src/lib/shared/` stays framework-free with no build step, the site is plain Astro with no UI framework.
- **SRP** — one responsibility per module and per script; a script orchestrates, a module implements.
- Times are `"HH:MM"` 24h strings; dates ISO `YYYY-MM-DD`; durations integer minutes; ids lowercase kebab-case and **immutable** once published.

## Invariants (validate.py enforces most of these)
- Exactly 14 day keys in canonical order: `sun-a, mon-b, tue-a, wed-b, thu-a, fri-b, sat-a, sun-b, mon-a, tue-b, wed-a, thu-b, fri-a, sat-b`.
- The neutral five-block day: `too-early, early, midday, late, too-late`; only early/midday/late carry a focus and activities. Questionnaire profiles carry their own 2–5 blocks (`weights.*.json` → `blocks`; rule in `docs/questionnaire.md`; a one-focus-block day's block is keyed `flexible` and shown without a header).
- The site has one face (`docs/app.md`): FortKnight (`/fortknight/`), plus the shared `/profile/` (the studio's skin and chrome, not a face's) and a landing at `/`. Its nav is ten pills — **Overview · Keep**, then one per Name Drop stone (**Fork Knife · Fresh Keep · Folk Knowledge · Fix Knitt · Foe Kiss · Fun Knee · Fret Knot**), then **Achievements**. Fort Knight itself has no pill: it is the agenda stone, and the agenda is what the Overview, Keep and the day pages already are. Every pill has a page, and `scripts/postbuild-check.mjs` now fails the build if one does not — added after three pills spent a day 404ing behind nothing but a written deploy hold.
- Everything the face does is **read**: the Overview keeps its thesis front-door content while no keep is loaded, with **Load your keep** (to `/fortknight/keep/`) as its primary action, and renders a compact fortnight grid linking to the day pages once a keep is stored; `/fortknight/keep/` and the fourteen `/fortknight/days/<dayKey>/` pages render the loaded keep's blocks, meals and appointments by day key — lookup only, no date resolution — falling back to a load-your-keep message. A profile is created from the buttons on `/` and `/fortknight/`, which is now its permanent home rather than a stopgap. **Every page that wrote anything is gone**, and `/fortknight/{build,questionnaire,assistant,ask}/` hard-404 by ruling — removals get no redirect stub, which is scoped to moves (`myfort`, `settings`, `allocations`, `fortnight` keep theirs, because their targets are alive).
- `/fortknight/keep/` **will regain building** — slab uploads producing a downloadable keep, per Operation Name Drop (`docs/megaseed/name-drop.md`, `beinsiculous/insiculous_web#24`). That is a new writer, not the parked chain returning.
- Seven categories: `meals, cleaning, working, spirituality-development, friends-family, health, operations` (+ `flexible` pseudo-focus). The set is closed — a category is a stone — and the web keep's schema enumerates it; subjects are a fort's own, and `data/categories.json` is the shipped default (working set `docs/megaseed/categories.md`, 2026-09-02).
- In every menu file present, every day has exactly one brunch, snack, and dinner; every meal-prep `mealRef` resolves to a menu meal (the neutral `data/` has no menu files).
- Season starts are computed by rule (`fk_core/dates.py` `start_date_for_rule`, one structured rule shape for the workbook seasons and a person's year-split sections), never typed in — the only typed dates are `manual` sections' `knownStarts`; each season restarts the fortnight on its `startDayKey`.
- Appointment block: week 1 (`sun-a`…`sat-a`) = `midday`, week 2 = `early`.

## The north star: weights — *the parked chain's design, not this site*
The creation chain's endgame was a questionnaire whose output is `weights.*.json` (see
`docs/weights.md`) — how much of the fortnight each category should get — with a generator
(`docs/generator.md`) turning weights into a proposed block focus grid. **None of it runs here any
more.** The generator, the analyser and the questionnaire→weights CLI were deleted on 2026-08-30 and
are preserved at `creation-chain-parked`; `fk_core/weights.py` survives only because `validate.py`
needs one function from it, and it no longer emits a `proposal`. Keep the contract in mind when
reading `data/schema/weights.schema.json`, which is still validated — but do not design new features
against a pipeline that is not here. What replaces it is the slab → stone → keep chain in
`docs/megaseed/name-drop.md`.

## Assistant workspace (no AI in the app) — *the parked chain's design*
The app never calls an LLM and holds no credentials, and Python scripts never call one either. That
much is permanent. The rest of this section describes a design that **is not implemented**: the app
generating a file set (README + docs + schemas + data + the person's settings/weights) for the
person to upload into their *own* AI workspace, and accepting back what the assistant produces. The
file list, the classifier and the two prompts lived in `src/lib/shared/workspace-docs.js`, deleted
2026-08-30 and preserved at `creation-chain-parked`; the contract is `docs/assistant-workspace.md`,
which carries a status banner saying the same thing. **`/profile/` has no workspace downloads and no
page promises any** — it holds the profile actions, the stored keep and the achievements board.
Named profiles per device still live at `settings.weightsProfiles` with one `activeWeightsId`,
switched from the nav dropdown; that part is live and is `src/lib/shared/user-settings.js`.

## The site (Astro 7, Node 24)
Static build, deployed to Cloudflare as a static-assets Worker. No UI framework; the face pages are
plain untyped JavaScript, so `tsconfig.json` excludes them from `astro check` and the Python parity
tests are what keep them honest. **Accessibility is a top priority at Be Insiculous**, and three
gates hold it in every `npm run verify` and in CI, so a regression blocks the deploy:
`scripts/postbuild-check.mjs` (every build — structure + static a11y + prose: `scripts/lib/prose-check.mjs`
gates a word glued to an inline tag and a straight apostrophe — Astro drops the newline between a
word and an inline tag on the next source line, so keep the tag on the word's line),
`scripts/a11y-check.mjs` (axe-core over
**every** built page, WCAG 2.2 AA), and `scripts/screenshot-pages.mjs` (every page answers 200 and
none scrolls sideways — desktop, phone, 641px, and 125% text on a phone via `LARGE_TEXT=1`). The target they hold is WCAG 2.2 AA with no separate "blind mode" — one properly semantic
codebase. After changing a layout or an interactive component, also do the manual pass the PR template
lists (keyboard-only, one screen-reader run, 200% zoom at 320px).

**The keep-fed pages are live; the creation chain is gone from `main`.** `main` is production and
only receives merges — `dev` integrates, and a `dev → main` pull request is the deploy. Commit on
**`m`**, push it, merge `m` into `dev`; never commit straight to `dev`.

The chain was parked on 2026-08-28 (placeholder routes kept as files) and then **removed outright on
2026-08-30** by the display-only ruling, because keeping dead routes wired into the nav was itself a
lie the site told. Everything removed is recoverable, from two places, **and the difference matters**:
the annotated tag `creation-chain-parked` lives on origin and preserves the functional chain — but it
pins the **2026-08-26** snapshot, before the 2026-08-28/29 naming settlements, so a file's state *at
removal* comes from `main` history (the removal commit's parent), not the tag. Restoring from the tag
alone would reintroduce naming drift. The face branches `fortknightdev` and `forknifedev` are that
chain's playgrounds, never merge, and are local-only as of 2026-08-29 — deleted from origin and kept
off it by a `pre-push` hook.

Live on `main`'s lineage: FortKnight's Overview, `/fortknight/keep/`, the fourteen
`/fortknight/days/<dayKey>/` pages, `/fortknight/achievements/`, `/profile/`, and the studio pages
including `/achievements/`. Fork Knife's `/forkknife/*` routes are removed; its menu rendering lands
under `/fortknight/forkknife/` (`#18`).

**The keep** is a small file the private Fort Knight app exports (`fortknight/src/lib/keep.js`): the fourteen
day keys with their meals, appointments and block shapes, plus a season card and the year wheel. The day keys are the
format's skeleton: this is a fourteen-day system, so a conforming keep uses exactly the canonical fourteen
(`sun-a, mon-b, tue-a, wed-b, thu-a, fri-b, sat-a, sun-b, mon-a, tue-b, wed-a, thu-b, fri-a, sat-b`, the order the
Invariants above pin). The
visitor loads their own file; it is kept in `localStorage` under `beinsiculous.keep`
(`src/lib/keep-store.js`), deletable from `/profile/`, and never uploaded. The rendering is
shared across the three keep-fed pages: `src/lib/keep-view.js` draws the panels, with season
colours from a **positional palette** — position pinned to first appearance in `year.slices`, never
keyed to a household's season ids — and one stored-keep boot path serves the Overview, Keep and
the day pages.

The keep-fed pages **resolve nothing** — the keep arrives pre-joined by day key. That is not a shortcut: Fort Knight
anchors every season on `sun-a` and has transition weeks, while `fk_core/dates.py` and
`src/lib/shared/fortknight-rules.js` still evaluate the archived `sun-b` starts for Ostara and
Fimbulsumar, so **running this repository's date evaluator over a keep would be wrong for half the
year.** Nothing here has to: `src/lib/keep.js` validates and the pages draw.

**A keep is somebody's real schedule, so it must never be committed here.**
`scripts/fk_core/no_schedules.py` enforces that — it refuses any JSON whose `meta.format` is `"keep"`,
or which carries `meta`, `calendar`, `days` and `tasks` together, and it reports files it cannot read
rather than skipping them. `validate.py` runs it, and `npm run verify` runs `validate.py`. Two fixtures are
exempt by exact path: `tests/fixtures/keep.sample.json`, which `a11y-check.mjs` loads so axe audits
a page with fourteen real panels instead of an empty file picker, and `tests/fixtures/keep.other-household.json`,
a second invented household the rendering tests and the a11y gate's second seeded pass use to prove the year wheel's
colours are positional rather than keyed to one household's season ids — that pass is what certifies the palette's
contrast on a keep that is not the original household's. Both are invented, and tests assert all of that.

## Achievements

Three types, two stores. **Game** achievements are written by the games' browser builds — one
localStorage key per game, `beinsiculous.games.<slug>.achievements`, holding the engine's native
save file byte for byte; `src/lib/games-achievements.js` reads them. **Insiculous** (site-wide) and
**FortKnight** achievements are written by the site itself into one store,
`beinsiculous.achievements`, with the same `{"unlocks": {"<id>": {"unlocked_at": <unix seconds>}}}`
shape; the registry of ids, titles, descriptions and types lives in `src/lib/achievements.js`. Two stores because
the writers are different programs: a wasm build persists exactly what its engine writes on desktop,
and sharing a key with the site's own unlocks would let one migrate into the other (the
`keep-store.js` argument). Initial achievements: `player` (insiculous — opened `/games/`) and
`moved-in` (fortknight — loaded a keep).

`/achievements/` is the every-achievement board — a studio page (BaseLayout, a nav entry after
Games). The insiculous and fortknight registry entries render locked **and** unlocked, with their
descriptions, unlocked sorting above locked within each group; game achievements render per game as
unlocked-only, because the games own their full lists in-game and the site does not duplicate
engine data. `/fortknight/achievements/` narrows to the active profile's unlocked fortnight
achievements, and sits in the face nav (six pills: Overview · Keep · Achievements · Build ·
Questionnaire · Assistant). `/games/` caps its grid at 75vh with scroll at multi-column widths
(≥40rem) and carries a game-achievements board under it; `/profile/`'s achievements panel shows all
three types in a scroll box. Both scroll regions — the `/profile/` box and the `/games/` grid — are
keyboard-reachable (tabindex + an accessible name). A visitor with no profile is offered one where
achievements happen: `/` and `/fortknight/` carry Create-a-profile buttons, and the first time an
achievement exists with no profile saved, the naming dialog (`askProfileName` in
`src/lib/profile-name-dialog.js`) opens — once ever, the settled flag riding beside the store under
`beinsiculous.achievements.profile-prompt`.

## Writing a devlog entry
Read `src/content/devlog/six-games-one-day.md` first — every rule here describes that entry. The
fields, the `draft:` mechanics and the NEW/OLD comment badge are `README.md`'s; this section is only
about writing the thing. (These rules load when you read a file under `src/content/`, which drafting
a new entry does not force — so start at the exemplar. Prose, not a gate.)

**Write as yourself.** An agent's `author:` is `claude` or `kimi`, never `jesse` or `m`, and the body
says an AI wrote it in the first paragraph, in your own words — not a disclaimer at the bottom. The
exemplar's "I'm the AI that did the porting, so consider this a devlog from the workshop floor" is
the register. The same rule covers `comments:`: **never write a comment in a developer's name.** You
may comment as `claude` or `kimi` — those are welcome extras and never gate the badge
(`src/lib/devlog-status.js`) — but the file cannot show who typed it, so a comment under a person's
name forges that name onto writing that never happened. Same reasoning as the skip trailers below.

**200–400 words of body**, frontmatter excluded, hard-wrapped at ~72–76 columns. Under 200 it is a
changelog line; over 400 it is a doc that wandered into the devlog. The two existing entries measure
353 and 211.

**Shape.** The first sentence carries the claim — a before/after, or the thesis — with no warm-up
paragraph. Three to five short paragraphs, at least one carrying a concrete specific with a number
or a named failure ("ninety minutes of interrogating a black rectangle", "between 1.4 and 3 MiB").
A closing line, then the signature: `— Name (Model), role at Be Insiculous`. Prose only: no headings,
no bullet lists. A list is the shape an agent defaults to and the wrong one here.

**Register and honesty.** The devlog is one of the four bubbles of quirk, not the studio's
professional register (`docs/thesis.md`, "Two registers"). First person, specific, self-aware. Report
the day that actually happened, including what went wrong — no projected benefits, no invented
metrics. A number in an entry is one you observed. What earns an entry: a thing that shipped, a
decision with its reason, or a failure worth the telling — not one entry per commit.

**You do not publish.** An agent's entry commits with `draft: true`; a developer releases it. Know
what that gates: the listing, the page and the feed — *not* visibility. This repository is public, so
a held entry is readable on GitHub the moment it commits. It is a gate on presentation, not on
confidentiality. Keep the teaching `#` comments above `author:`, `draft:` and `comments:` — both
existing entries carry them and they are part of the convention.

**Slug** is the filename minus `.md`: lowercase kebab-case, no date prefix, three or four words
drawn from the claim rather than the title verbatim, and immutable once published.
`scripts/screenshot-pages.mjs` walks every built page, so a renamed or re-drafted post needs no
registration there — but re-drafting **every** entry fails the gate on purpose, because the comment
thread and its badge would go untested.

## Work tracking

Open work lives on the **Studio Board** (https://github.com/orgs/beinsiculous/projects/1)
as issues in this repo. **Always pass `-R beinsiculous/insiculous_web`** — a bare `gh` command
resolves against the session's working directory, which is often the working-set root, so
it lists and files against the wrong repository.

```sh
gh issue list -R beinsiculous/insiculous_web
gh api repos/beinsiculous/insiculous_web/milestones --jq '.[] | "\(.title): \(.description)"'
```

Issues are grouped into **sprint milestones**; each description records the batch's
internal order and its gates. Take the next unblocked issue in a sprint, not an arbitrary
one. Claim by assigning yourself; close with `fixes beinsiculous/insiculous_web#N` in the commit.

**Unfinished work becomes an issue.** Anything you don't finish — work you deferred, debt
you created, a follow-up you spotted — is filed before you report done. Never buried in a
doc, never left as a bare `TODO:`, never dropped. The `file-issue` skill carries the shape;
`sprint-planning` groups issues into shippable batches.

## Review convention: adversarial review (Claude Code ↔ Kimi Code CLI)
Plans and large diffs get an adversarial review by the *other* CLI, adjudicated with the user —
see `.claude/skills/adversarial-review/SKILL.md` (Claude side) and
`.kimi-code/skills/adversarial-review/SKILL.md` (kimi side; same workflow, reviewer roles
swapped). Two hooks make it the default in both harnesses — approved plans are routed through
plan mode, and `git commit` with ≥100 changed lines is denied until code mode has run (retry
with the `ADV_REVIEWED=1` prefix, which asserts the review *happened* — it is not a way to skip
one). **Skipping is the developer's call**, made in the last lines of the commit message where
the world can read it: `Adversarial-Review-Skipped: <reason over 10 characters>` plus
`Skip-Signed-Off-By: <name>`. Any reason qualifies — "just because" is a reason. That buys
friction and a paper trail, **not** proof of authorship: the hook cannot tell who typed the
trailers, so an agent writing them forges a person's name onto a review that never happened.
An agent never writes them — it asks.
Claude's hooks are
registered in `.claude/settings.json`; kimi's live in the global `~/.kimi-code/config.toml`
and both hook scripts (`scripts/plan-review-hook.sh`, `scripts/commit-review-hook.sh`) take a
`--harness=claude|kimi` flag and stay silent in repos that don't carry the skill marker.
Artifacts live in `review/` (gitignored); reviewer prompts in `prompts/` are fixed.
`scripts/adversarial-review.sh` is the fully-headless variant, not for interactive use.
Hook behavior is covered by `tests/test_hooks.py`.

## Where to look
| need | file |
|------|------|
| why any of this exists — the studio's banner, the two registers (studio professional / the four projects quirky), what each surface argues, and the art policy's wording | `docs/thesis.md` |
| concepts and vocabulary | `docs/domain.md` |
| every JSON file and field | `docs/data-model.md`, `data/schema/*.schema.json` |
| how the workbook mapped to JSON, known quirks | `docs/workbook-mapping.md` |
| what the surviving Python scripts do (and the six CLIs that are gone) | `docs/scripts.md` |
| weights / questionnaire contract — *parked design* | `docs/weights.md` |
| the generator — *parked design, code removed 2026-08-30* | `docs/generator.md`; the code is at `git show creation-chain-parked:scripts/fk_core/generator.py` |
| questionnaire questions, answers → weights mapping — *parked design; nothing renders it* | `docs/questionnaire.md`, `data/questionnaire.json` |
| import document contract — *parked design; the schema is still validated* | `docs/importers.md`, `data/schema/import.schema.json` |
| the meal plan / Fork Knife (menu, prep + cooking tasks) | `docs/meal-plan.md`, `data/schema/meal-plan.schema.json`, `scripts/fk_core/meal_plan.py` |
| the keep format — the spec a person hand-makes a keep from, and its machine schema | `docs/keep-format.md`, `data/schema/keep.schema.json` |
| how an assistant reads a spreadsheet into an import document — *parked design* | `docs/import-from-spreadsheet.md` |
| what the site actually is now — the display-only face, page by page | `docs/app.md` |
| the studio site, games/devlog content, WASM drop-in convention, deploy | `README.md` |
| devlog authorship (`author:`), comments in frontmatter, the NEW/OLD comment badge | `README.md`, `src/lib/devlog-status.js` |
| how to write a devlog entry — voice, length, signature, and why an agent never publishes one | "Writing a devlog entry" above, `src/content/devlog/six-games-one-day.md` |
| accessibility target, the three gates, the manual pass | `README.md`, `scripts/a11y-check.mjs`, `scripts/postbuild-check.mjs` |
| the face registry (labels, skins, nav, favicons) | `src/lib/faces.js`, `src/layouts/FaceLayout.astro` |
| achievements — the three types, the two stores, the registry | `src/lib/achievements.js`, `src/lib/games-achievements.js` |
| how an assistant should propose changes | `docs/llm-guide.md` |
| assistant workspace (file set, reply contract) | `docs/assistant-workspace.md` |
| what comes next for Fort Knight — the one app and the eight stones | `insiculous/docs/roadmap-fortnight-apps.md` in the working set |
| what comes next that is web-specific, and the studio | `docs/roadmap.md` |
| Fork Knife's full chain: questions → the agent interviewing back → menu, recipes, prep, cooking, shopping (design, not built) | `docs/fork-knife-chain.md` |
| forts, the five roles, boards, a real login — the household/community direction (design, not built) | `docs/fortress.md` |
| adversarial review workflow | `.claude/skills/adversarial-review/SKILL.md`, `.kimi-code/skills/adversarial-review/SKILL.md`, `scripts/request-review.sh`, `prompts/` |
