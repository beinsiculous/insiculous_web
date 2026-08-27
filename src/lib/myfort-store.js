// Where a My Fort seed lives in the browser, and the only place that name is written down.
//
// A My Fort seed is exported from the Focus Key app and loaded here by the person who owns it. It is a
// household's schedule, so it never leaves this device: no upload, no server, no copy in this repository.
//
// Its own key, deliberately separate from `fortknight.user-settings`. The two are different documents from
// different apps, and sharing a key would let one migrate into the other the first time either changed
// shape. /profile/ can delete it; the My Fort page reads and writes it.

/** The localStorage key. Namespaced to the site, like `beinsiculous.a11y`, because the seed belongs to the
 *  person rather than to either face. */
export const MYFORT_SEED_KEY = "beinsiculous.myfort-seed";

/** The stored seed, or null when there is none — and also null when what is stored cannot be parsed.
 *  A wall display reloads into this path, so a truncated value must show the load screen rather than throw. */
export function loadMyFortSeed() {
  try {
    const raw = localStorage.getItem(MYFORT_SEED_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Forget the stored seed. Safe to call when there is none. */
export function clearMyFortSeed() {
  try {
    localStorage.removeItem(MYFORT_SEED_KEY);
  } catch {
    // A browser refusing storage has nothing to forget.
  }
}

/** What /profile/ shows about the stored seed without rendering any of it: whether one is here, and when it
 *  was exported. Deliberately not the contents — the profile page is about the device, not the schedule. */
export function describeMyFortSeed() {
  const seed = loadMyFortSeed();
  if (!seed) return { present: false, exportedAt: null };
  return { present: true, exportedAt: typeof seed?.meta?.exportedAt === "string" ? seed.meta.exportedAt : null };
}
