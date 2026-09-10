// Shared accessibility scenarios, seed fixtures and populated-state initialization
// used by the axe accessibility gate (a11y-check.mjs), the announce gate (announce-check.mjs),
// and the layout screenshot pass (screenshot-pages.mjs).
//
// Centralising these definitions ensures that all accessibility and layout gates audit the
// identical populated states and opened disclosure scenarios.

import { readFileSync } from "node:fs";

export const SEEDED_PROFILE = {
  schemaVersion: 3,
  theme: "fort-knight",
  epochOverride: null,
  timezone: null,
  activeSeasonId: null,
  weightsProfiles: {
    "lucky-garden-poet": { id: "lucky-garden-poet", questionnaire: { answers: {} } },
  },
  activeWeightsId: "lucky-garden-poet",
  hidden: [],
  overrides: {},
  added: [],
  dayNotes: {},
};

// One invented site unlock is enough for the profile-name dialog prompt:
// shouldPromptForProfile (src/lib/achievements.js) gates on any achievement, no saved profile, flag unset.
export const SEEDED_SITE_ACHIEVEMENTS = JSON.stringify({
  unlocks: { player: { unlocked_at: 1756425600 } },
});

export const sampleKeepSeed = readFileSync(
  new URL("../../tests/fixtures/keep.sample.json", import.meta.url),
  "utf8"
);

export const otherHouseholdSeed = readFileSync(
  new URL("../../tests/fixtures/keep.other-household.json", import.meta.url),
  "utf8"
);

// A keep whose season focuses on every category, built from the sample so nothing else about it changes.
// The seven come from data/categories.json — the shipped default and the list's one authored home — so
// this module does not carry a separate copy of the closed set.
const categories = JSON.parse(
  readFileSync(new URL("../../data/categories.json", import.meta.url), "utf8")
);
const everyStoneFocus = categories.order.map((key) => ({
  key,
  label: categories.categories[key].label,
}));
export const sampleKeep = JSON.parse(sampleKeepSeed);
export const everyStoneKeepSeed = JSON.stringify({
  ...sampleKeep,
  season: { ...sampleKeep.season, focus: everyStoneFocus },
});

// The /profile/ achievements board renders its headings, lists and delete button only when a game
// has recorded unlocks — seed invented saves so audits test the populated board, not just the
// empty state (the value is the engine's save-file shape, games-achievements.js). There are this
// many on purpose: enough rows that the board's 75vh scroll box genuinely overflows, so axe's
// scrollable-region-focusable rule has a real scrollable region to test rather than passing as
// inapplicable.
export const pongAchievements = JSON.stringify({
  unlocks: {
    win_normal: { unlocked_at: 1756252800 },
    beat_cpu_easy: { unlocked_at: 1756339200 },
    marathon_win: { unlocked_at: 1756512000 },
    chaos_survivor: { unlocked_at: 1756598400 },
    perfect_round: { unlocked_at: 1756684800 },
    comebacks: { unlocked_at: 1756771200 },
    untouchable: { unlocked_at: 1756857600 },
    hat_trick: { unlocked_at: 1756944000 },
  },
});

// The /fortknight/achievements/ page and the /profile/ panel group every achievement by type, and
// the site's own two types (insiculous and fortknight, registry in src/lib/achievements.js) render
// populated only when their one store has unlocks — seed the two initial achievements invented,
// in the same save-file shape the games write (games-achievements.js). The ids past those two are
// invented and deliberately not in the registry: unknown ids still render, prettified, in the
// insiculous group (loadSiteAchievements), and they are what makes the /profile/ board
// long enough to overflow its 75vh box for the rule named above.
export const siteAchievements = JSON.stringify({
  unlocks: {
    player: { unlocked_at: 1756425600 },
    "moved-in": { unlocked_at: 1757030400 },
    night_owl: { unlocked_at: 1757116800 },
    early_bird: { unlocked_at: 1757203200 },
    completionist: { unlocked_at: 1757289600 },
    explorer: { unlocked_at: 1757376000 },
    tinkerer: { unlocked_at: 1757462400 },
    regular: { unlocked_at: 1757548800 },
    champion_run: { unlocked_at: 1757635200 },
    pixel_pusher: { unlocked_at: 1757721600 },
    speedrun_spirit: { unlocked_at: 1757808000 },
    hidden_gem: { unlocked_at: 1757894400 },
  },
});

// Plant the four standard localStorage stores before navigation so pages see returning user state.
export async function addPopulatedStateInitScript(target) {
  await target.addInitScript(
    ([settings, seed, gameUnlocks, siteUnlocks]) => {
      localStorage.setItem("fortknight.user-settings", settings);
      localStorage.setItem("beinsiculous.keep", seed);
      localStorage.setItem("beinsiculous.games.pong.achievements", gameUnlocks);
      localStorage.setItem("beinsiculous.achievements", siteUnlocks);
    },
    [JSON.stringify({ schemaVersion: 2 }), sampleKeepSeed, pongAchievements, siteAchievements]
  );
}

// Keep-fed routes re-audited under the second household's keep fixture.
export const SEED_FED_ROUTES = new Set([
  "/fortknight/",
  "/fortknight/keep/",
  "/fortknight/folkknowledge/",
  "/fortknight/forkknife/",
]);

/** What the page sweep cannot see, opened and then audited: one entry per element and state.
 *  { route, seed (localStorage records), label, viewport (optional; the default is desktop), open (runs
 *  in the page: returns true once the element is open, or a string saying what it found instead — the
 *  string fails the gate and skips the audit), waitFor (the selector that proves it opened) }.
 *
 *  The profile-name dialog (src/lib/profile-name-dialog.js) is built in JavaScript and exists only once
 *  something opens it, so neither the page sweep nor postbuild-check (static HTML) can see it. Its CSS
 *  is written twice — global.css for the studio pages, faces.css for the face — so it is opened on one
 *  page of each. The two entries want opposite states: /profile/'s
 *  Duplicate control is hidden until a profile is saved, while /fortknight/achievements/ opens the
 *  first-achievement prompt at boot only when achievements exist and no profile is saved.
 *
 *  The face nav's Peripheral strip (src/components/FaceNav.astro) is a closed <details>, and axe prunes
 *  a closed details' contents, so its links are audited only here, open — in every state the bar can
 *  take: the sample keep's four focus pills with three stones behind Peripheral, no keep with all
 *  seven behind it, the same four-and-three inside the ☰ on a phone (the nested column has its own
 *  rules in faces.css), and a keep focusing on every stone, where the pill is hidden and seven are
 *  promoted. Each entry first asserts the partition it expects, so promotion — which the script does
 *  at boot and no other gate can observe — fails the build with the counts it saw. */
/** Opens the editor pages' Help: static markup, but display: none until showModal(), so the page
 *  sweep sees none of its prose. Both editor surfaces render one, and their contents differ. */
const openHelpDialog = () => {
  const button = document.getElementById("help-button");
  if (!button) return "no #help-button on the page — the a11y pass over Help did not run";
  button.click();
  return true;
};

export const OPENED_ELEMENT_ROUTES = [
  {
    route: "/profile/",
    seed: { "fortknight.user-settings": JSON.stringify(SEEDED_PROFILE) },
    label: "dialog",
    waitFor: "dialog.name-dialog[open]",
    open: () => {
      // The Duplicate control is hidden until a profile is saved; the seed above saves one.
      const button = document.getElementById("duplicateProfileButton");
      if (!button || button.hidden) {
        return "could not open the profile-name dialog — the a11y pass over it did not run";
      }
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
    seed: { "beinsiculous.keep": sampleKeepSeed },
    label: "peripheral",
    waitFor: "details.nav-peripheral[open]",
    open: () => {
      const promoted = Array.from(document.querySelectorAll(".nav-links > a[data-category]"));
      const inside = Array.from(document.querySelectorAll(".nav-peripheral-panel a[data-category]"));
      const promotedKeys = promoted.map((link) => link.dataset.category);
      const expectedKeys = ["meals", "cleaning", "working", "health"];
      const orderMatches =
        promotedKeys.length === 4 &&
        promotedKeys.every((key, index) => key === expectedKeys[index]);
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
    seed: { "beinsiculous.keep": sampleKeepSeed },
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
    route: "/playground/",
    seed: {},
    label: "help dialog",
    waitFor: "dialog#playground-help[open]",
    open: openHelpDialog,
  },
  {
    // The prose-heavy dialog at the width the phone pass exists for.
    route: "/playground/",
    seed: {},
    label: "help dialog, phone",
    viewport: { width: 390, height: 844 },
    waitFor: "dialog#playground-help[open]",
    open: openHelpDialog,
  },
  {
    route: "/playground/pong/",
    seed: {},
    label: "help dialog",
    waitFor: "dialog#playground-help[open]",
    open: openHelpDialog,
  },
  {
    // axe prunes a closed <details>, so the dock's two panels are audited only open — at both
    // widths, because the dock lays out in two columns from 66rem and one below it.
    route: "/playground/",
    seed: {},
    label: "dock",
    waitFor: "details#dock[open]",
    open: () => {
      const dock = document.getElementById("dock");
      if (!(dock instanceof HTMLDetailsElement)) return "details#dock not found";
      dock.open = true;
      return true;
    },
  },
  {
    route: "/playground/",
    seed: {},
    label: "dock, phone",
    viewport: { width: 390, height: 844 },
    waitFor: "details#dock[open]",
    open: () => {
      const dock = document.getElementById("dock");
      if (!(dock instanceof HTMLDetailsElement)) return "details#dock not found";
      dock.open = true;
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
