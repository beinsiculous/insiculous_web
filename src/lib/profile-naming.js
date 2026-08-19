// When a save or an apply creates a profile, let the person name it (the name is the id). The profile is
// already written by the time this runs, so the dialog has no Cancel: there is nothing left to cancel.
// Escape keeps the generated name. Shared by both questionnaires, Build, Spoon Feed and Apply from assistant.
import { loadSettings, profileIds, renameProfile, saveSettings } from "./shared/user-settings.js";
import { askProfileName } from "./profile-name-dialog.js";

/** Name the profile just created; resolves to "" (kept), " Profile named X." — errors keep the dialog open. */
export async function promptProfileName(createdId) {
  const opening = loadSettings(); // presentational only: what Regenerate should avoid right now
  const chosen = await askProfileName({
    title: "Name your profile",
    name: createdId,
    takenIds: [...profileIds(opening), opening.activeWeightsId].filter((id) => id !== createdId),
    confirmLabel: "Save name",
    canCancel: false,
    // Runs on submit, after the await: re-read here so a dialog left open while another tab saved
    // cannot write a stale settings record back over it.
    commit(typed) {
      const settings = loadSettings();
      if (!typed.trim() || typed.trim() === createdId) return createdId; // keeping the name is not a rename
      renameProfile(settings, createdId, typed);
      saveSettings(settings);
      return settings.activeWeightsId;
    },
  });
  return !chosen || chosen === createdId ? "" : ` Profile named ${chosen}.`;
}
