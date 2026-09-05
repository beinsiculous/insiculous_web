// Accessibility gate: serve dist/ locally, run axe-core (WCAG 2.0/2.2 A+AA) on every page, and
// fail the build on any violation. Runs as part of `npm run verify`, so a regression blocks a
// deploy exactly like a type error does. The keep-fed pages are audited twice, once per invented
// Keep fixture: the second household's pass is what certifies the positional season palette's
// contrast on a keep that is not the original household's.
//
// axe finds roughly half of real-world issues — the rest is the manual checklist in README
// (keyboard pass, screen-reader pass, zoom/reflow). Zero violations here is necessary, not
// sufficient.
//
// Usage:
//   npm run build, then `npm run a11y`
//   A11Y_ONLY=games node scripts/a11y-check.mjs   (substring filter, for iterating)
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";
import { distRoutes, serveDist } from "./lib/serve-dist.mjs";

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

const SEEDED_PROFILE = {
  schemaVersion: 3, theme: "fort-knight", epochOverride: null, timezone: null, activeSeasonId: null,
  weightsProfiles: { "lucky-garden-poet": { id: "lucky-garden-poet", questionnaire: { answers: {} } } },
  activeWeightsId: "lucky-garden-poet", hidden: [], overrides: {}, added: [], dayNotes: {},
};

// One invented site unlock is enough for the prompt entry below: shouldPromptForProfile
// (src/lib/achievements.js) gates on any achievement, no saved profile, flag unset.
const SEEDED_SITE_ACHIEVEMENTS = JSON.stringify({ unlocks: { player: { unlocked_at: 1756425600 } } });

const keepSeed = readFileSync(new URL("../tests/fixtures/keep.sample.json", import.meta.url), "utf8");
// A keep whose season focuses on every category, built from the sample so nothing else about it changes.
// The seven come from data/categories.json — the shipped default and the list's one authored home — so
// this file does not carry a copy of the closed set.
const categories = JSON.parse(readFileSync(new URL("../data/categories.json", import.meta.url), "utf8"));
const everyStoneFocus = categories.order.map((key) => ({ key, label: categories.categories[key].label }));
const sampleKeep = JSON.parse(keepSeed);
const everyStoneKeepSeed = JSON.stringify({ ...sampleKeep, season: { ...sampleKeep.season, focus: everyStoneFocus } });

/** What the page sweep cannot see, opened and then audited: one entry per element and state.
 *  { route, seed (localStorage records), label, viewport (optional; the default is desktop), open (runs
 *  in the page: returns true once the element is open, or a string saying what it found instead — the
 *  string fails the gate and skips the audit), waitFor (the selector that proves it opened) }.
 *
 *  The profile-name dialog (src/lib/profile-name-dialog.js) is built in JavaScript and exists only once
 *  something opens it, so neither the page sweep nor postbuild-check (static HTML) can see it. It is the
 *  site's only <dialog>, and its CSS is written twice — global.css for the studio pages, faces.css for
 *  the face — so it is opened on one page of each. The two entries want OPPOSITE states: /profile/'s
 *  Duplicate control is hidden until a profile is saved, while /fortknight/achievements/ opens the
 *  first-achievement prompt at boot only when achievements exist and NO profile is saved.
 *
 *  The face nav's Peripheral strip (src/components/FaceNav.astro) is a closed <details>, and axe prunes
 *  a closed details' contents, so its links are audited only here, open — in every state the bar can
 *  take: the sample keep's four focus pills with three stones behind Peripheral, no keep with all
 *  seven behind it, the same four-and-three inside the ☰ on a phone (the nested column has its own
 *  rules in faces.css), and a keep focusing on every stone, where the pill is hidden and seven are
 *  promoted. Each entry first asserts the partition it expects, so promotion — which the script does
 *  at boot and no other gate can observe — fails the build with the counts it saw. */
const OPENED_ELEMENT_ROUTES = [
  {
    route: "/profile/",
    seed: { "fortknight.user-settings": JSON.stringify(SEEDED_PROFILE) },
    label: "dialog",
    waitFor: "dialog.name-dialog[open]",
    open: () => {
      // The Duplicate control is hidden until a profile is saved; the seed above saves one.
      const button = document.getElementById("duplicateProfileButton");
      if (!button || button.hidden) return "could not open the profile-name dialog — the a11y pass over it did not run";
      button.click();
      return true;
    },
  },
  {
    route: "/fortknight/achievements/",
    seed: { "beinsiculous.achievements": SEEDED_SITE_ACHIEVEMENTS },
    label: "dialog",
    waitFor: "dialog.name-dialog[open]",
    // The page itself opens the prompt at boot; there is nothing to click, so wait for the dialog.
    open: async () => {
      for (let attempt = 0; attempt < 50; attempt += 1) {
        if (document.querySelector("dialog.name-dialog[open]")) return true;
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      return "could not open the profile-name dialog — the a11y pass over it did not run";
    },
  },
  {
    route: "/fortknight/fixknitt/",
    seed: { "beinsiculous.keep": keepSeed },
    label: "peripheral",
    waitFor: "details.nav-peripheral[open]",
    open: () => {
      const promoted = Array.from(document.querySelectorAll(".nav-links > a[data-category]"));
      const inside = Array.from(document.querySelectorAll(".nav-peripheral-panel a[data-category]"));
      const promotedKeys = promoted.map((link) => link.dataset.category);
      const expectedKeys = ["meals", "cleaning", "working", "health"];
      const orderMatches = promotedKeys.length === 4 && promotedKeys.every((key, index) => key === expectedKeys[index]);
      if (!orderMatches || inside.length !== 3) {
        return `unexpected counts: promoted ${promoted.length} [${promotedKeys.join(", ")}], inside ${inside.length}`;
      }
      const details = document.querySelector("details.nav-peripheral");
      if (!details) return "details.nav-peripheral not found";
      details.open = true;
      return true;
    },
  },
  {
    route: "/fortknight/fixknitt/",
    seed: {},
    label: "peripheral",
    waitFor: "details.nav-peripheral[open]",
    open: () => {
      const promoted = Array.from(document.querySelectorAll(".nav-links > a[data-category]"));
      const inside = Array.from(document.querySelectorAll(".nav-peripheral-panel a[data-category]"));
      if (promoted.length !== 0 || inside.length !== 7) {
        return `unexpected counts: promoted ${promoted.length}, inside ${inside.length}`;
      }
      const details = document.querySelector("details.nav-peripheral");
      if (!details) return "details.nav-peripheral not found";
      details.open = true;
      return true;
    },
  },
  {
    // Inside the ☰ on a phone: the strip is a nested, indented column with rules of its own
    // (faces.css, `.menu-panel .nav-peripheral-panel`), and both disclosures must be open to see it.
    route: "/fortknight/fixknitt/",
    seed: { "beinsiculous.keep": keepSeed },
    label: "peripheral, phone",
    viewport: { width: 390, height: 844 },
    waitFor: "details.nav-peripheral[open]",
    open: () => {
      const promoted = Array.from(document.querySelectorAll(".nav-links > a[data-category]"));
      const inside = Array.from(document.querySelectorAll(".nav-peripheral-panel a[data-category]"));
      if (promoted.length !== 4 || inside.length !== 3) {
        return `unexpected counts: promoted ${promoted.length}, inside ${inside.length}`;
      }
      const menu = document.querySelector("details.menu");
      const details = document.querySelector("details.nav-peripheral");
      if (!menu || !details) return "details.menu or details.nav-peripheral not found";
      menu.open = true;
      details.open = true;
      return true;
    },
  },
  {
    // Every stone a focus: seven promoted pills and the Peripheral pill hidden — the one branch no
    // fixture reaches. There is nothing to open; the bar itself is what axe audits.
    route: "/fortknight/fixknitt/",
    seed: { "beinsiculous.keep": everyStoneKeepSeed },
    label: "peripheral, every stone a focus",
    waitFor: ".nav-links > a[data-category]",
    open: () => {
      const promoted = Array.from(document.querySelectorAll(".nav-links > a[data-category]"));
      const inside = Array.from(document.querySelectorAll(".nav-peripheral-panel a[data-category]"));
      const details = document.querySelector("details.nav-peripheral");
      if (!(details instanceof HTMLDetailsElement)) return "details.nav-peripheral not found";
      if (promoted.length !== 7 || inside.length !== 0 || !details.hidden) {
        return `unexpected state: promoted ${promoted.length}, inside ${inside.length}, peripheral hidden ${details.hidden}`;
      }
      return true;
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
  // Keep renders entirely from a keep in localStorage. Without this the page audited is a file picker
  // on an otherwise empty page, and the one hard requirement it has — being readable across a room — is
  // checked by a gate that never sees it. The fixture is invented, not anybody's fortnight.
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
    localStorage.setItem("beinsiculous.keep", seed);
    localStorage.setItem("beinsiculous.games.pong.achievements", gameUnlocks);
    localStorage.setItem("beinsiculous.achievements", siteUnlocks);
  }, [JSON.stringify({ schemaVersion: 2 }), keepSeed, pongAchievements, siteAchievements]);
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
  // strongest reason this second pass exists.
  const SEED_FED_ROUTES = new Set(["/fortknight/", "/fortknight/keep/", "/fortknight/folkknowledge/", "/fortknight/forkknife/"]);
  const keepFed = chosen.filter((route) =>
    SEED_FED_ROUTES.has(route) || route.startsWith("/fortknight/days/"));
  const otherHouseholdSeed = readFileSync(new URL("../tests/fixtures/keep.other-household.json", import.meta.url), "utf8");
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
