// On-device user settings: localStorage persistence, import/export, migration from older shapes.
// The questionnaire IS the settings: named weights profiles (the answers ride inside each at
// weights.questionnaire.answers), one of them active, plus device-only extras. Nothing secret lives here.
import { DAY_KEY_ORDER } from "./fortknight-rules.js";
import { DEFAULT_WEIGHTS_ID, activeWeights, slugifyId } from "./weights-rules.js";
import { randomProfileName } from "./profile-names.js";
import { classifyAssistantDocument } from "./workspace-docs.js";

const STORAGE_KEY = "fortknight.user-settings";
/** The pre-migration record of each schema step, kept (minus the old AI-provider block and its key) so a bad
 *  migration can be recovered: fortknight.user-settings.v1-backup, .v2-backup, … — one key per version, never reused. */
const backupStorageKey = (schemaVersion) => `${STORAGE_KEY}.v${Number.isInteger(schemaVersion) ? schemaVersion : 1}-backup`;
/** Where this device's generated default profile name lives — its own key, so a first visit costs one
 *  small write instead of a whole settings record nobody asked to save yet. */
const DEVICE_NAME_KEY = "fortknight.default-profile-id";
export const SETTINGS_SCHEMA_VERSION = 3;
/** The default profile id (kept under its old name for the pages that import it). */
export const USER_WEIGHTS_ID = DEFAULT_WEIGHTS_ID;

export function defaultSettings() {
  return {
    schemaVersion: SETTINGS_SCHEMA_VERSION,
    theme: "fort-knight", // ignored: the page's face picks its skin. Field kept so old exports still import cleanly
    epochOverride: null,
    timezone: null,
    activeSeasonId: null,
    weightsProfiles: {}, // weights id -> weights file (weights.schema.json); a profile appears once it is saved
    activeWeightsId: DEFAULT_WEIGHTS_ID,
    hidden: [],
    overrides: {},
    added: [],
    dayNotes: {},
  };
}

/** Bring any stored/exported settings object up to the current shape (pure).
 *  v1 → v3: `weightsProfiles` + `activeWeightsId` are kept as they are (the AI-provider block, including
 *  any API key, is dropped); v2 → v3: the single `weights` becomes the one profile under its id (the
 *  DEFAULT_WEIGHTS_ID fallback when unnamed; loadSettings swaps that for the device's generated name
 *  when no profile is saved) and is made active. Every profile's `id` is normalised to its key; unknown keys are dropped.
 *  `recoveredProfiles` (optional, id -> weights) are added when their id is free — how loadSettings() hands
 *  back the profiles the v1 → v2 step parked in the backup. */
export function migrateSettings(parsed, recoveredProfiles = null) {
  const defaults = defaultSettings();
  const source = { ...parsed };
  const migrated = {};
  for (const key of Object.keys(defaults)) migrated[key] = key in source ? source[key] : defaults[key];
  migrated.schemaVersion = SETTINGS_SCHEMA_VERSION;
  migrated.epochOverride = validEpochOverride(migrated.epochOverride);
  const profiles = {};
  const storedProfiles = source.weightsProfiles && typeof source.weightsProfiles === "object" ? source.weightsProfiles : {};
  // Profile keys are weights ids: kebab-case (a file an assistant named "My Profile" lands as my-profile);
  // two stored keys that slugify alike keep both profiles (the second becomes my-profile-2, and so on).
  const renamed = {}; // stored key -> final id, so the active id follows its profile
  for (const [key, weights] of Object.entries(storedProfiles)) {
    if (!weights || typeof weights !== "object") continue;
    const id = freeProfileId(profiles, profileIdFrom(key));
    profiles[id] = { ...weights, id };
    renamed[key] = id;
  }
  if (source.weights && typeof source.weights === "object") { // v2's single profile
    const id = profileIdFrom(source.weights.id);
    profiles[id] = { ...source.weights, id };
    migrated.activeWeightsId = id;
  }
  for (const [key, weights] of Object.entries(recoveredProfiles || {})) {
    const id = profileIdFrom(key);
    if (!(id in profiles) && weights && typeof weights === "object") profiles[id] = { ...weights, id };
  }
  if (typeof migrated.activeWeightsId === "string") migrated.activeWeightsId = renamed[migrated.activeWeightsId] || profileIdFrom(migrated.activeWeightsId);
  migrated.weightsProfiles = profiles;
  const ids = Object.keys(profiles);
  // An active id that names no saved profile is legitimate: a profile started (nav dropdown "New…") and not saved
  // yet must survive the page load that follows; only a missing/invalid id falls back to the first saved profile.
  if (typeof migrated.activeWeightsId !== "string" || !migrated.activeWeightsId) migrated.activeWeightsId = ids[0] || DEFAULT_WEIGHTS_ID;
  return migrated;
}

/** A profile id from any id-ish value: kebab-case via slugifyId, the default id when empty. */
export function profileIdFrom(value) {
  const id = typeof value === "string" ? slugifyId(value) : "";
  return id || DEFAULT_WEIGHTS_ID;
}

/** `wanted` when no profile has it yet, else wanted-2, wanted-3, … */
function freeProfileId(profiles, wanted) {
  if (!(wanted in profiles)) return wanted;
  let counter = 2;
  while (`${wanted}-${counter}` in profiles) counter += 1;
  return `${wanted}-${counter}`;
}

/** Merge the profiles of an imported settings file into a device's: profiles in the file are added or updated,
 *  the device's others are kept, the file's device extras win; the active profile is the file's when it carries
 *  one, else the device's. Pure — returns a new settings object. */
export function mergeImportedSettings(current, imported) {
  const weightsProfiles = { ...(current.weightsProfiles || {}), ...(imported.weightsProfiles || {}) };
  const activeWeightsId = imported.weightsProfiles?.[imported.activeWeightsId] ? imported.activeWeightsId : current.activeWeightsId;
  return { ...imported, weightsProfiles, activeWeightsId };
}

/** {date, dayKey} with a real ISO date and a known day key, else null (a bad anchor must not break date resolution). */
function validEpochOverride(epochOverride) {
  if (!epochOverride || typeof epochOverride.date !== "string" || !DAY_KEY_ORDER.includes(epochOverride.dayKey)) return null;
  const [year, month, day] = epochOverride.date.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  const isRealDate = /^\d{4}-\d{2}-\d{2}$/.test(epochOverride.date) && date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
  return isRealDate ? { date: epochOverride.date, dayKey: epochOverride.dayKey } : null;
}

/** The profiles a v1 → v2 migration parked in the v1 backup record (id -> weights), for the v2 → v3 step. */
function parkedProfiles() {
  try {
    const backup = JSON.parse(localStorage.getItem(backupStorageKey(1)) || "null");
    return backup?.weightsProfiles && typeof backup.weightsProfiles === "object" ? backup.weightsProfiles : null;
  } catch {
    return null;
  }
}

let deviceProfileId = null; // resolved once per JS context, then reused

/** This device's generated default profile name (adjective-noun-title) — made once, then remembered.
 *  Memoised because loadSettings() runs several times per page view (the Profile page alone reads it
 *  three times) and every one of them must show the same name. Each localStorage call is guarded on
 *  its own: with storage blocked the name is stable for the page view but cannot outlive it, which is
 *  the best available behaviour rather than a placeholder everybody shares. */
export function deviceDefaultProfileId() {
  if (deviceProfileId) return deviceProfileId;
  try {
    const stored = localStorage.getItem(DEVICE_NAME_KEY);
    if (stored) return (deviceProfileId = stored);
  } catch (error) {
    console.warn("device profile name unreadable, generating one", error);
  }
  deviceProfileId = randomProfileName();
  try {
    localStorage.setItem(DEVICE_NAME_KEY, deviceProfileId);
  } catch (error) {
    console.warn("device profile name not stored, it lasts this page view only", error);
  }
  return deviceProfileId;
}

/** A device with nothing saved shows its generated name rather than the bare fallback id. Applied on the
 *  way out of loadSettings so the pure functions above stay pure: a fresh device, a v2 record whose
 *  `weights` was null, and the reload after the last profile is deleted all land here. */
function withDeviceDefaultName(settings) {
  const noneSaved = Object.keys(settings.weightsProfiles || {}).length === 0;
  if (noneSaved && settings.activeWeightsId === DEFAULT_WEIGHTS_ID) settings.activeWeightsId = deviceDefaultProfileId();
  return settings;
}

export function loadSettings() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return withDeviceDefaultName(defaultSettings());
    const parsed = JSON.parse(stored);
    const isOlder = !Number.isInteger(parsed.schemaVersion) || parsed.schemaVersion < SETTINGS_SCHEMA_VERSION;
    // v2 → v3 recovers the profiles the earlier collapse parked in the backup (lossless; the person can delete them).
    const settings = migrateSettings(parsed, isOlder && parsed.schemaVersion === 2 ? parkedProfiles() : null);
    // Older records are migrated in place (the pre-migration copy is kept, minus the AI key);
    // newer ones are only read through — never downgraded on disk.
    if (isOlder) {
      const { aiProvider, ...backup } = parsed; // never keep the old API key around
      localStorage.setItem(backupStorageKey(parsed.schemaVersion), JSON.stringify(backup)); // its own key: the v1 backup stays intact
      saveSettings(settings); // purge old fields (and the key) from the live record right away
    }
    return withDeviceDefaultName(settings);
  } catch (error) {
    console.warn("settings unreadable, using defaults", error);
    return withDeviceDefaultName(defaultSettings());
  }
}

export function saveSettings(settings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

// ----- profiles (pure operations on a settings object; callers save) -----

/** Saved profile ids in stored order; the active one is `settings.activeWeightsId` (which may not be saved yet). */
export function profileIds(settings) {
  return Object.keys(settings.weightsProfiles || {});
}

/** Store `weights` under its id and make it the active profile. Returns `settings`. */
export function setActiveWeights(settings, weights) {
  const id = profileIdFrom(typeof weights?.id === "string" && weights.id ? weights.id : settings.activeWeightsId);
  settings.weightsProfiles = { ...(settings.weightsProfiles || {}), [id]: { ...weights, id } };
  settings.activeWeightsId = id;
  return settings;
}

/** A profile id from what the person typed: kebab-case, non-empty, unused. Throws with a readable message. */
export function newProfileId(settings, typedName) {
  const id = slugifyId(typedName || "");
  if (!id || !String(typedName || "").trim()) throw new Error("A profile needs a name.");
  if (profileIds(settings).includes(id) || id === settings.activeWeightsId) throw new Error(`There is already a profile called ${id}.`);
  return id;
}

/** Make `id` the active profile (it need not be saved yet — an unsaved profile shows typical defaults). */
export function switchProfile(settings, id) {
  settings.activeWeightsId = id;
  return settings;
}

/** A new, empty profile: active at once, saved once the person saves the questionnaire. */
export function createProfile(settings, typedName) {
  return switchProfile(settings, newProfileId(settings, typedName));
}

/** Copy the saved profile `fromId` under a new name and make the copy active. */
export function duplicateProfile(settings, fromId, typedName) {
  const source = settings.weightsProfiles?.[fromId];
  if (!source) throw new Error(`Profile ${fromId} has not been saved yet — save it before duplicating.`);
  const id = newProfileId(settings, typedName);
  return setActiveWeights(settings, { ...JSON.parse(JSON.stringify(source)), id });
}

/** Rename a profile: its id changes with the name (ids are the weights file names, weights.<id>.json), the
 *  answers and weights move under the new id, and the active id follows. An unsaved profile just changes id. */
export function renameProfile(settings, fromId, typedName) {
  const id = newProfileId(settings, typedName);
  const source = settings.weightsProfiles?.[fromId];
  if (source) {
    const { [fromId]: moved, ...others } = settings.weightsProfiles;
    settings.weightsProfiles = { ...others, [id]: { ...JSON.parse(JSON.stringify(moved)), id } };
  }
  if (settings.activeWeightsId === fromId) settings.activeWeightsId = id;
  return settings;
}

/** Forget a profile (any of them, the last one included). Deleting the active one activates the first other;
 *  with none left the device is back to a blank, unsaved default profile. */
export function deleteProfile(settings, id) {
  const remaining = profileIds(settings).filter((other) => other !== id);
  const { [id]: dropped, ...profiles } = settings.weightsProfiles || {};
  settings.weightsProfiles = profiles;
  if (settings.activeWeightsId === id) settings.activeWeightsId = remaining[0] || DEFAULT_WEIGHTS_ID;
  return settings;
}

export { activeWeights };

export function exportSettings(settings) {
  return JSON.stringify(settings, null, 2) + "\n";
}

/** Parse a settings file (any schema version) into the current shape; throws when it is not one. */
export function importSettings(jsonText) {
  const parsed = JSON.parse(jsonText);
  if (classifyAssistantDocument(parsed) !== "user-settings") throw new Error("Not a FortKnight user-settings file.");
  return migrateSettings(parsed);
}
