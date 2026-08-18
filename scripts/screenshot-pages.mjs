// Dev utility: screenshot every surface of the site so the three identities can be compared, and fail loudly on
// any page that scrolls sideways.
//
// The studio pages wear BaseLayout's dark mono look (the Profile page among them); FortKnight and ForkKnife each
// bring their own skin from app/shared/themes.css (the page's face picks it — see src/lib/faces.js).
//
// Every page is shot at both widths, and BOTH passes measure the document's horizontal overflow: a viewport that
// scrolls sideways is a layout bug at any size, not a preference, so a non-zero reading is reported per page and
// makes the run exit non-zero. The phone is where it actually bites, but a desktop reading is a bug too and this
// will fail on it. Keep both at zero.
//
// Usage:
//   npm run build && npm run preview (in another shell), then
//   PLAYWRIGHT_BROWSERS_PATH=<browsers> node scripts/screenshot-pages.mjs
//   ONLY=mobile node scripts/screenshot-pages.mjs      (one viewport)
//   FULL_PAGE=1 node scripts/screenshot-pages.mjs      (whole scroll height, not just the fold)
// Output: shots/<name>.png and shots/<name>-mobile.png (gitignored).
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const baseUrl = process.env.PREVIEW_URL || "http://localhost:4321";
const pages = {
  // the studio
  "studio-home": "",
  "studio-games": "games/",
  "studio-game": "games/pong/",
  "studio-devlog": "devlog/",
  "studio-engine": "engine/",
  profile: "profile/",
  // FortKnight
  "fortknight-overview": "fortknight/",
  "fortknight-day": "fortknight/days/wed-b/",
  "fortknight-build": "fortknight/build/",
  "fortknight-questionnaire": "fortknight/questionnaire/",
  "fortknight-assistant": "fortknight/assistant/",
  // ForkKnife
  "forkknife-overview": "forkknife/",
  "forkknife-spoon-feed": "forkknife/spoon-feed/",
  "forkknife-questionnaire": "forkknife/questionnaire/",
  "forkknife-assistant": "forkknife/assistant/",
};

// "" is the desktop suffix so the existing shot names keep working; -mobile is the phone.
// The phone pass emulates touch, so `@media (pointer: coarse)` — where the 44px tap targets and the bigger
// dual-range thumbs live — is actually exercised rather than silently skipped.
const viewports = {
  desktop: { suffix: "", context: { viewport: { width: 1440, height: 900 } } },
  mobile: { suffix: "-mobile", context: { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } },
};
const only = process.env.ONLY;
const chosen = only ? { [only]: viewports[only] } : viewports;
if (only && !viewports[only]) {
  console.error(`ONLY must be one of: ${Object.keys(viewports).join(", ")}`);
  process.exit(1);
}

mkdirSync("shots", { recursive: true });
const browser = await chromium.launch();
const overflowing = [];
for (const [label, { suffix, context: contextOptions }] of Object.entries(chosen)) {
  const context = await browser.newContext(contextOptions);
  await context.addInitScript(() => {
    localStorage.setItem("fortknight.user-settings", JSON.stringify({ schemaVersion: 2 }));
  });
  const page = await context.newPage();
  for (const [name, path] of Object.entries(pages)) {
    await page.goto(`${baseUrl}/${path}`, { waitUntil: "networkidle" });
    await page.screenshot({ path: `shots/${name}${suffix}.png`, fullPage: Boolean(process.env.FULL_PAGE) });
    // scrollWidth beyond clientWidth is content the viewport cannot reach without scrolling sideways.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    if (overflow > 0) {
      overflowing.push(`${label}/${name}: ${overflow}px`);
      console.error(`shot ${name}${suffix} — OVERFLOW ${overflow}px`);
    } else {
      console.log(`shot ${name}${suffix}`);
    }
  }
  await context.close();
}
await browser.close();

if (overflowing.length) {
  console.error(`\n${overflowing.length} page(s) scroll sideways:\n  ${overflowing.join("\n  ")}`);
  process.exit(1);
}
console.log("\nNo page scrolls sideways.");
