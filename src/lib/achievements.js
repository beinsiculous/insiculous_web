// The site-wide achievements core: one localStorage key, `beinsiculous.achievements`, for the
// achievements the SITE awards (playing the games is one way to earn, not the only one). Its own
// key, deliberately separate from the games' per-slug saves (`beinsiculous.games.<slug>.achievements`)
// and from `fortknight.user-settings` — different documents from different writers, and sharing a
// key would let one migrate into the other the first time either changed shape (games-achievements.js
// and keep-store.js make the argument). The value keeps the games' save shape,
// {"unlocks": {"<achievement id>": {"unlocked_at": <unix seconds>}}}, so one tolerant reader rule
// serves both stores: this module reuses games-achievements.js's unlocksFromSaveFile rather than
// re-deciding what counts as a date.
//
// Unlike the games' saves, this store's ids mean nothing without their display text, so the
// registry below carries title and description — the store stays id-only and byte-compatible.
//
// The first-achievement profile prompt rides beside the store under
// `beinsiculous.achievements.profile-prompt`: not part of the unlocks record because it is not an
// achievement, and not in user-settings because it must be askable before any settings exist.
import { achievementTitleFromId, loadGameAchievements, unlocksFromSaveFile } from "./games-achievements.js";
import { askProfileName } from "./profile-name-dialog.js";
import { unusedProfileName } from "./shared/profile-names.js";
import { createProfile, loadSettings, profileIds, saveSettings } from "./shared/user-settings.js";

const SITE_ACHIEVEMENTS_KEY = "beinsiculous.achievements";
const PROFILE_PROMPT_KEY = "beinsiculous.achievements.profile-prompt";

/** The achievement types a board can group by. "game" is not a site-store type — game groups come
 *  from the games' own saves — but it shares the board, so it shares the vocabulary. */
export const ACHIEVEMENT_TYPES = Object.freeze(["insiculous", "game", "fortknight"]);

/** Every site achievement, {id, type, title, description}. Ids are immutable once published
 *  (stored unlock records name them); type is one of ACHIEVEMENT_TYPES minus "game". */
export const ACHIEVEMENTS = Object.freeze([
  { id: "player", type: "insiculous", title: "Player", description: "Opened the games page." },
  { id: "moved-in", type: "fortknight", title: "Moved In", description: "Loaded a keep." },
]);

/** This browser's site unlock records, [{id, unlockedAt: Date|null}] — malformed storage reads as
 *  empty, never as an error (games-achievements.js's unlocksFromSaveFile sets the date rules). */
function readSiteUnlocks() {
  try {
    const raw = localStorage.getItem(SITE_ACHIEVEMENTS_KEY);
    if (!raw) return [];
    return unlocksFromSaveFile(JSON.parse(raw));
  } catch {
    return []; // blocked storage or malformed JSON — the board renders from whatever is readable
  }
}

/**
 * This browser's site achievements, enriched from the registry:
 * [{id, type, title, description, unlockedAt: Date|null}], dated oldest first, undated last.
 * An id the registry does not know still renders — prettified like the game reader does, with an
 * empty description and the "insiculous" type so the board has a group to put it in (the store is
 * the site's own; an unknown id there is a newer build's achievement, not a game's).
 */
export function loadSiteAchievements() {
  const registry = new Map(ACHIEVEMENTS.map((achievement) => [achievement.id, achievement]));
  return readSiteUnlocks().map(({ id, unlockedAt }) => {
    const known = registry.get(id);
    return known
      ? { id, type: known.type, title: known.title, description: known.description, unlockedAt }
      : { id, type: "insiculous", title: achievementTitleFromId(id), description: "", unlockedAt };
  });
}

/**
 * Record a site achievement. Registry ids only — a page cannot invent one by unlocking it.
 * Idempotent: returns true only when this call did the unlocking. Never throws; blocked storage
 * reads as "not newly unlocked", because an achievement is never worth an exception.
 */
export function unlockAchievement(achievementId) {
  if (!ACHIEVEMENTS.some((achievement) => achievement.id === achievementId)) return false;
  try {
    const raw = localStorage.getItem(SITE_ACHIEVEMENTS_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    const stored = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed.unlocks : null;
    // A malformed store reads as empty above, so replacing it with a clean record loses nothing.
    const unlocks = stored && typeof stored === "object" && !Array.isArray(stored) ? stored : {};
    if (unlocks[achievementId]) return false;
    unlocks[achievementId] = { unlocked_at: Math.floor(Date.now() / 1000) };
    localStorage.setItem(SITE_ACHIEVEMENTS_KEY, JSON.stringify({ unlocks }));
    return true;
  } catch {
    return false; // storage refused
  }
}

/** Remove this browser's recorded site achievements. The delete-all on /profile/ calls this beside
 *  clearGameAchievements(): the board shows both stores, so the button must clear both. */
export function clearSiteAchievements() {
  try {
    localStorage.removeItem(SITE_ACHIEVEMENTS_KEY);
  } catch {
    // storage blocked — nothing readable to remove either
  }
}

/** Every achievement this browser holds: the site store plus each game's save. The game list is
 *  not duplicated here — loadGameAchievements() already enumerates it. */
export function totalAchievementCount() {
  const gameCount = loadGameAchievements().reduce((total, board) => total + board.unlocks.length, 0);
  return readSiteUnlocks().length + gameCount;
}

/** Record that the first-achievement profile prompt was settled ("created" or "dismissed"), so it
 *  fires once ever either way. Best-effort: with storage blocked the prompt may reappear, which is
 *  the honest failure mode — the flag exists to spare people repeats, not to gate anything. */
function setPromptFlag(outcome) {
  try {
    localStorage.setItem(PROFILE_PROMPT_KEY, outcome);
  } catch {
    // storage refused — see above
  }
}

/**
 * The gating predicate for the first-achievement prompt, exported on its own because the dialog
 * itself needs a real document and cannot run under the node-driven tests: this is the part that
 * must be provably right. Prompt when this browser holds at least one achievement (any store,
 * games included — an achievement is an achievement), has no saved profile yet, and has never
 * settled the prompt. Never throws; an unreadable store reads as "do not prompt".
 */
export function shouldPromptForProfile() {
  try {
    if (localStorage.getItem(PROFILE_PROMPT_KEY)) return false;
    if (profileIds(loadSettings()).length > 0) return false;
    return totalAchievementCount() > 0;
  } catch {
    return false;
  }
}

/**
 * Offer to create a profile the first time this browser earns an achievement with none saved.
 * Fires once ever: committing sets the flag to "created", dismissing to "dismissed". Async and
 * never throws — a popup is a nicety, so any failure (storage blocked, dialog unavailable) just
 * means no prompt this time. Resolves true only when a profile was created.
 */
export async function maybePromptForProfile() {
  try {
    if (!shouldPromptForProfile()) return false;
    const current = loadSettings();
    const takenIds = [...profileIds(current), current.activeWeightsId];
    const chosen = await askProfileName({
      title: "You earned your first achievement",
      name: unusedProfileName(takenIds),
      takenIds,
      confirmLabel: "Create profile",
      canCancel: true,
      commit(typedName) {
        const settings = loadSettings(); // re-read here: the dialog may have been open a while
        createProfile(settings, typedName);
        saveSettings(settings);
        setPromptFlag("created");
        return settings.activeWeightsId;
      },
    });
    if (!chosen) setPromptFlag("dismissed");
    return Boolean(chosen);
  } catch {
    return false;
  }
}

/**
 * The shared achievements board: one h3 + ul per group with unlocks, appended to `container`
 * (which is emptied first). `types` — a subset of ACHIEVEMENT_TYPES — says which groups render:
 * "game" draws one group per game with unlocks (from the games' own saves, exactly as /profile/
 * always has), "insiculous" and "fortknight" one group each from the site store. Group order is
 * the ACHIEVEMENT_TYPES order regardless of the order `types` lists them, so every page's board
 * reads the same. All DOM is createElement + textContent — nothing here is ever innerHTML.
 * Returns whether anything rendered, so the caller can show its own empty-state copy instead.
 *
 * `includeLocked` (default false — the other pages show what was earned) turns on the registry
 * spine for the site types, as /achievements/ wants: every ACHIEVEMENTS entry renders, unlocked or
 * not, with its description — unlocked first (dated oldest first, undated last, the store's order),
 * then the locked entries, which carry the class `achievement-locked` and a plain-text "Locked"
 * marker (no padlock glyph: a marker everyone can read). Game groups cannot do this: the engine
 * owns each game's full achievement list, the save file carries unlocked ids only, and copying the
 * locked set into this registry would drift the first time a game added one — so with
 * `includeLocked` a game group just says, in a `p.achievement-note`, where its full list lives.
 */
export function renderAchievementsBoard(container, { types = [...ACHIEVEMENT_TYPES], includeLocked = false } = {}) {
  const wanted = new Set(types);
  container.textContent = "";
  let rendered = false;

  const renderGroup = (heading, rows, note = null) => {
    if (!rows.length) return;
    const headingElement = document.createElement("h3");
    const unlockedCount = rows.filter((row) => !row.locked).length;
    headingElement.textContent = `${heading} — ${unlockedCount} unlocked`;
    const list = document.createElement("ul");
    for (const row of rows) {
      const item = document.createElement("li");
      const parts = [row.title];
      if (row.description) parts.push(row.description);
      if (row.unlockedAt) parts.push(row.unlockedAt.toLocaleDateString());
      if (row.locked) {
        parts.push("Locked");
        item.className = "achievement-locked";
      }
      item.textContent = parts.join(" — ");
      list.append(item);
    }
    container.append(headingElement, list);
    if (note) {
      const noteElement = document.createElement("p");
      noteElement.className = "achievement-note";
      noteElement.textContent = note;
      container.append(noteElement);
    }
    rendered = true;
  };

  const wantsSite = wanted.has("insiculous") || wanted.has("fortknight");
  const siteUnlocks = wantsSite ? loadSiteAchievements() : [];
  for (const type of ACHIEVEMENT_TYPES) {
    if (!wanted.has(type)) continue;
    if (type === "game") {
      for (const board of loadGameAchievements()) {
        renderGroup(board.title,
          board.unlocks.map((unlock) => ({ title: achievementTitleFromId(unlock.id), unlockedAt: unlock.unlockedAt })),
          includeLocked ? "The full achievement list lives in the game — this board only sees what this browser has unlocked." : null);
      }
    } else {
      const heading = type === "fortknight" ? "FortKnight" : "Be Insiculous";
      const unlocked = siteUnlocks.filter((unlock) => unlock.type === type);
      if (includeLocked) {
        const unlockedIds = new Set(unlocked.map((unlock) => unlock.id));
        const rows = [
          ...unlocked.map((unlock) => ({ title: unlock.title, description: unlock.description, unlockedAt: unlock.unlockedAt })),
          ...ACHIEVEMENTS.filter((achievement) => achievement.type === type && !unlockedIds.has(achievement.id))
            .map((achievement) => ({ title: achievement.title, description: achievement.description, locked: true })),
        ];
        renderGroup(heading, rows);
      } else {
        renderGroup(heading, unlocked.map((unlock) => ({ title: unlock.title, unlockedAt: unlock.unlockedAt })));
      }
    }
  }
  return rendered;
}
