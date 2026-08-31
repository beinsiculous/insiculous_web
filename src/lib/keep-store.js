// Where a keep lives in the browser, and the only place that name is written down.
//
// A keep is exported from the Fort Knight app and loaded here by the person who owns it. It is a
// household's schedule, so it never leaves this device: no upload, no server, no copy in this repository.
//
// Its own key, deliberately separate from `fortknight.user-settings`. The two are different documents from
// different apps, and sharing a key would let one migrate into the other the first time either changed
// shape. /profile/ can delete it; the Keep page reads and writes it.

/** The localStorage key. Namespaced to the site, like `beinsiculous.a11y`, because the keep belongs to the
 *  person rather than to either face. */
export const KEEP_STORE_KEY = "beinsiculous.keep";

/** The key this store used while the keep was called the My Fort keep. Removed on sight rather than
 *  migrated: the format string changed with the name (2026-08-28), so anything under the old key can no
 *  longer validate, and carrying it forward would only make /profile/ describe a file no page can read. */
const LEGACY_STORE_KEY = "beinsiculous.myfort-seed";

function dropLegacyKey() {
  try {
    localStorage.removeItem(LEGACY_STORE_KEY);
  } catch {
    // A browser refusing storage has no legacy value either.
  }
}

/** The stored keep, or null when there is none — and also null when what is stored cannot be parsed.
 *  A wall display reloads into this path, so a truncated value must show the load screen rather than throw. */
export function loadKeep() {
  dropLegacyKey();
  try {
    const raw = localStorage.getItem(KEEP_STORE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Forget the stored keep. Safe to call when there is none. */
export function clearKeep() {
  try {
    localStorage.removeItem(KEEP_STORE_KEY);
  } catch {
    // A browser refusing storage has nothing to forget.
  }
}

/** What /profile/ shows about the stored keep without rendering any of it: whether one is here, and when it
 *  was exported. Deliberately not the contents — the profile page is about the device, not the schedule. */
export function describeKeep() {
  const keep = loadKeep();
  if (!keep) return { present: false, exportedAt: null };
  return { present: true, exportedAt: typeof keep?.meta?.exportedAt === "string" ? keep.meta.exportedAt : null };
}
