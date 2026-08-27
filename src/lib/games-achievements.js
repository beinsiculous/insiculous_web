// Achievements the games' browser builds record, one localStorage key per game:
// `beinsiculous.games.<slug>.achievements`. Its own key per game, deliberately separate from
// `fortknight.user-settings` and the My Fort seed — different documents from different apps, and
// sharing a key would let one migrate into the other the first time either changed shape
// (myfort-store.js makes the argument). The value is the engine's native achievement save file,
// byte for byte: {"unlocks": {"<achievement id>": {"unlocked_at": <unix seconds>}}} — the
// `engine_core` achievements module's on-disk JSON — so a wasm build persists exactly what it
// already writes on desktop. The games write these keys; this module reads them for the
// /profile/ board and deletes them on request. Reserved beside them, not yet written:
// `beinsiculous.games.<slug>.scores` for high scores.
//
// The save file carries ids only — display names and descriptions live in each game, so the board
// prettifies the id. Schema agreed with the engine repository (beinsiculous/insiculous_2d#17).

/** The games this site serves, in listing order: slug (the `public/games/<slug>` directory) and display title. */
export const GAMES = [
  { slug: "pong", title: "Insiculous Pong" },
  { slug: "breakout", title: "Insiculous Breakout" },
  { slug: "invaders", title: "Insiculous Invaders" },
  { slug: "snake", title: "Insiculous Snake" },
  { slug: "asteroids", title: "Insiculous Asteroids" },
  { slug: "frogger", title: "Insiculous Frogger" },
];

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
 * What this browser has recorded: [{slug, title, unlocks: [{id, unlockedAt: Date|null}]}] for
 * every game with at least one unlock, oldest unlock first. A missing key, blocked storage, or a
 * malformed record contributes nothing — the board renders from whatever is readable.
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
    const records = parsed && typeof parsed === "object" ? parsed.unlocks : null;
    if (!records || typeof records !== "object") continue;
    const unlocks = Object.entries(records)
      .map(([id, record]) => ({
        id,
        unlockedAt: Number.isFinite(record?.unlocked_at) ? new Date(record.unlocked_at * 1000) : null,
      }))
      .sort((first, second) => (first.unlockedAt?.getTime() ?? 0) - (second.unlockedAt?.getTime() ?? 0));
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
