// The word tables a profile name is drawn from: [Adjective]-[Noun]-[Title], e.g. lucky-garden-poet.
// A device's first profile is named this way instead of carrying a placeholder, and /profile/'s
// Regenerate button rolls another. Every combination is already a valid weights id
// (^[a-z0-9]+(-[a-z0-9]+)*$, weights.schema.json), so a generated name never needs slugifying.
// Browser module with no build step; the naming is the app's own, so there is no fk_core twin.

export const ADJECTIVES = Object.freeze([
  "humorous", "courageous", "thoughtful", "alluring", "lucky", "festive", "familiar", "fantastic",
  "attractive", "energetic", "glamorous", "resolute", "amusing", "wise", "scientific", "acoustic",
  "fortunate", "bouncy", "determined", "awesome", "romantic", "elegant", "lyrical", "lively",
  "hypnotic", "cooperative", "beautiful", "sincere", "pleasant", "super",
]);

export const NOUNS = Object.freeze([
  "library", "kitchen", "earth", "forest", "market", "penthouse", "club", "garden", "campus",
  "cloud", "field", "studio", "at-home", "restaurant", "commute", "couch", "pool-side", "downtown",
  "farmhouse", "airport", "community", "intention", "computer", "memory", "office", "committee",
  "university", "obligation",
]);

export const TITLES = Object.freeze([
  "poet", "champion", "director", "inspector", "trainer", "buyer", "worker", "teacher", "editor",
  "passenger", "winner", "user", "manufacturer", "owner", "player", "member", "manager", "writer",
  "leader", "employer", "farmer", "secretary", "historian", "artisan", "assistant", "analyst",
  "professor", "customer", "driver", "employee",
]);

/** How many rolls before falling back to a suffix; a collision needs the same three words twice. */
const ROLL_ATTEMPTS = 20;

/** One entry of `table`; `random` returns 0 <= value < 1, so the index stays inside the table. */
function pick(table, random) {
  return table[Math.min(table.length - 1, Math.floor(random() * table.length))];
}

/** One name, adjective-noun-title. `random` is injectable so the tests can drive it deterministically. */
export function randomProfileName(random = Math.random) {
  return `${pick(ADJECTIVES, random)}-${pick(NOUNS, random)}-${pick(TITLES, random)}`;
}

/** A name none of `takenIds` holds. `takenIds` must be every id newProfileId would reject — the saved
 *  ids AND the active one, saved or not (user-settings.js) — or a roll can return the name already in
 *  force. Rolls a few times, then falls back to the -2, -3 suffix loop freeProfileId also uses, so the
 *  result is always a name newProfileId accepts. */
export function unusedProfileName(takenIds, random = Math.random) {
  const taken = new Set(takenIds || []);
  let name = randomProfileName(random);
  for (let attempt = 1; attempt < ROLL_ATTEMPTS && taken.has(name); attempt += 1) name = randomProfileName(random);
  if (!taken.has(name)) return name;
  let counter = 2;
  while (taken.has(`${name}-${counter}`)) counter += 1;
  return `${name}-${counter}`;
}
