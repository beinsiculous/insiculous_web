// Copies FortKnight's canonical assets into this site: the built data bundle, the
// assistant-workspace source documents, the shared JS modules, the theme skin, the cursors,
// the vendored fonts and the theme images.
//
// The FortKnight repository (github.com/…/FortKnight) stays the source of truth for all of these —
// its data/ is validated and built by python3 scripts/build.py. This site only renders them, so the
// synced files are COMMITTED here: the Cloudflare build has no FortKnight checkout and must not need one.
//
// Usage: npm run sync:fortknight   (FORTKNIGHT_REPO=/path/to/FortKnight to point elsewhere)
import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const siteRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const fortknightRoot = resolve(siteRoot, process.env.FORTKNIGHT_REPO || "../FortKnight");

if (!existsSync(join(fortknightRoot, "app", "shared"))) {
  console.error(
    `No FortKnight checkout at ${fortknightRoot}.\n` +
    `Clone it beside this repository, or set FORTKNIGHT_REPO to its path.`
  );
  process.exit(1);
}

// Canonical JS modules live in FortKnight's app/shared/ (plain ES modules its Python-side tests
// drive through node); sync them in like the data rather than maintaining a second copy.
const SHARED_MODULES = [
  "fortknight-rules.js",
  "astronomy.js",
  "user-settings.js",
  "clock.js",
  "import-document.js",
  "import-review.js",
  "weights-rules.js",
  "generator-rules.js",
  "workspace-docs.js",
  "download.js",
  "day-plan.js",
  "allocations-rules.js",
  "allocation-bars.js",
  "workspace-files.js",
  "meal-plan.js",
];

// The assistant-workspace source documents (docs + schemas) the Profile and Assistant pages read at
// build time. Kept in step with WORKSPACE_STATIC_DOCUMENTS in app/shared/workspace-docs.js, which is
// imported from the checkout so the two can never drift.
const { WORKSPACE_STATIC_DOCUMENTS } = await import(
  pathToFileURL(join(fortknightRoot, "app", "shared", "workspace-docs.js"))
);

const bundle = join(fortknightRoot, "build", "fortknight.bundle.json");
if (!existsSync(bundle)) {
  console.error(`No data bundle at ${bundle}. Run python3 scripts/build.py in ${fortknightRoot} first.`);
  process.exit(1);
}

// Synced trees are replaced wholesale so files dropped upstream do not linger here.
for (const staleTree of [
  join(siteRoot, "src", "lib", "shared"),
  join(siteRoot, "src", "styles", "cursors"),
  join(siteRoot, "src", "data", "workspace"),
  join(siteRoot, "public", "app"),
]) {
  rmSync(staleTree, { recursive: true, force: true });
}

/** Every *.svg / *.woff2 / image in one of FortKnight's asset folders, as [source, target] pairs.
    A folder that does not exist yields nothing: no webfont is vendored today (Bungee was dropped when
    the themes went to system font stacks), but a theme may vendor one again. */
function assetsIn(sourceSegments, targetSegments, pattern) {
  const sourceDirectory = join(fortknightRoot, ...sourceSegments);
  if (!existsSync(sourceDirectory)) return [];
  return readdirSync(sourceDirectory)
    .filter((name) => pattern.test(name))
    .map((name) => [join(sourceDirectory, name), join(siteRoot, ...targetSegments, name)]);
}

const copies = [
  // The bundle goes to both src/data (build-time import for the static pages; being in the module
  // graph makes `astro dev` reload on data changes) and public/ (client-side fetch for the date
  // resolver and the assistant pages).
  [bundle, join(siteRoot, "src", "data", "bundle.json")],
  [bundle, join(siteRoot, "public", "bundle.json")],
  ...Object.entries(WORKSPACE_STATIC_DOCUMENTS).map(([fileName, source]) => [
    join(fortknightRoot, ...source.split("/")),
    join(siteRoot, "src", "data", "workspace", fileName),
  ]),
  ...SHARED_MODULES.map((fileName) => [
    join(fortknightRoot, "app", "shared", fileName),
    join(siteRoot, "src", "lib", "shared", fileName),
  ]),
  // The mouse cursors, inlined by Vite from src/styles/ (faces.css references them relatively).
  ...assetsIn(["app", "shared", "cursors"], ["src", "styles", "cursors"], /\.svg$/),
  // Theme skin + any vendored fonts + theme photographs, mirrored at their repo-relative paths so
  // themes.css's url(../fonts/…) and url(../images/…) resolve from the mirror.
  [join(fortknightRoot, "app", "shared", "themes.css"), join(siteRoot, "public", "app", "shared", "themes.css")],
  ...assetsIn(["app", "fonts"], ["public", "app", "fonts"], /\.woff2$/),
  ...assetsIn(["app", "images"], ["public", "app", "images"], /\.(jpe?g|png|webp|svg)$/),
];

for (const [source, target] of copies) {
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(source, target);
  console.log(`synced ${source} -> ${target}`);
}
