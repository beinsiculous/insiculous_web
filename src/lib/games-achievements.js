// Achievements the games' browser builds record, one localStorage key per game:
// `beinsiculous.games.<slug>.achievements`. Its own key per game, deliberately separate from
// `fortknight.user-settings` and the keep — different documents from different apps, and
// sharing a key would let one migrate into the other the first time either changed shape
// (keep-store.js makes the argument). The value is the engine's native achievement save file,
// byte for byte: {"unlocks": {"<achievement id>": {"unlocked_at": <unix seconds>}}} — the
// `engine_core` achievements module's on-disk JSON — so a wasm build persists exactly what it
// already writes on desktop. The games write these keys; this module reads them for the
// /profile/ board and deletes them on request. Reserved beside them, not yet written:
// `beinsiculous.games.<slug>.scores` for high scores.
//
// The save file carries ids only — display names and descriptions live in each game, so the board
// prettifies the id. Schema agreed with the engine repository (beinsiculous/insiculous_2d#17).

/**
 * The games this site serves, in listing order: slug (the `public/games/<slug>` directory) and
 * display title. Kept by hand rather than derived from `src/content/games/` — this module runs in
 * the browser where the content collection does not exist, and slugs are immutable once published,
 * so the list only grows. Adding a game to the site means adding its row here too.
 */
export const GAMES = [
  { slug: "pong", title: "Insiculous Pong" },
  { slug: "breakout", title: "Insiculous Breakout" },
  { slug: "invaders", title: "Insiculous Invaders" },
  { slug: "snake", title: "Insiculous Snake" },
  { slug: "asteroids", title: "Insiculous Asteroids" },
  { slug: "frogger", title: "Insiculous Frogger" },
];

// Unix seconds for 9999-12-31 — the sanity ceiling on unlock dates. The likeliest writer bug, a
// milliseconds value where seconds belong, still fits inside ECMAScript's Date-valid range (it
// renders as year ~57000, not "Invalid Date"), so validity alone is not the guard: anything past
// year 9999 is treated as undated instead.
const MAX_UNIX_SECONDS = 253_402_300_800;

function storageKey(slug) {
  return `beinsiculous.games.${slug}.achievements`;
}

/** "beat_cpu_easy" → "Beat Cpu Easy" — the honest rendering of an id-only save file. */
export function achievementTitleFromId(achievementId) {
  return achievementId
    .split(/[_-]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * One parsed save file → [{id, unlockedAt: Date|null}], dated unlocks first (oldest first),
 * undated ones last. Pure, and deliberately strict about shape: `unlocks` must be a plain object,
 * and an `unlocked_at` that is not a positive integer inside the Date-valid range counts as
 * undated rather than rendering as "Invalid Date" or a 1970 unlock. Anything else malformed
 * yields [] — the board renders from whatever is readable.
 */
export function unlocksFromSaveFile(saveFile) {
  const records = saveFile && typeof saveFile === "object" && !Array.isArray(saveFile) ? saveFile.unlocks : null;
  if (!records || typeof records !== "object" || Array.isArray(records)) return [];
  return Object.entries(records)
    .map(([id, record]) => {
      const seconds = record && typeof record === "object" && !Array.isArray(record) ? record.unlocked_at : null;
      const dated = Number.isInteger(seconds) && seconds > 0 && seconds <= MAX_UNIX_SECONDS;
      return { id, unlockedAt: dated ? new Date(seconds * 1000) : null };
    })
    .sort((first, second) => {
      if (!first.unlockedAt) return second.unlockedAt ? 1 : 0;
      if (!second.unlockedAt) return -1;
      return first.unlockedAt.getTime() - second.unlockedAt.getTime();
    });
}

/**
 * What this browser has recorded: [{slug, title, unlocks}] for every game with at least one
 * readable unlock. A missing key, blocked storage, or malformed JSON contributes nothing.
 */
export function loadGameAchievements() {
  const boards = [];
  for (const { slug, title } of GAMES) {
    let parsed;
    try {
      const raw = localStorage.getItem(storageKey(slug));
      if (!raw) continue;
      parsed = JSON.parse(raw);
    } catch {
      continue;
    }
    const unlocks = unlocksFromSaveFile(parsed);
    if (unlocks.length) boards.push({ slug, title, unlocks });
  }
  return boards;
}

/** Remove every game's recorded achievements from this device. */
export function clearGameAchievements() {
  for (const { slug } of GAMES) {
    try {
      localStorage.removeItem(storageKey(slug));
    } catch {
      // storage blocked — nothing readable to remove either
    }
  }
}
