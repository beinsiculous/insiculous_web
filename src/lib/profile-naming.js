// When a save or an apply creates a profile, let the person name it (the name is the id; Cancel or the same
// name keeps it). Shared by the Assistant and ForkKnife pages (the questionnaire's Save has its own status flow).
import { loadSettings, renameProfile, saveSettings } from "./shared/user-settings.js";
import { slugifyId } from "./shared/weights-rules.js";

/** Prompt for the new profile's name; returns "" (kept), " Profile named X." or " Not renamed: …". */
export function promptProfileName(createdId) {
  const name = prompt("This created a profile. Name it:", createdId);
  if (!name || slugifyId(name) === createdId) return "";
  const settings = loadSettings();
  try {
    renameProfile(settings, createdId, name);
    saveSettings(settings);
    return ` Profile named ${settings.activeWeightsId}.`;
  } catch (error) {
    return ` Not renamed: ${error.message} — rename it on the Profile page.`;
  }
}
