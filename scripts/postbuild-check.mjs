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
// 5. No word glued to an inline tag ("it is a<a>proving ground</a>"): Astro drops the newline
//    between a word and an inline tag that sit on different source lines, so correct-looking
//    copy can ship without the space. The rule lives in scripts/lib/glue-check.mjs; its three
//    exclusions (aria-hidden, .visually-hidden, empty elements) are the false-positive budget —
//    widen that list rather than loosening the patterns, and add the case to
//    tests/test_postbuild_check.py.
// 6. No straight apostrophe in rendered prose: the site's copy uses ’, which Markdown content gets
//    from smartypants — without this the .astro pages drift the other way and the two spellings sit
//    side by side on one page.
// 7. Every pill in a face's nav (src/lib/faces.js faceNav) resolves to a real page in dist/. Nothing
//    else notices a dead nav link: the visual gates walk dist/, so a route that does not exist is
//    simply absent from what they check.

import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';
import { findGluedBoundaries, findStraightApostrophes } from './lib/prose-check.mjs';

// Anchor to the project root regardless of cwd.
const ROOT = resolve(import.meta.dirname, '..');
const DIST = join(ROOT, 'dist');
const PUBLIC_GAMES = join(ROOT, 'public', 'games');
const PUBLIC_PLAYGROUND = join(ROOT, 'public', 'playground');
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

for (const [dir, label] of [
  [PUBLIC_GAMES, 'public/games/'],
  [PUBLIC_PLAYGROUND, 'public/playground/'],
]) {
  if (existsSync(dir)) {
    walk(dir, (path) => {
      // Case-insensitive: Index.html on a case-insensitive filesystem would
      // still be served as the directory index.
      if (basename(path).toLowerCase() === 'index.html') {
        errors.push(
          `${path}: index.html inside ${label} would overwrite the generated page in dist/. ` +
          `Drop in only the wasm-bindgen output (game.js, game_bg.wasm, assets) — never index.html.`
        );
      }
    });
  }
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

    // Every embed names its wasm glue in data-wasm-src (GameEmbed from frontmatter, PlaygroundEmbed
    // from its default); a bumped version dir that misses one leaves a page that says "Failed to
    // start" to every visitor, so the reference must resolve like a frontmatter one does.
    for (const match of html.matchAll(/data-wasm-src="([^"]+)"/g)) {
      const target = join(DIST, match[1].replace(/^\//, ''));
      if (!existsSync(target) || !statSync(target).isFile()) {
        errors.push(`${path}: embeds '${match[1]}' but ${target} does not exist.`);
      }
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

    // A lost space between a word and an inline tag — keep the tag on the same source line as
    // the word beside it, rather than letting a line break fall on the boundary.
    for (const boundary of findGluedBoundaries(html)) {
      errors.push(`${path}: word glued to an inline tag (${boundary.kind}): …${boundary.snippet}…`);
    }

    // The site's prose uses curly apostrophes; Markdown content gets them from smartypants, so a
    // straight one in an .astro page shows up next to a curly one on the same page.
    for (const apostrophe of findStraightApostrophes(html)) {
      errors.push(`${path}: straight apostrophe in prose (use ’): …${apostrophe.snippet}…`);
    }
  });
}

// 7. Every face nav pill points at a page that exists.
//
// This gate is here because its absence cost something real. The display-only removals landed the
// six-pill nav a day before three of those pills had pages, and for that day FortKnight's primary
// navigation carried dead links on every face page with nothing able to notice: this file had no link
// check, and a11y-check.mjs and screenshot-pages.mjs both walk dist/, where a route that does not exist
// simply is not there. The only thing standing in that spot was a written "dev → main is held" note —
// friction and a paper trail, not a check. So: a written hold is what you use while the pages are being
// built, and this is what makes forgetting to lift it impossible.
//
// Scoped to the face nav on purpose. A general internal-link crawler is a different, larger tool; this
// one checks the single list that is generated from code and rendered on every page of a face.
if (existsSync(DIST)) {
  // FACES and faceNav, not facePath: facePath goes through withBase(), which reads
  // import.meta.env.BASE_URL and exists only under Vite. Importing the module is fine — that value is
  // read when withBase is CALLED — so the route is composed from the face's own `home` instead, which
  // is the same string facePath would prefix. dist/ is laid out from the site root regardless of any
  // configured base path, so composing without it is also the correct thing to look up here.
  const { FACES, FACE_IDS, faceNav } = await import(new URL('../src/lib/faces.js', import.meta.url));
  for (const faceId of FACE_IDS) {
    for (const item of faceNav()) {
      const route = `${FACES[faceId].home}${item.path}`;
      if (!existsSync(join(DIST, route, 'index.html'))) {
        errors.push(
          `face nav "${item.label}" points at /${route}, which has no page in dist/. ` +
          `Add the route, or take the pill out of faceNav() in src/lib/faces.js until it exists.`
        );
      }
    }
  }
}

if (errors.length > 0) {
  console.error('postbuild-check FAILED:\n');
  for (const err of errors) console.error(`  - ${err}\n`);
  process.exit(1);
}

console.log('postbuild-check: OK');
