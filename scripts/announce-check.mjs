// Announce gate: serve dist/ locally, capture Playwright's ariaSnapshot (the browser's
// accessibility tree) on every page, and assert screen-reader structural invariants:
// 1. Landmarks: exactly one main, at least one navigation, a banner and a contentinfo.
// 2. Headings: exactly one level-1 heading, it comes first, and no heading level is skipped.
// 3. Controls: every link, button, textbox, combobox, checkbox, radio, slider, switch, tab,
//    and menuitem has an accessible name.
// 4. Named regions and dialogs: every region and dialog node has an accessible name.
// 5. Sentinels: seeded storage on the main sweep verifies that expected headings render.
//
// This is the honest mechanical check for the pull-request template's screen-reader line:
// it verifies what an assistive technology announces as structural landmarks, headings,
// and interactive controls. It CANNOT hear pronunciation, verbosity, or live-region timing;
// when a new interaction lands, a real listen with VoiceOver or NVDA is still required.
//
// Technical note on desktop face navigation:
// The <nav> landmarks in the face header live inside a closed <details class="menu"> that is
// made visible on desktop viewports by `.site-nav .menu::details-content { content-visibility: visible }`
// (faces.css:118, Chromium's pseudo-element). If a future Playwright bump fails face landmarks,
// verify details-content pseudo-element support first.
//
// The heading rules cover every page in dist/, including devlog posts: a post that opens
// with `###` (h3) directly under the page's `h1` will fail this gate by design.
//
// Usage:
//   npm run build, then `npm run announce`
//   ANNOUNCE_ONLY=games node scripts/announce-check.mjs   (substring filter, for iterating)

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { chromium } from "playwright";
import { distRoutes, serveDist } from "./lib/serve-dist.mjs";
import {
  addPopulatedStateInitScript,
  OPENED_ELEMENT_ROUTES,
} from "./lib/a11y-scenarios.mjs";
import {
  announceFindings,
  missingSentinels,
  parseAriaSnapshot,
} from "./lib/announce-tree.mjs";

const DIST = resolve(import.meta.dirname, "..", "dist");

const SENTINELS = {
  "/profile/": [
    "Insiculous Pong — 8 unlocked",
    "Be Insiculous — 11 unlocked",
    "FortKnight — 1 unlocked",
  ],
  "/games/": [
    "Insiculous Pong — 8 unlocked",
  ],
  "/fortknight/keep/": [
    "Sunday A",
  ],
  "/fortknight/days/sun-a/": [
    "Sunday A",
  ],
  "/fortknight/": [
    "Your fortnight",
  ],
};

function isRedirectStub(distDir, route) {
  const relativePath = route.endsWith(".html")
    ? route.replace(/^\//, "")
    : join(route.replace(/^\//, ""), "index.html");
  const fullPath = join(distDir, relativePath);
  try {
    const html = readFileSync(fullPath, "utf8");
    return html.includes('http-equiv="refresh"');
  } catch {
    return false;
  }
}

const allRoutes = distRoutes(DIST);
const only = process.env.ANNOUNCE_ONLY;
const filteredRoutes = only ? allRoutes.filter((route) => route.includes(only)) : allRoutes;

if (only && filteredRoutes.length === 0) {
  console.error(`ANNOUNCE_ONLY='${only}' matched no route. Routes:\n  ${allRoutes.join("\n  ")}`);
  process.exit(1);
}

const { server, port } = await serveDist(DIST);

const failures = [];
let analyzedPages = 0;
const browser = await chromium.launch();

try {
  // 1. Main sweep across routes
  const mainContext = await browser.newContext();
  const mainPage = await mainContext.newPage();
  await addPopulatedStateInitScript(mainPage);

  for (const route of filteredRoutes) {
    if (isRedirectStub(DIST, route)) {
      console.log(`skip ${route} (redirect stub)`);
      continue;
    }

    await mainPage.goto(`http://localhost:${port}${route}`, { waitUntil: "networkidle" });
    const yaml = await mainPage.locator("body").ariaSnapshot();
    const nodes = parseAriaSnapshot(yaml);
    const findings = announceFindings(nodes);

    const missing = missingSentinels(route, nodes, SENTINELS);
    for (const item of missing) {
      findings.push(`missing sentinel heading: "${item}"`);
    }

    analyzedPages += 1;
    if (findings.length > 0) {
      for (const finding of findings) {
        failures.push(`${route}: ${finding}`);
      }
    }
  }
  await mainContext.close();

  // 2. Scenarios sweep (each scenario runs in its own context seeded with its own records only)
  for (const { route, seed, label, viewport, open, waitFor } of OPENED_ELEMENT_ROUTES) {
    if (only && !route.includes(only)) {
      continue;
    }

    const scenarioContext = await browser.newContext(viewport ? { viewport } : {});
    await scenarioContext.addInitScript((records) => {
      for (const [key, value] of Object.entries(records)) {
        localStorage.setItem(key, value);
      }
    }, seed);

    const scenarioPage = await scenarioContext.newPage();
    try {
      await scenarioPage.goto(`http://localhost:${port}${route}`, { waitUntil: "networkidle" });
      const openResult = await scenarioPage.evaluate(open);
      if (openResult !== true) {
        failures.push(`${route} (${label} open): failed to open disclosure — ${openResult}`);
        continue;
      }
      try {
        await scenarioPage.waitForSelector(waitFor, { timeout: 5000 });
      } catch {
        // A disclosure that opened but never showed its content is this scenario's failure,
        // not the run's: the remaining scenarios still get their turn.
        failures.push(`${route} (${label} open): did not reach ${waitFor}`);
        continue;
      }
      const yaml = await scenarioPage.locator("body").ariaSnapshot();
      const nodes = parseAriaSnapshot(yaml);
      const findings = announceFindings(nodes);

      analyzedPages += 1;
      if (findings.length > 0) {
        for (const finding of findings) {
          failures.push(`${route} (${label} open): ${finding}`);
        }
      }
    } finally {
      await scenarioContext.close();
    }
  }
} finally {
  await browser.close();
  server.close();
}

if (failures.length > 0) {
  console.error(`announce-check FAILED — ${failures.length} finding(s) across ${analyzedPages} page(s):\n`);
  for (const failure of failures) {
    console.error(`  - ${failure}`);
  }
  process.exit(1);
}

console.log(`announce-check: OK — ${analyzedPages} page(s) and scenario(s) verified`);
