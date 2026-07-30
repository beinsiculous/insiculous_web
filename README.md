# Be Insiculous — studio site

Static site for [Be Insiculous](https://insiculous-web.jessemsmcintosh.workers.dev), an
independent game studio / solo-dev label. Built with [Astro](https://astro.build),
deployed to Cloudflare Pages. The site is wired to embed WebAssembly game
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

## Deploying to Cloudflare (Workers static assets)

The repo is connected via the Cloudflare dashboard's Git integration
(Workers Builds). `wrangler.toml` declares a static-assets Worker serving
`dist/`, so the default pipeline works as-is:

- Build command: `npm run build`
- Deploy command: `npx wrangler deploy`

Every push to `main` builds and deploys; the `404-page` handling serves the
Astro 404 page, and `public/_headers` rules apply to the served assets.

Manual deploy from a machine with wrangler auth: `npm run build && npx
wrangler deploy`.

After the first deploy, set the real URL (workers.dev or custom domain) in
`astro.config.mjs` (`site`).
