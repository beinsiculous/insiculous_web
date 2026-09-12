// Accessibility gate: serve dist/ locally, run axe-core (WCAG 2.0/2.2 A+AA) on every page, and
// fail the build on any violation. Runs as part of `npm run verify`, so a regression blocks a
// deploy exactly like a type error does. The keep-fed pages are audited twice, once per invented
// Keep fixture: tests/fixtures/keep.sample.json, and tests/fixtures/keep.other-household.json (via ./lib/a11y-scenarios.mjs).
// The second household's pass is what certifies the positional season palette's
// contrast on a keep that is not the original household's.
//
// axe finds roughly half of real-world issues — the rest is the manual checklist in README
// (keyboard pass, screen-reader pass, zoom/reflow). Zero violations here is necessary, not
// sufficient.
//
// Usage:
//   npm run build, then `npm run a11y`
//   A11Y_ONLY=games node scripts/a11y-check.mjs   (substring filter, for iterating)
import { resolve } from "node:path";
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";
import { distRoutes, serveDist } from "./lib/serve-dist.mjs";
import {
  addPopulatedStateInitScript,
  otherHouseholdSeed,
  SEED_FED_ROUTES,
  OPENED_ELEMENT_ROUTES,
} from "./lib/a11y-scenarios.mjs";
const DIST = resolve(import.meta.dirname, "..", "dist");

// Every route the site serves: each index.html, plus standalone pages like 404.html.
const routes = distRoutes(DIST);

const only = process.env.A11Y_ONLY;
const chosen = only ? routes.filter((r) => r.includes(only)) : routes;
if (only && chosen.length === 0) {
  console.error(`A11Y_ONLY='${only}' matched no route. Routes:\n  ${routes.join("\n  ")}`);
  process.exit(1);
}

// Minimal static server mirroring wrangler's assets behavior (scripts/lib/serve-dist.mjs).
const { server, port } = await serveDist(DIST);

const failures = [];
let analyzed = 0;
const browser = await chromium.launch();
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  await addPopulatedStateInitScript(page);
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

  // The pages that render from the stored keep are the only output that changes with the keep, so only
  // they get a second pass, seeded with the other invented household. Its season ids and names are not
  // the ones the original palette was keyed to, which is exactly what certifies the positional palette's
  // contrast on a keep that is not the original household's; re-auditing the rest of the site would
  // audit identical output.
  //
  // ADD A STONE PAGE HERE WHEN IT RENDERS KEEP CONTENT. The list is explicit rather than a prefix match
  // on /fortknight/ because most stone pages draw honest empty states, whose output does not vary with
  // the keep — auditing those twice would cost a browser context to prove nothing. A page that draws
  // season colours belongs here; /fortknight/folkknowledge/ draws the year wheel, which is the single
  const keepFed = chosen.filter((route) =>
    SEED_FED_ROUTES.has(route) || route.startsWith("/fortknight/days/"));
  const otherHouseholdContext = await browser.newContext();
  await otherHouseholdContext.addInitScript(([settings, seed]) => {
    localStorage.setItem("fortknight.user-settings", settings);
    localStorage.setItem("beinsiculous.keep", seed);
  }, [JSON.stringify({ schemaVersion: 2 }), otherHouseholdSeed]);
  const otherHouseholdPage = await otherHouseholdContext.newPage();
  for (const route of keepFed) {
    await otherHouseholdPage.goto(`http://localhost:${port}${route}`, { waitUntil: "networkidle" });
    const results = await new AxeBuilder({ page: otherHouseholdPage })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze();
    analyzed++;
    for (const violation of results.violations) {
      const targets = violation.nodes.map((node) => node.target.join(" ")).join("; ");
      failures.push(`${route} (keep: other-household)  [${violation.id}] ${violation.help}\n    ${targets}`);
    }
  }
  await otherHouseholdContext.close();

  // What the page sweep cannot see, opened first (OPENED_ELEMENT_ROUTES says what and why). Each entry
  // gets its own context, because the entries want different storage and, for the phone, a viewport.
  for (const { route, seed, label, viewport, open, waitFor } of OPENED_ELEMENT_ROUTES) {
    const openedContext = await browser.newContext(viewport ? { viewport } : {});
    await openedContext.addInitScript((records) => {
      for (const [key, value] of Object.entries(records)) localStorage.setItem(key, value);
    }, seed);
    const openedPage = await openedContext.newPage();
    try {
      await openedPage.goto(`http://localhost:${port}${route}`, { waitUntil: "networkidle" });
      const openResult = await openedPage.evaluate(open);
      if (openResult !== true) {
        failures.push(`${route} [${label}] ${openResult}`);
        continue;
      }
      await openedPage.waitForSelector(waitFor, { timeout: 5000 });
      const results = await new AxeBuilder({ page: openedPage })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze();
      analyzed++;
      for (const violation of results.violations) {
        const targets = violation.nodes.map((node) => node.target.join(" ")).join("; ");
        failures.push(`${route} (${label} open)  [${violation.id}] ${violation.help}\n    ${targets}`);
      }
    } finally {
      await openedContext.close();
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
