// Accessibility gate: serve dist/ locally, run axe-core (WCAG 2.0/2.2 A+AA) on every page, and
// fail the build on any violation. Runs as part of `npm run verify`, so a regression blocks a
// deploy exactly like a type error does. The seed-fed pages are audited twice, once per invented
// My Fort fixture: the second household's pass is what certifies the positional season palette's
// contrast on a seed that is not the original household's.
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

// One invented site unlock is enough for the prompt entry below: shouldPromptForProfile
// (src/lib/achievements.js) gates on any achievement, no saved profile, flag unset.
const SEEDED_SITE_ACHIEVEMENTS = JSON.stringify({ unlocks: { player: { unlocked_at: 1756425600 } } });

// [route, localStorage records to seed, function run in the page that opens the dialog (or waits
// for the one the page itself opens) and returns whether it managed to]
// /profile/ carries the studio's rule set (global.css, like every BaseLayout page); a face page
// carries faces.css. The two entries want OPPOSITE states: /profile/'s Duplicate control is hidden
// until a profile is saved, while the face entry audits the dialog the way a face page really opens
// it on this branch — the first-achievement prompt (maybePromptForProfile) fires at
// /fortknight/achievements/ boot only when achievements exist and NO profile is saved.
const DIALOG_ROUTES = [
  {
    route: "/profile/",
    seed: { "fortknight.user-settings": JSON.stringify(SEEDED_PROFILE) },
    open: () => {
      const button = document.getElementById("duplicateProfileButton");
      if (!button || button.hidden) return false;
      button.click();
      return true;
    },
  },
  {
    route: "/fortknight/achievements/",
    seed: { "beinsiculous.achievements": SEEDED_SITE_ACHIEVEMENTS },
    // The page itself opens the prompt at boot; there is nothing to click, so wait for the dialog.
    open: async () => {
      for (let attempt = 0; attempt < 50; attempt += 1) {
        if (document.querySelector("dialog.name-dialog[open]")) return true;
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      return false;
    },
  },
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
  // has recorded unlocks — seed invented saves so axe audits the populated board, not just the
  // empty state (the value is the engine's save-file shape, games-achievements.js). There are this
  // MANY on purpose: enough rows that the board's 75vh scroll box genuinely overflows, so axe's
  // scrollable-region-focusable rule has a real scrollable region to test rather than passing as
  // inapplicable.
  const pongAchievements = JSON.stringify({
    unlocks: {
      win_normal: { unlocked_at: 1756252800 }, beat_cpu_easy: { unlocked_at: 1756339200 },
      marathon_win: { unlocked_at: 1756512000 }, chaos_survivor: { unlocked_at: 1756598400 },
      perfect_round: { unlocked_at: 1756684800 }, comebacks: { unlocked_at: 1756771200 },
      untouchable: { unlocked_at: 1756857600 }, hat_trick: { unlocked_at: 1756944000 },
    },
  });
  // The /fortknight/achievements/ page and the /profile/ panel group every achievement by type, and
  // the site's own two types (insiculous and fortknight, registry in src/lib/achievements.js) render
  // populated only when their one store has unlocks — seed the two initial achievements invented,
  // in the same save-file shape the games write (games-achievements.js). The ids past those two are
  // invented and deliberately NOT in the registry: unknown ids still render, prettified, in the
  // insiculous group (loadSiteAchievements), and they are what makes the /profile/ and /achievements/
  // boards long enough to overflow their 75vh boxes for the rule named above.
  const siteAchievements = JSON.stringify({
    unlocks: {
      player: { unlocked_at: 1756425600 }, "moved-in": { unlocked_at: 1757030400 },
      night_owl: { unlocked_at: 1757116800 }, early_bird: { unlocked_at: 1757203200 },
      completionist: { unlocked_at: 1757289600 }, explorer: { unlocked_at: 1757376000 },
      tinkerer: { unlocked_at: 1757462400 }, regular: { unlocked_at: 1757548800 },
      champion_run: { unlocked_at: 1757635200 }, pixel_pusher: { unlocked_at: 1757721600 },
      speedrun_spirit: { unlocked_at: 1757808000 }, hidden_gem: { unlocked_at: 1757894400 },
    },
  });
  await page.addInitScript(([settings, seed, gameUnlocks, siteUnlocks]) => {
    localStorage.setItem("fortknight.user-settings", settings);
    localStorage.setItem("beinsiculous.myfort-seed", seed);
    localStorage.setItem("beinsiculous.games.pong.achievements", gameUnlocks);
    localStorage.setItem("beinsiculous.achievements", siteUnlocks);
  }, [JSON.stringify({ schemaVersion: 2 }), myFortSeed, pongAchievements, siteAchievements]);
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

  // The pages that render from the stored seed — the Overview, My Fort and the fourteen day pages —
  // are the only output that changes with the seed, so only they get a second pass, seeded with the
  // other invented household. Its season ids and names are not the ones the original palette was
  // keyed to, which is exactly what certifies the positional palette's contrast on a seed that is
  // not the original household's; re-auditing the rest of the site would audit identical output.
  const seedFed = chosen.filter((route) =>
    route === "/fortknight/" || route === "/fortknight/myfort/" || route.startsWith("/fortknight/days/"));
  const otherHouseholdSeed = readFileSync(new URL("../tests/fixtures/myfort.other-household.json", import.meta.url), "utf8");
  const otherHouseholdContext = await browser.newContext();
  await otherHouseholdContext.addInitScript(([settings, seed]) => {
    localStorage.setItem("fortknight.user-settings", settings);
    localStorage.setItem("beinsiculous.myfort-seed", seed);
  }, [JSON.stringify({ schemaVersion: 2 }), otherHouseholdSeed]);
  const otherHouseholdPage = await otherHouseholdContext.newPage();
  for (const route of seedFed) {
    await otherHouseholdPage.goto(`http://localhost:${port}${route}`, { waitUntil: "networkidle" });
    const results = await new AxeBuilder({ page: otherHouseholdPage })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze();
    analyzed++;
    for (const violation of results.violations) {
      const targets = violation.nodes.map((node) => node.target.join(" ")).join("; ");
      failures.push(`${route} (seed: other-household)  [${violation.id}] ${violation.help}\n    ${targets}`);
    }
  }
  await otherHouseholdContext.close();

  // The profile-name dialog (src/lib/profile-name-dialog.js) is built in JavaScript and only exists once
  // something opens it, so the page sweep above can never see it — and postbuild-check, which reads
  // static HTML, cannot either. It is the site's only <dialog>, and its CSS is written twice (once in
  // global.css for the studio pages, once in faces.css for the faces), so both rule sets are
  // checked here: open it on one page of each and run the same rules against it. Each entry carries
  // its own seed because the two open paths want opposite states (the DIALOG_ROUTES comment says which).
  for (const { route, seed, open } of DIALOG_ROUTES) {
    const dialogContext = await browser.newContext();
    await dialogContext.addInitScript((records) => {
      for (const [key, value] of Object.entries(records)) localStorage.setItem(key, value);
    }, seed);
    const dialogPage = await dialogContext.newPage();
    try {
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
    } finally {
      await dialogContext.close();
    }
  }
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
