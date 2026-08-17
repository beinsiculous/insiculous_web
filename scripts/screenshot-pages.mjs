// Dev utility: screenshot every surface of the site so the three identities can be compared.
// The studio pages wear BaseLayout's dark mono look; FortKnight and ForkKnife each bring their own
// skin from app/shared/themes.css (the page's face picks it — see src/lib/faces.js).
//
// Usage:
//   npm run build && npm run preview (in another shell), then
//   PLAYWRIGHT_BROWSERS_PATH=<browsers> node scripts/screenshot-pages.mjs
// Output: shots/<name>.png (gitignored).
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const baseUrl = process.env.PREVIEW_URL || "http://localhost:4321";
const pages = {
  // the studio
  "studio-home": "",
  "studio-games": "games/",
  "studio-devlog": "devlog/",
  // FortKnight
  "fortknight-overview": "fortknight/",
  "fortknight-day": "fortknight/days/wed-b/",
  "fortknight-questionnaire": "fortknight/questionnaire/",
  "fortknight-assistant": "fortknight/assistant/",
  // ForkKnife
  "forkknife-overview": "forkknife/",
  "forkknife-questionnaire": "forkknife/questionnaire/",
  "forkknife-assistant": "forkknife/assistant/",
  // shared
  profile: "profile/",
};

mkdirSync("shots", { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addInitScript(() => {
  localStorage.setItem("fortknight.user-settings", JSON.stringify({ schemaVersion: 2 }));
});
const page = await context.newPage();
for (const [name, path] of Object.entries(pages)) {
  await page.goto(`${baseUrl}/${path}`, { waitUntil: "networkidle" });
  await page.screenshot({ path: `shots/${name}.png` });
  console.log(`shot ${name}`);
}
await context.close();
await browser.close();
