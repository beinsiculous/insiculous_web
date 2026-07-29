// Post-build guardrails for the WASM drop-in convention and Cloudflare Pages limits.
// Run automatically via `npm run build` (astro build && node scripts/postbuild-check.mjs).
//
// 1. `public/games/<slug>/.../index.html` is forbidden: Astro copies `public/`
//    over the generated routes, so such a file would silently replace the
//    generated /games/<slug>/ page in dist/.
// 2. Cloudflare Pages rejects any single asset over 25 MiB. Catch oversized
//    files (usually .wasm) locally instead of at deploy time.

import { readdirSync, statSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const SIZE_LIMIT = 25 * 1024 * 1024; // Cloudflare Pages per-file limit
const errors = [];

function walk(dir, onFile) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) walk(path, onFile);
    else onFile(path);
  }
}

if (existsSync('public/games')) {
  walk('public/games', (path) => {
    if (path.endsWith('/index.html') || path.endsWith('\\index.html')) {
      errors.push(
        `${path}: index.html inside public/games/ would overwrite the generated game page in dist/. ` +
        `Drop in only the wasm-bindgen output (game.js, game_bg.wasm, assets) — never index.html.`
      );
    }
  });
}

if (existsSync('dist')) {
  walk('dist', (path) => {
    const { size } = statSync(path);
    if (size > SIZE_LIMIT) {
      errors.push(
        `${path}: ${(size / 1024 / 1024).toFixed(1)} MiB exceeds Cloudflare Pages' 25 MiB per-file limit. ` +
        `For .wasm files try wasm-opt -Oz and a release profile with opt-level = "z", lto = true, strip = true.`
      );
    }
  });
}

if (errors.length > 0) {
  console.error('postbuild-check FAILED:\n');
  for (const err of errors) console.error(`  - ${err}\n`);
  process.exit(1);
}

console.log('postbuild-check: OK');
