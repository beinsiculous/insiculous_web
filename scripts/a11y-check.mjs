// Accessibility gate: serve dist/ locally, run axe-core (WCAG 2.0/2.2 A+AA) on every page, and
// fail the build on any violation. Runs as part of `npm run verify`, so a regression blocks a
// deploy exactly like a type error does.
//
// axe finds roughly half of real-world issues — the rest is the manual checklist in README
// (keyboard pass, screen-reader pass, zoom/reflow). Zero violations here is necessary, not
// sufficient.
//
// Usage:
//   npm run build, then `npm run a11y`
//   A11Y_ONLY=games node scripts/a11y-check.mjs   (substring filter, for iterating)
import { createServer } from "node:http";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const DIST = resolve(import.meta.dirname, "..", "dist");
const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".webp": "image/webp",
  ".wasm": "application/wasm",
  ".woff2": "font/woff2",
  ".txt": "text/plain",
  ".xml": "application/xml",
};

function walk(dir, onFile) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) walk(path, onFile);
    else onFile(path);
  }
}

// Every route the site serves: each index.html, plus standalone pages like 404.html.
const routes = [];
walk(DIST, (path) => {
  if (extname(path) !== ".html") return;
  const rel = path.slice(DIST.length).replaceAll("\\", "/");
  const route = rel.endsWith("/index.html") ? rel.slice(0, -"index.html".length) : rel;
  routes.push(route);
});
routes.sort();

const only = process.env.A11Y_ONLY;
const chosen = only ? routes.filter((r) => r.includes(only)) : routes;
if (only && chosen.length === 0) {
  console.error(`A11Y_ONLY='${only}' matched no route. Routes:\n  ${routes.join("\n  ")}`);
  process.exit(1);
}

// Minimal static server mirroring wrangler's assets behavior: /foo/ -> /foo/index.html,
// unknown paths -> 404.html (not_found_handling = "404-page").
const server = createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  let path = join(DIST, decodeURIComponent(url.pathname));
  try {
    if (statSync(path).isDirectory()) path = join(path, "index.html");
    const body = readFileSync(path);
    res.writeHead(200, { "content-type": MIME[extname(path)] ?? "application/octet-stream" });
    res.end(body);
  } catch {
    res.writeHead(404, { "content-type": MIME[".html"] });
    res.end(readFileSync(join(DIST, "404.html")));
  }
});
await new Promise((resolveListen) => server.listen(0, resolveListen));
const port = server.address().port;

const SEEDED_PROFILE = {
  schemaVersion: 3, theme: "fort-knight", epochOverride: null, timezone: null, activeSeasonId: null,
  weightsProfiles: { "lucky-garden-poet": { id: "lucky-garden-poet", questionnaire: { answers: {} } } },
  activeWeightsId: "lucky-garden-poet", hidden: [], overrides: {}, added: [], dayNotes: {},
};

// [route, function run in the page that opens the dialog and returns whether it managed to]
// /profile/ carries the studio's rule set (app-widgets.css); a face page carries faces.css.
const DIALOG_ROUTES = [
  ["/profile/", () => {
    const button = document.getElementById("duplicateProfileButton");
    if (!button || button.hidden) return false;
    button.click();
    return true;
  }],
  // The face-side entry lived here and opened the dialog through the nav's "New profile…" option. That
  // option is not offered while the faces are placeholders, so the dialog cannot be reached on a face page
  // on this branch and there is nothing here to audit. faces.css's copy of the dialog rules is still
  // exercised on the face branches, where the questionnaire is real; this entry returns with them.
];

const failures = [];
let analyzed = 0;
const browser = await chromium.launch();
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  // The faces only render their full UI once a profile exists locally — same seeding the
  // screenshot harness uses, so axe sees what a returning user sees.
  // My Fort renders entirely from a seed in localStorage. Without this the page audited is a file picker
  // on an otherwise empty page, and the one hard requirement it has — being readable across a room — is
  // checked by a gate that never sees it. The fixture is invented, not anybody's fortnight.
  const myFortSeed = readFileSync(new URL("../tests/fixtures/myfort.sample.json", import.meta.url), "utf8");
  // The /profile/ achievements board renders its headings, lists and delete button only when a game
  // has recorded unlocks — seed one invented save so axe audits the populated board, not just the
  // empty state (the value is the engine's save-file shape, games-achievements.js).
  const pongAchievements = JSON.stringify({
    unlocks: { win_normal: { unlocked_at: 1756252800 }, beat_cpu_easy: { unlocked_at: 1756339200 } },
  });
  await page.addInitScript(([settings, seed, achievements]) => {
    localStorage.setItem("fortknight.user-settings", settings);
    localStorage.setItem("beinsiculous.myfort-seed", seed);
    localStorage.setItem("beinsiculous.games.pong.achievements", achievements);
  }, [JSON.stringify({ schemaVersion: 2 }), myFortSeed, pongAchievements]);
  for (const route of chosen) {
    await page.goto(`http://localhost:${port}${route}`, { waitUntil: "networkidle" });
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze();
    analyzed++;
    for (const violation of results.violations) {
      const targets = violation.nodes.map((node) => node.target.join(" ")).join("; ");
      failures.push(`${route}  [${violation.id}] ${violation.help}\n    ${targets}`);
    }
  }

  // The profile-name dialog (src/lib/profile-name-dialog.js) is built in JavaScript and only exists once
  // something opens it, so the page sweep above can never see it — and postbuild-check, which reads
  // static HTML, cannot either. It is the site's only <dialog>, and its CSS is written twice (once in
  // app-widgets.css for the studio's /profile/, once in faces.css for the faces), so both rule sets are
  // checked here: open it on one page of each and run the same rules against it.
  // Both controls that open it are hidden until a profile is actually saved, so this pass needs a
  // richer seed than the sweep above: one saved profile, which is also the state a real person is in
  // when they meet the dialog.
  const dialogContext = await browser.newContext();
  await dialogContext.addInitScript((settings) => {
    localStorage.setItem("fortknight.user-settings", settings);
  }, JSON.stringify(SEEDED_PROFILE));
  const dialogPage = await dialogContext.newPage();
  for (const [route, open] of DIALOG_ROUTES) {
    await dialogPage.goto(`http://localhost:${port}${route}`, { waitUntil: "networkidle" });
    const opened = await dialogPage.evaluate(open);
    if (!opened) {
      failures.push(`${route}  [dialog] could not open the profile-name dialog — the a11y pass over it did not run`);
      continue;
    }
    await dialogPage.waitForSelector("dialog.name-dialog[open]", { timeout: 5000 });
    const results = await new AxeBuilder({ page: dialogPage })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze();
    analyzed++;
    for (const violation of results.violations) {
      const targets = violation.nodes.map((node) => node.target.join(" ")).join("; ");
      failures.push(`${route} (dialog open)  [${violation.id}] ${violation.help}\n    ${targets}`);
    }
  }
  await dialogContext.close();
} finally {
  await browser.close();
  server.close();
}

if (failures.length > 0) {
  console.error(`a11y-check FAILED — ${failures.length} violation(s) across ${analyzed} page(s):\n`);
  for (const failure of failures) console.error(`  - ${failure}\n`);
  process.exit(1);
}
console.log(`a11y-check: OK — ${analyzed} page(s), no WCAG 2.0/2.2 A+AA violations`);
