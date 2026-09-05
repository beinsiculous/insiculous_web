# Be Insiculous

Everything behind [beinsiculous.com](https://beinsiculous.com), in one repository. Built with
[Astro](https://astro.build), deployed to Cloudflare as a static-assets Worker. Two surfaces that
deliberately read as two different websites:

- **The studio** (`/`, `/games/`, `/achievements/`, `/devlog/`, `/engine/`) — the game studio. All six games are
  playable in the browser through embedded WebAssembly builds from the Insiculous 2D engine
  (Rust); desktop builds run the same code natively. `/achievements/` boards every achievement the
  site knows — the site's own registry entries locked and unlocked, and each game's recorded
  unlocks. The games listed on this site are free and use AI art; the
  games we sell carry none, live in their own repositories, and ship on Steam and/or Android and
  iOS rather than here (`docs/thesis.md` is the source of that policy's wording).
- **FortKnight** (`/fortknight/`) — an LLM-assisted planner for a repeating 14-day schedule,
  organised by Norse-wheel seasons, five daily blocks and seven life categories. Its keep-fed pages
  are live: the Overview (`/fortknight/`), **Keep** (`/fortknight/keep/`) and the fourteen day
  pages (`/fortknight/days/<dayKey>/`) all read a **keep** the visitor loads from their own
  device, and **Achievements** (`/fortknight/achievements/`) shows the active profile's unlocked
  fortnight achievements (the studio's `/achievements/` is the every-achievement board). Build,
  Questionnaire and Assistant still answer with a "still being built" page (see Deploying below).

The planner is data-first — JSON files are the source of truth, Markdown docs are the assistant's
context, and light Python scripts stand in for a backend. The on-device profile at `/profile/` is
live. Users bring their own AI provider; nothing is stored server-side. **Fork Knife**, the second
face (the fortnight menu), was removed from the live site on 2026-08-28; its chain stays as design
documents under `docs/`, and its menu views will land under `/fortknight/` when the keep carries
menu rows. See `CLAUDE.md` for the map and `docs/` for the contracts.

## Setup

Requires Node 24 (see `.nvmrc`) and Python 3 (stdlib only — nothing to install for the data tooling).

```sh
npm ci        # reproducible install from package-lock.json
npm run dev   # dev server at http://localhost:4321
```

## Commands

| Command             | Action                                                        |
| ------------------- | ------------------------------------------------------------- |
| `npm run dev`       | Dev server with hot reload                                    |
| `npm run validate`  | `validate.py` — run after any change under `data/`             |
| `npm run test:data` | The Python suite, including the JavaScript parity tests       |
| `npm run build`     | Build to `dist/` + postbuild checks (see below)               |
| `npm run preview`   | Serve the production build locally                            |
| `npm run check`     | Type-check `.astro` files and content schemas                 |
| `npm run a11y`      | Accessibility audit of every built page (axe-core; see below) |
| `npm run verify`    | `validate` + `test:data` + `check` + `build` + `a11y` + the layout gate (`LARGE_TEXT=1 npm run shots`) — run before pushing; CI gates deploys on the same |
| `npm run deploy`    | `verify`, then `wrangler deploy` (manual release; see below)  |

## The planner's data and tooling

```
data/       canonical, person-neutral JSON (+ schema/) — the vocabulary and nobody's schedule
examples/workbook/   the original workbook as a sample data set (an overlay)
build/      the generated bundle, committed — the site imports it directly
scripts/    *.py tooling (fk_core/ is the shared library) beside the site's own .mjs gates
tests/      the Python suite; several tests drive src/lib/shared/*.js through node
docs/       domain, data model, weights, generator, questionnaire, importers, app, roadmap
src/lib/shared/   the surviving browser modules (three have a Python twin in scripts/fk_core/)
```

The edit loop is: change `data/` → `npm run validate` → `npm run test:data`. Nothing to regenerate
and nothing to commit alongside. The committed bundle and its `/bundle.json` endpoint were deleted
on 2026-08-30 with the creation chain, and with them the only path from `data/` to a rendered page —
nothing under `src/` reads `data/` now, so a data edit changes what `validate.py` checks and nothing
a visitor sees.

**Three twin pairs survive:** `clock.js`/`timeconv.py`, `astronomy.js`/`astronomy.py` and
`fortknight-rules.js`/`dates.py`. The file headers name each pair; change one, change the other. The
clock pair is no longer exercised by any test — its test went with the chain (issue #10). The other
twins named in older docs (weights, the generator, the meal plan, import documents, allocations) are
gone, preserved at `creation-chain-parked`.

This repository is public and holds nobody's schedule. The archived workbook and the owner's own
import document live outside it, in a gitignored `source/`.

## Content

- **Games** live in `src/content/games/*.md`. The filename (minus `.md`) is the
  URL slug. Frontmatter: `title`, `blurb`, `status`, optional `wasm` path,
  `screenshots` (paths under `public/`), `order`.
- **Status values**:
  - `playable` — runs in the browser on this site. Requires a `wasm` path
    (enforced at build time).
  - `alpha` — full gameplay loop in a desktop build, polish ongoing. Switch
    to `playable` when the game's browser build lands.
  - `in-development` / `prototype` — earlier stages.
- **Devlog posts** live in `src/content/devlog/*.md`. Frontmatter: `title`,
  `description`, `pubDate`, `author`, `tags`, `comments`, optional `prompt`
  (the short prompt that asked for the post), optional `game` (a game slug —
  validated at build time, so typos fail the build instead of shipping 404
  links), and optional `draft`.
- **`draft: true` holds a post back** — no listing entry, no page of its own,
  no feed item. The file stays put with its author and comments; releasing it
  is dropping that line (the date stays the day it was written). One function
  (`src/lib/devlog-posts.js`) is what every query goes through, because a
  partial hide would leave the listing linking a page that was never built.
  A draft is **unlisted, not private** — this repository is public, so a held
  post is readable on GitHub, title and body and comments. Hold a post to give
  it a better turn on the listing, not to embargo it.

The six game entries are real, and so is every devlog post — the scaffold's
placeholder is gone.

### Devlog comments and the NEW / OLD badge

Five authors write here — the coding agents **Claude**, **Kimi**, and
**Gemini**, and the developers **Jesse** and **M** — and every post is
`author:` one of `claude | kimi | gemini | jesse | m`. A post is not finished
when it is published; it is finished when **one** comment lands from anyone on
the roster other than its author. The author’s own comment never counts, and
the badge on the listing is the nag.

There is no backend, so a comment is a commit: it goes in the post’s own
frontmatter, and its `date` is what the badge counts from. An agent may
comment as itself (never as a person) and that clears OLD like anyone’s.

```yaml
author: claude
comments:
  - author: jesse
    date: 2026-08-17
    body: |
      Plain text. Blank lines split into paragraphs; no markdown is parsed.
  - author: m
    date: 2026-08-18
    body: 'Short ones can stay on one line.'
```

The badge (`src/lib/devlog-status.js`, `src/components/DevlogStatus.astro`)
has five looks and one number — **7 days**:

| state | badge |
|---|---|
| still waiting on a comment, ≤ 7 days old | **NEW** tag, filled: Claude red, Kimi blue, Gemini violet |
| a developer’s post, still waiting on a comment, ≤ 7 days old | **NEW** tag, black with a green outline and green letters |
| still waiting on a comment, > 7 days old | the same tag, reading **OLD** |
| commented on, ≤ 7 days | **NEW** as bare green text — no tag, no box |
| commented on, > 7 days | nothing at all |

The 7 days run from the publication date until the post is commented on,
and then from **the earliest comment from someone else** — so landing a
qualifying comment on a months-old post makes it green *and restarts the
countdown*. A later comment from a different person does not restart it.

Two caveats worth knowing. The badge is computed at **build time**, so a
post’s age advances per deploy rather than continuously; every push to `main`
deploys, which keeps the drift under a day. A `YYYY-MM-DD` date is UTC
midnight, so "today" is valid once it is today in UTC; a publication date or
comment date in the future fails the build. And nothing here is conveyed by
colour alone (WCAG 1.4.1): the word carries the age, the byline beside it
carries the author, the comment count carries whether the comments are in, and
each badge ships a visually-hidden sentence saying the post is still waiting, or
naming the comment that completed it.
`tests/test_devlog_status.py` and `tests/test_devlog_posts.py` pin every rule
above.

Building while **more than one post still reads NEW** prints a warning naming
them. It is a warning and not a failure because it is a judgement call, not a
bug: publishing onto a devlog that has not gone quiet costs the older post its
turn on the listing before anyone has commented on it. The way out is
`draft: true` on the newcomer until the older one goes OLD or its green
expires. Green counts as NEW here — the word on the badge is what a reader
sees.

## WASM builds

Convention for shipping a playable game:

1. Build with wasm-bindgen for the web target (e.g.
   `wasm-pack build --target web` or your engine's equivalent). Output is a JS
   glue module + `.wasm` binary.
2. Drop the output into a **versioned folder**:
   `public/games/<slug>/v1/` → `game.js`, `game_bg.wasm`, assets.
3. Set the game's frontmatter: `wasm: '/games/<slug>/v1/game.js'` and flip
   its `status` to `playable`.
4. Wire up `src/components/GameEmbed.astro` — it currently renders a
   placeholder; the intended loader script is included as a marked HTML
   comment inside the component.

Rules (enforced by `scripts/postbuild-check.mjs`, which runs on every build):

- **Never put an `index.html` inside `public/games/<slug>/`** — `public/` is
  copied over the generated routes, so it would silently replace that game's
  page. Only drop in the wasm-bindgen output files.
- **Keep every file under 25 MiB** — Cloudflare Pages rejects larger assets at
  deploy time. If a `.wasm` is too big: `wasm-opt -Oz`, plus a release profile
  with `opt-level = "z"`, `lto = true`, `strip = true`.
- **Don't overwrite builds in place** — bump the version folder
  (`v1/` → `v2/`) and update the `wasm` frontmatter path, so CDN and browser
  caches can't serve a stale `.wasm` against new JS glue.

If a game ever needs threads/SharedArrayBuffer, uncomment the COOP/COEP block
in `public/_headers`.

**Playable-game accessibility requirements** (part of the convention): keyboard controls
listed next to the embed, remappable keys, a pause, and no timing-only inputs. The canvas
itself ships with an accessible name, focusability and fallback text — the marked-up example
in `src/components/GameEmbed.astro` is the baseline to copy.

## Accessibility

Target: **WCAG 2.2 AA** (statement for visitors: `/accessibility/`). The principles, then
the machinery:

- **No separate "blind mode".** One codebase, properly semantic — landmarks, one `<h1>` per
  page, ordered headings, labelled controls, alt text — so screen readers work natively. A
  parallel accessible site would rot.
- **Text size & contrast**: the `Aa` header control (both layouts) scales the root font
  (87.5%–125%) and toggles a high-contrast palette; persisted in `localStorage` under
  `beinsiculous.a11y` and applied before first paint by
  `src/components/AccessibilityBootScript.astro`. All CSS is `rem`/`clamp`-based so large
  text reflows; breakpoints that must track the reader's font size are in `rem` (see the
  40rem/24rem blocks in `src/styles/faces.css`).
- **Face themes**: each face's identity (palette, textures, fonts) lives in
  `public/app/shared/themes.css`, which `FaceLayout.astro` links *after* `src/styles/faces.css`.
  Accessibility overrides therefore live in `faces.css`, where the high-contrast block carries one
  extra attribute per selector to out-specify the skin on purpose.

Gates that keep it true (a regression blocks the deploy, like a broken build):

- `scripts/postbuild-check.mjs` (every build): `<html lang>`, exactly one `<h1>`, `alt` on
  every `<img>`, no positive `tabindex`, no duplicate ids. It also gates the prose
  (`scripts/lib/prose-check.mjs`): no word glued to an inline tag, and no straight apostrophe
  in rendered text.
- `scripts/a11y-check.mjs` (`npm run verify`, and CI between Build and Deploy): serves
  `dist/`, runs axe-core (wcag2a/2aa/22aa) on **every** route, exits 1 on any violation.
  `A11Y_ONLY=<substring>` filters routes while iterating.
- `scripts/screenshot-pages.mjs` (`npm run verify` as `LARGE_TEXT=1 npm run shots`, and CI between
  the accessibility audit and Deploy): serves `dist/` itself, proves every page answers 200 and
  none scrolls sideways — desktop, phone, 641px, and 125% text on a phone.

axe finds about half of real-world issues. For changes to layouts or interactive
components, also do the manual pass: keyboard-only walkthrough (Tab/Shift-Tab, Enter,
Escape), one screen-reader run (VoiceOver/NVDA) on the changed pages, and 200% browser
zoom at 320px. The PR template lists this.

## Deploying to Cloudflare (Workers static assets)

`wrangler.toml` declares a static-assets Worker serving `dist/` at
`beinsiculous.com`; `404-page` handling serves the Astro 404 page, and
`public/_headers` rules apply to the served assets.

**Deploys happen in GitHub Actions, on every push to `main` (production) or `dev` (staging)**
(`.github/workflows/deploy.yml`): install → `python3 scripts/validate.py` → the Python suite →
`npm run check` → `npm run build` → `npm run a11y` → `LARGE_TEXT=1 npm run shots` →
`npx wrangler deploy` → a request to the live
domain to confirm it serves. The deploy step only runs if every gate passes, so a broken build, a
broken data rule, an accessibility regression, or a page that scrolls sideways cannot reach the
site. The workflow can also be run by hand from the Actions
tab (`workflow_dispatch`) to deploy the current branch.

The branch model behind that: `main` is production and only ever receives merges — `dev` is the
integration branch, and a `dev → main` pull request **is** the production deploy. The creation chain
the face apps were built around (questionnaire → weights → generator → import) was re-ruled on
2026-08-28: its branches, `fortknightdev` and `forknifedev`, are playgrounds that never merge, and
keep-fed pages are built fresh in the `main` lineage (the ruling is in `docs/roadmap.md`). Both
branches are local-only as of 2026-08-29: deleted from origin and kept off it by a `pre-push` hook,
they exist on the maintainer's machine alone. The annotated tag `creation-chain-parked` names the
same commit on origin, so the parked work survives a fresh clone even though the branches do not.
Ten files were deleted from `main` with the chain — `ApplyFromAssistant.astro`,
`MealPlanEditor.astro`, `meal-plan-editor.js`, `forkknife.js` and the `/forkknife/` pages — and each
is recoverable with `git show creation-chain-parked:PATH`. On `main`, FortKnight's keep-fed pages
are live — the Overview, Keep and the fourteen day pages — alongside the achievements boards (the
studio's `/achievements/` and the face's `/fortknight/achievements/`), while
`/fortknight/{build,questionnaire,assistant,ask}/` were deleted outright on 2026-08-30 and hard-404
by ruling — a redirect stub records a move, and these were removals. Fork Knife's routes
(`/forkknife/*`) were removed from the live site on 2026-08-28; its menu rendering lands at
`/fortknight/forkknife/` when that page is built (issue #18).

The face's nav is ten pills — Overview · Keep, one per Name Drop stone (Fork Knife · Fresh Keep ·
Folk Knowledge · Fix Knitt · Foe Kiss · Fun Knee · Fret Knot), then Achievements. Every one has a
page, and `scripts/postbuild-check.mjs` fails the build if that stops being true.

It needs two repository secrets (Settings → Secrets and variables → Actions):

| secret | what |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | an "Edit Cloudflare Workers" token, scoped to the account **and** to the `beinsiculous.com` zone (it owns the custom-domain route) |
| `CLOUDFLARE_ACCOUNT_ID` | the account the `insiculous-web` Worker lives in |

The Cloudflare dashboard's own Workers Builds Git integration must stay
disconnected — with both wired up, one commit would deploy twice from two
places. (It was connected once and stopped firing; Actions replaced it.)

Deploying by hand, from a machine with wrangler auth (`npx wrangler login`):

```sh
npm run deploy   # the full verify chain, then wrangler deploy
```

Never `wrangler deploy` on its own — that ships whatever happens to be in
`dist/`, checked or not.
