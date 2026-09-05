// Layout gate (and dev utility): fail loudly on any page that answers anything but 200 or scrolls
// sideways, and screenshot the named surfaces so the identities can be compared. Runs in
// `npm run verify` and in CI with LARGE_TEXT=1, so a regression blocks the deploy exactly like a
// type error does.
//
// The routes are every page of the built site — walked from dist/ exactly like the a11y gate
// (scripts/lib/serve-dist.mjs), so a new page is covered the moment it builds and "every page"
// means every page. The curated names below only decide which routes get a PNG in shots/; the
// 200 + overflow measurements run on all of them.
//
// The studio pages wear BaseLayout's dark mono look (the Profile page among them); FortKnight brings
// its own skin from public/app/shared/themes.css (the page's face picks it — see src/lib/faces.js).
// The keep-fed pages render from the invented keep fixture seeded below (the same one the a11y
// gate uses) — without it they would all measure the empty file-picker state instead of the
// fourteen panels.
//
// Every pass measures the document's horizontal overflow: a viewport that scrolls sideways is a
// layout bug at any size, not a preference, so a non-zero reading is reported per page and makes
// the run exit non-zero. The phone is where it actually bites, but a desktop reading is a bug too
// and this will fail on it. Keep both at zero.
//
// Usage:
//   npm run build, then `npm run shots` — dist/ is served on an ephemeral port
//   PREVIEW_URL=http://localhost:4321 npm run shots   (audit a running dev/preview server; the
//                                                      route list still comes from dist/)
//   ONLY=mobile node scripts/screenshot-pages.mjs      (one viewport)
//   FULL_PAGE=1 node scripts/screenshot-pages.mjs      (whole scroll height, not just the fold)
//   LARGE_TEXT=1 node scripts/screenshot-pages.mjs     (extra pass: 125% text on a phone, overflow only)
// Output: shots/<name>.png and shots/<name>-mobile.png (gitignored).
import { chromium } from "playwright";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { distRoutes, serveDist } from "./lib/serve-dist.mjs";

const DIST = resolve(import.meta.dirname, "..", "dist");
if (!existsSync(join(DIST, "index.html"))) {
  console.error("dist/ is not built — run `npm run build` first.");
  process.exit(1);
}
const routes = distRoutes(DIST);

// Only published entries build a devlog post page — so an all-drafts devlog would silently drop
// that surface from the gate.
// Fail loudly instead: that state is a decision to make on purpose, not a coverage hole.
const devlogPostRoutes = routes.filter((route) => /^\/devlog\/.+\/$/.test(route));
if (devlogPostRoutes.length === 0) {
  console.error(
    "No devlog post page in dist/ (every entry under src/content/devlog/ is a draft?) — the post page would go untested. Release an entry, or change this gate on purpose."
  );
  process.exit(1);
}

// Which routes get a PNG, and under what name. "" is the desktop suffix so the existing shot
// names keep working; -mobile is the phone. Every other route is measured but not shot.
const shotNames = {
  "/": "studio-home",
  "/games/": "studio-games",
  "/achievements/": "studio-achievements",
  "/games/pong/": "studio-game",
  "/devlog/": "studio-devlog",
  [devlogPostRoutes[0]]: "studio-devlog-post",
  "/engine/": "studio-engine",
  "/playground/": "studio-playground",
  "/profile/": "profile",
  "/fortknight/": "fortknight-overview",
  "/fortknight/days/wed-b/": "fortknight-day",
  "/fortknight/achievements/": "fortknight-achievements",
  "/fortknight/folkknowledge/": "fortknight-folkknowledge",
  "/fortknight/forkknife/": "fortknight-forkknife",
};

// The phone pass emulates touch, so `@media (pointer: coarse)` — where the 44px tap targets live — is
// actually exercised rather than silently skipped.
const viewports = {
  desktop: { suffix: "", context: { viewport: { width: 1440, height: 900 } } },
  mobile: { suffix: "-mobile", context: { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } },
  // 641px: the first pixel above the 40rem phone breakpoint, where the wide layout has to stand on its
  // own. It is the worst case, and the only one worth gating — a panel pinned to its min-content width
  // stays that wide at every larger size, so a friendlier 768 or 1024 "tablet" passes while the bug is
  // still there (that is exactly how a 739px panel went unnoticed until it was measured here).
  tablet: { suffix: "-tablet", shots: false, context: { viewport: { width: 641, height: 900 } } },
  // LARGE_TEXT=1 only: the site at its largest Aa setting (125% root font), phone width. No shots —
  // this pass exists purely to prove big text reflows instead of breaking the layout (WCAG 1.4.4/1.4.10).
  largetext: {
    suffix: "-largetext",
    shots: false,
    context: { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true },
    initScript: () => localStorage.setItem("beinsiculous.a11y", JSON.stringify({ fontScale: 1.25 })),
  },
};
const only = process.env.ONLY;
const chosen = only
  ? { [only]: viewports[only] }
  : Object.fromEntries(
      // largetext is opt-in (LARGE_TEXT=1); desktop, mobile and tablet always run.
      Object.entries(viewports).filter(([label]) => label !== "largetext" || process.env.LARGE_TEXT)
    );
if (only && !viewports[only]) {
  console.error(`ONLY must be one of: ${Object.keys(viewports).join(", ")}`);
  process.exit(1);
}

// PREVIEW_URL audits a running server; otherwise dist/ is served here, like the a11y gate does.
let baseUrl = process.env.PREVIEW_URL;
let server;
if (!baseUrl) {
  ({ server } = await serveDist(DIST));
  baseUrl = `http://localhost:${server.address().port}`;
}

// Same seeding as the a11y gate's main sweep, minus the achievement stores: a saved profile so the
// faces render their full UI, and the invented keep fixture so the keep-fed pages measure the
// fourteen panels rather than an empty file picker. The fixture is invented, not anybody's fortnight.
const keepSeed = readFileSync(new URL("../tests/fixtures/keep.sample.json", import.meta.url), "utf8");

mkdirSync("shots", { recursive: true });
const browser = await chromium.launch();
const failures = [];
for (const [label, { suffix, context: contextOptions, initScript, shots = true }] of Object.entries(chosen)) {
  const context = await browser.newContext(contextOptions);
  await context.addInitScript(([settings, seed]) => {
    localStorage.setItem("fortknight.user-settings", settings);
    localStorage.setItem("beinsiculous.keep", seed);
  }, [JSON.stringify({ schemaVersion: 2 }), keepSeed]);
  if (initScript) await context.addInitScript(initScript);
  const page = await context.newPage();
  for (const route of routes) {
    const name = shotNames[route];
    const response = await page.goto(`${baseUrl}${route}`, { waitUntil: "networkidle" });
    // Anything but 200 must fail: the overflow reading of an error page proves nothing about the
    // page this route exists to serve.
    const status = response?.status();
    if (status !== 200) {
      failures.push(`${label} ${route}: answered ${status ?? "no response"}, not 200`);
      console.error(`${label} ${route} — NOT SERVED (${status ?? "no response"})`);
      continue;
    }
    if (shots && name) {
      await page.screenshot({ path: `shots/${name}${suffix}.png`, fullPage: Boolean(process.env.FULL_PAGE) });
    }
    // scrollWidth beyond clientWidth is content the viewport cannot reach without scrolling sideways.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    if (overflow > 0) {
      failures.push(`${label} ${route}: scrolls sideways by ${overflow}px`);
      console.error(`${label} ${route} — OVERFLOW ${overflow}px`);
    } else if (name) {
      console.log(`shot ${name}${suffix}`);
    }
  }
  await context.close();
}
await browser.close();
server?.close();

if (failures.length) {
  console.error(`\n${failures.length} page(s) failed the layout gate:\n  ${failures.join("\n  ")}`);
  process.exit(1);
}
console.log(
  `\n${routes.length} route(s) × ${Object.keys(chosen).length} viewport pass(es): every page answered 200 and no page scrolls sideways.`
);
