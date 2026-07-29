# Be Insiculous — studio site

Static site for [Be Insiculous](https://be-insiculous.pages.dev), an
independent game studio / solo-dev label. Built with [Astro](https://astro.build),
deployed to Cloudflare Pages. Games run in the browser as WebAssembly builds
from the Insiculous 2D engine (Rust).

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
  URL slug. Frontmatter: `title`, `blurb`, `status`
  (`playable` / `in-development` / `prototype`), optional `wasm` path,
  `screenshots` (paths under `public/`), `order`.
- **Devlog posts** live in `src/content/devlog/*.md`. Frontmatter: `title`,
  `description`, `pubDate`, `tags`, optional `game` (a game slug — validated
  at build time, so typos fail the build instead of shipping 404 links).

Current entries are clearly-marked placeholders — replace them.

## WASM builds

Convention for shipping a playable game:

1. Build with wasm-bindgen for the web target (e.g.
   `wasm-pack build --target web` or your engine's equivalent). Output is a JS
   glue module + `.wasm` binary.
2. Drop the output into a **versioned folder**:
   `public/games/<slug>/v1/` → `game.js`, `game_bg.wasm`, assets.
3. Set the game's frontmatter: `wasm: '/games/<slug>/v1/game.js'`.
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

## Deploying to Cloudflare Pages

1. Push this repo to GitHub/GitLab.
2. Cloudflare dashboard → Workers & Pages → Create → Pages → connect the repo.
3. Build settings (also declared in `wrangler.toml`):
   - Build command: `npm run build`
   - Build output directory: `dist`
4. Set the `NODE_VERSION` environment variable to `24` (matches `.nvmrc`).
5. Every push to the production branch deploys; other branches get preview
   deployments.

After connecting, set the real domain in `astro.config.mjs` (`site`).
