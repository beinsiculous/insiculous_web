# Be Insiculous — studio site

Static site for [Be Insiculous](https://beinsiculous.com), an
independent game studio / solo-dev label. Built with [Astro](https://astro.build),
deployed to Cloudflare as a static-assets Worker. The site is wired to embed WebAssembly game
builds from the Insiculous 2D engine (Rust) as they land — the games are
desktop-only until the engine's web export ships.

## Setup

Requires Node 24 (see `.nvmrc`).

```sh
npm ci        # reproducible install from package-lock.json
npm run dev   # dev server at http://localhost:4321
```

## Commands

| Command           | Action                                                        |
| ----------------- | ------------------------------------------------------------- |
| `npm run dev`     | Dev server with hot reload                                    |
| `npm run build`   | Build to `dist/` + postbuild checks (see below)               |
| `npm run preview` | Serve the production build locally                            |
| `npm run check`   | Type-check `.astro` files and content schemas                 |
| `npm run a11y`    | Accessibility audit of every built page (axe-core; see below) |
| `npm run verify`  | `check` + `build` + `a11y` — run before pushing; CI gates deploys on the same |
| `npm run deploy`  | `verify`, then `wrangler deploy` (manual release; see below)  |

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
  `description`, `pubDate`, `tags`, optional `game` (a game slug — validated
  at build time, so typos fail the build instead of shipping 404 links).

The six game entries are real; the devlog still contains one clearly-marked
placeholder post to delete once real posts exist.

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
- **Face themes are synced**: `public/app/shared/themes.css` and `src/lib/shared/*` are
  wholesale-copied from the FortKnight repo by `scripts/sync-fortknight.mjs` — never edit
  them here; accessibility overrides for the faces live in `src/styles/faces.css` (the
  high-contrast block there out-specifies the synced skin on purpose).

Gates that keep it true (a regression blocks the deploy, like a broken build):

- `scripts/postbuild-check.mjs` (every build): `<html lang>`, exactly one `<h1>`, `alt` on
  every `<img>`, no positive `tabindex`, no duplicate ids.
- `scripts/a11y-check.mjs` (`npm run verify`, and CI between Build and Deploy): serves
  `dist/`, runs axe-core (wcag2a/2aa/22aa) on **every** route, exits 1 on any violation.
  `A11Y_ONLY=<substring>` filters routes while iterating.
- `scripts/screenshot-pages.mjs` with `LARGE_TEXT=1`: extra pass proving no page scrolls
  sideways at 125% text on a phone.

axe finds about half of real-world issues. For changes to layouts or interactive
components, also do the manual pass: keyboard-only walkthrough (Tab/Shift-Tab, Enter,
Escape), one screen-reader run (VoiceOver/NVDA) on the changed pages, and 200% browser
zoom at 320px. The PR template lists this.

## Deploying to Cloudflare (Workers static assets)

`wrangler.toml` declares a static-assets Worker serving `dist/` at
`beinsiculous.com`; `404-page` handling serves the Astro 404 page, and
`public/_headers` rules apply to the served assets.

**Production deploys happen in GitHub Actions, on every push to `main`**
(`.github/workflows/deploy.yml`): install → `npm run check` → `npm run build`
→ `npm run a11y` → `npx wrangler deploy` → a request to the live domain to confirm it serves.
The deploy step only runs if the checks pass, so a broken build — or an accessibility
regression — cannot reach the site. The workflow can also be run by hand from the Actions
tab (`workflow_dispatch`) to redeploy the current `main`.

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
npm run deploy   # check + build + postbuild + wrangler deploy
```

Never `wrangler deploy` on its own — that ships whatever happens to be in
`dist/`, checked or not.
