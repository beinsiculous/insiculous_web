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

const failures = [];
let analyzed = 0;
const browser = await chromium.launch();
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  // The faces only render their full UI once a profile exists locally — same seeding the
  // screenshot harness uses, so axe sees what a returning user sees.
  await page.addInitScript(() => {
    localStorage.setItem("fortknight.user-settings", JSON.stringify({ schemaVersion: 2 }));
  });
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
