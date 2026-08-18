// Post-build guardrails for the WASM drop-in convention and Cloudflare Pages limits.
// Run automatically via `npm run build` (astro build && node scripts/postbuild-check.mjs).
//
// 1. `public/games/<slug>/.../index.html` is forbidden: Astro copies `public/`
//    over the generated routes, so such a file would silently replace the
//    generated /games/<slug>/ page in dist/.
// 2. Cloudflare Pages rejects any single asset over 25 MiB. Catch oversized
//    files (usually .wasm) locally instead of at deploy time.
// 3. Every `wasm`/`screenshots` path referenced in games frontmatter must
//    exist as a file in dist/ — a typo'd path should fail the build, not
//    surface when a visitor hits Play.
// 4. Static accessibility checks on every built page: <html lang>, exactly one <h1>, alt on
//    every <img>, no positive tabindex, no duplicate ids. (The deep audit is
//    scripts/a11y-check.mjs, run by `npm run verify`.)

import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';

// Anchor to the project root regardless of cwd.
const ROOT = resolve(import.meta.dirname, '..');
const DIST = join(ROOT, 'dist');
const PUBLIC_GAMES = join(ROOT, 'public', 'games');
const CONTENT_GAMES = join(ROOT, 'src', 'content', 'games');

const SIZE_LIMIT = 25 * 1024 * 1024; // Cloudflare Pages per-file limit
const errors = [];

function walk(dir, onFile) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) walk(path, onFile);
    else onFile(path);
  }
}

if (existsSync(PUBLIC_GAMES)) {
  walk(PUBLIC_GAMES, (path) => {
    // Case-insensitive: Index.html on a case-insensitive filesystem would
    // still be served as the directory index.
    if (basename(path).toLowerCase() === 'index.html') {
      errors.push(
        `${path}: index.html inside public/games/ would overwrite the generated game page in dist/. ` +
        `Drop in only the wasm-bindgen output (game.js, game_bg.wasm, assets) — never index.html.`
      );
    }
  });
}

if (existsSync(DIST)) {
  walk(DIST, (path) => {
    const { size } = statSync(path);
    if (size > SIZE_LIMIT) {
      errors.push(
        `${path}: ${(size / 1024 / 1024).toFixed(1)} MiB exceeds Cloudflare Pages' 25 MiB per-file limit. ` +
        `For .wasm files try wasm-opt -Oz and a release profile with opt-level = "z", lto = true, strip = true.`
      );
    }
  });
}

// Frontmatter asset references: naive-but-sufficient extraction for this
// repo's own frontmatter style (quoted paths; screenshots as an inline
// [...] array or "- item" lines).
if (existsSync(DIST) && existsSync(CONTENT_GAMES)) {
  walk(CONTENT_GAMES, (path) => {
    if (!path.endsWith('.md')) return;
    const source = readFileSync(path, 'utf8');
    const frontmatter = source.split(/^---\s*$/m)[1] ?? '';
    const refs = [];

    const wasm = frontmatter.match(/^wasm:\s*['"]([^'"]+)['"]/m);
    if (wasm) refs.push(wasm[1]);

    const inline = frontmatter.match(/^screenshots:\s*\[([^\]]*)\]/m);
    const block = frontmatter.match(/^screenshots:\s*\n((?:\s+-\s+.*\n?)+)/m);
    for (const list of [inline?.[1], block?.[1]]) {
      if (!list) continue;
      for (const quoted of list.matchAll(/['"]([^'"]+)['"]/g)) refs.push(quoted[1]);
    }

    for (const ref of refs) {
      const target = join(DIST, ref.replace(/^\//, ''));
      if (!existsSync(target) || !statSync(target).isFile()) {
        errors.push(
          `${path}: references '${ref}' but ${target} does not exist. ` +
          `Asset paths must point at real files under public/ (copied to dist/ at build).`
        );
      }
    }
  });
}

// Cheap static accessibility checks on the built HTML. The deep audit is scripts/a11y-check.mjs
// (axe-core in a real browser, part of `npm run verify`); these run on every build with no browser
// at all, so the obvious regressions fail fast.
if (existsSync(DIST)) {
  walk(DIST, (path) => {
    if (!path.endsWith('.html')) return;
    const html = readFileSync(path, 'utf8');

    if (!/<html[^>]*\blang=/.test(html)) {
      errors.push(`${path}: <html> has no lang attribute — screen readers need it to pick a voice.`);
    }

    const h1Count = (html.match(/<h1[\s>]/g) || []).length;
    if (h1Count !== 1) {
      errors.push(`${path}: expected exactly one <h1>, found ${h1Count}.`);
    }

    for (const img of html.matchAll(/<img\b[^>]*>/g)) {
      if (!/\balt=/.test(img[0])) {
        errors.push(`${path}: <img> without an alt attribute: ${img[0].slice(0, 120)}`);
      }
    }

    // Positive tabindex breaks the natural focus order; 0 and -1 are the only legal values here.
    const badTabindex = html.match(/tabindex="[1-9]/);
    if (badTabindex) {
      errors.push(`${path}: positive tabindex (${badTabindex[0]}) — use 0 or -1 only.`);
    }

    const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]);
    const duplicated = ids.filter((id, index) => ids.indexOf(id) !== index);
    if (duplicated.length > 0) {
      errors.push(`${path}: duplicate id(s): ${[...new Set(duplicated)].join(', ')}`);
    }
  });
}

if (errors.length > 0) {
  console.error('postbuild-check FAILED:\n');
  for (const err of errors) console.error(`  - ${err}\n`);
  process.exit(1);
}

console.log('postbuild-check: OK');
