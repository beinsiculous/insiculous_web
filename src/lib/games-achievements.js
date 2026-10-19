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
// A renamed game leaves its unlocks under its former slug's key. The engine owns that migration:
// the renamed game's bundle folds the former key into memory at boot, writes only the new key, and
// never writes the former one. This module only reads — the board shows the union of the two keys
// so progress is visible before the renamed game is ever opened, and writes nothing.
//
// The save file carries ids only; names and descriptions come from the manifest when a page
// passes one, and the board falls back to prettifying the id when no catalog is present.

/**
 * The games this site serves, in listing order: slug (the `public/games/<slug>` directory), the
 * slug it was published under before a rename (`formerSlug`, the entry's frontmatter field of the
 * same name) and display title. Kept by hand rather than derived from `src/content/games/` — this
 * module runs in the browser where the content collection does not exist. A slug may be retired to
 * `formerSlug` but is never dropped: the row keeps the former key readable, because a browser that
 * played under the old name still holds its unlocks there. Adding a game to the site means adding
 * its row here too.
 */
export const GAMES = [
  { slug: "tong", formerSlug: "pong", title: "Tong" },
  { slug: "food-pyramid", formerSlug: "breakout", title: "The Food Pyramid" },
  { slug: "toast-busters", formerSlug: "invaders", title: "Toast Busters" },
  { slug: "bratdog", formerSlug: "snake", title: "Bratdog" },
  { slug: "meatieroids", formerSlug: "asteroids", title: "Meatieroids" },
  { slug: "chicken-coop", formerSlug: "frogger", title: "Chicken Coop" },
];

// Unix seconds for 9999-12-31 — the sanity ceiling on unlock dates. The likeliest writer bug, a
// milliseconds value where seconds belong, still fits inside ECMAScript's Date-valid range (it
// renders as year ~57000, not "Invalid Date"), so validity alone is not the guard: anything past
// year 9999 is treated as undated instead.
const MAX_UNIX_SECONDS = 253_402_300_800;

function storageKey(slug) {
  return `beinsiculous.games.${slug}.achievements`;
}

/** Every storage key a game's unlocks may sit under: its own, then its former slug's. */
function storageKeysOf(slug) {
  const game = GAMES.find((candidate) => candidate.slug === slug);
  return game?.formerSlug ? [storageKey(slug), storageKey(game.formerSlug)] : [storageKey(slug)];
}

/** Dated unlocks first, oldest first; undated ones last. */
function byUnlockDate(first, second) {
  if (!first.unlockedAt) return second.unlockedAt ? 1 : 0;
  if (!second.unlockedAt) return -1;
  return first.unlockedAt.getTime() - second.unlockedAt.getTime();
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
    .sort(byUnlockDate);
}

/** One key's readable unlocks, or [] for a missing key, blocked storage, or malformed JSON. */
function unlocksUnderKey(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    return unlocksFromSaveFile(JSON.parse(raw));
  } catch {
    return [];
  }
}

/**
 * One game's readable unlocks: [{id, unlockedAt: Date|null}], sorted as `unlocksFromSaveFile`
 * sorts. For a game with a `formerSlug`, the union of its key and the former slug's key, each read
 * on its own so an unreadable half never hides the other. For an id in both, a dated unlock
 * supersedes an undated one, and of two dated ones the earlier wins, as the engine keeps the
 * earliest when it folds the former key in. Keyed on a Map so an id such as `__proto__` is kept as
 * the save file spells it. Takes the current slug only: a former slug has no row, so it reads its own key alone.
 */
export function loadGameUnlocks(slug) {
  const unlocksById = new Map();
  for (const key of storageKeysOf(slug)) {
    for (const unlock of unlocksUnderKey(key)) {
      const kept = unlocksById.get(unlock.id);
      const datedEarlier = unlock.unlockedAt
        && (!kept?.unlockedAt || unlock.unlockedAt.getTime() < kept.unlockedAt.getTime());
      if (!kept || datedEarlier) unlocksById.set(unlock.id, unlock);
    }
  }
  return [...unlocksById.values()].sort(byUnlockDate);
}

/**
 * What this browser has recorded: [{slug, title, unlocks}] for every game with at least one
 * readable unlock. A missing key, blocked storage, or malformed JSON contributes nothing.
 */
export function loadGameAchievements() {
  return GAMES.map(({ slug, title }) => ({ slug, title, unlocks: loadGameUnlocks(slug) }))
    .filter((board) => board.unlocks.length > 0);
}

/**
 * Remove every game's recorded achievements from this device — under its former slug's key too,
 * since the board shows the union of both and the button must clear what it shows.
 */
export function clearGameAchievements() {
  for (const { slug } of GAMES) {
    for (const key of storageKeysOf(slug)) {
      try {
        localStorage.removeItem(key);
      } catch {
        // storage blocked — nothing readable to remove either
      }
    }
  }
}
