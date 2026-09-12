/**
 * Node-only loader for game achievement manifests from the public directory.
 * Kept separate from games-catalog.js because achievements.js is bundled for
 * the browser and must never import node:fs.
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { parseGameCatalog } from "./games-catalog.js";

// Anchored on the working directory, not on this module's location: Astro bundles the module
// into dist/.prerender/chunks/ for the build, so import.meta.url points somewhere different at
// build time than in the dev server or the tests. The build, the dev server and the tests all run
// from the project root, which is also the directory public/ is defined relative to; the tests
// pass the directory explicitly anyway.
export const PUBLIC_DIRECTORY = path.resolve(process.cwd(), "public");

/**
 * Read and parse achievements manifests for all playable games.
 *
 * @param {Array} games - Results from getCollection('games')
 * @param {string} [publicDirectory=PUBLIC_DIRECTORY] - Base public directory for resolving manifests
 * @returns {Array<{slug: string, title: string, achievements: Array}>}
 */
export function readGameCatalogs(games, publicDirectory = PUBLIC_DIRECTORY) {
  const playableGames = games
    .filter((game) => Boolean(game.data.wasm))
    .sort((first, second) => first.data.order - second.data.order);

  return playableGames.map((game) => {
    const wasmDirectory = path.dirname(game.data.wasm).replace(/^\/+/, "");
    const manifestPath = path.join(publicDirectory, wasmDirectory, "achievements.json");

    if (!existsSync(manifestPath)) {
      throw new Error(
        `Missing achievements manifest for ${game.id} at ${manifestPath}. ` +
        `Fix: run the game with --achievements-manifest, or build_wasm.sh`
      );
    }

    const manifestText = readFileSync(manifestPath, "utf8");
    const achievements = parseGameCatalog(manifestText, game.id);

    return {
      slug: game.id,
      title: game.data.title,
      achievements,
    };
  });
}
