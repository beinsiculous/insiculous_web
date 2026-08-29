// The one static server the browser gates share: serve a built dist/ the way wrangler's static
// assets do — /foo/ -> /foo/index.html, unknown paths -> 404.html (not_found_handling =
// "404-page") — on an ephemeral port, so the gates need no preview server and cannot collide.
// Consumers: scripts/a11y-check.mjs and scripts/screenshot-pages.mjs. The mapping lives only here.
import { createServer } from "node:http";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join } from "node:path";

function walk(dir, onFile) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) walk(path, onFile);
    else onFile(path);
  }
}

/** Every route the built site serves: each index.html, plus standalone pages like 404.html. */
export function distRoutes(dist) {
  const routes = [];
  walk(dist, (path) => {
    if (extname(path) !== ".html") return;
    const rel = path.slice(dist.length).replaceAll("\\", "/");
    routes.push(rel.endsWith("/index.html") ? rel.slice(0, -"index.html".length) : rel);
  });
  routes.sort();
  return routes;
}

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

/** Serve `dist` on an ephemeral port. Returns { server, port }; callers close server when done. */
export async function serveDist(dist) {
  const server = createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    let path = join(dist, decodeURIComponent(url.pathname));
    try {
      if (statSync(path).isDirectory()) path = join(path, "index.html");
      const body = readFileSync(path);
      res.writeHead(200, { "content-type": MIME[extname(path)] ?? "application/octet-stream" });
      res.end(body);
    } catch {
      res.writeHead(404, { "content-type": MIME[".html"] });
      res.end(readFileSync(join(dist, "404.html")));
    }
  });
  await new Promise((resolveListen) => server.listen(0, resolveListen));
  return { server, port: server.address().port };
}
