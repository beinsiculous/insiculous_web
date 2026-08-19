// The one place a profile gets named: an in-page dialog with a Regenerate button, used by every save
// and every create. It replaces the native prompt(), which could carry neither a Regenerate button nor
// an honest set of buttons — after a save the profile is already written, so a "Cancel" there cancelled
// nothing. This is the repo's only <dialog>; showModal() brings the focus trap, Escape and focus restore,
// so there is no focus management to get wrong (the rule AccessibilityControls.astro:8-9 states).
//
// Styles live in BOTH src/styles/app-widgets.css (the studio's /profile/) and src/styles/faces.css (the
// face pages) under the same class names — those two files are deliberately not shared.
import { unusedProfileName } from "./shared/profile-names.js";

let dialog = null; // built once, on first use
let pending = null; // the in-flight ask, so a double-click cannot call showModal() on an open dialog

/** Build the dialog once and hand back its parts. Ids are its own; nothing on any page uses them. */
function buildDialog() {
  const element = document.createElement("dialog");
  element.className = "name-dialog";
  element.setAttribute("aria-labelledby", "nameDialogTitle");
  // A heading, not an <h1>: postbuild-check allows exactly one <h1> per page and the page owns it.
  element.innerHTML = `
    <form class="name-dialog-form" method="post">
      <h2 id="nameDialogTitle"></h2>
      <label class="inline-field">Name <input type="text" id="nameDialogInput" autocomplete="off" required /></label>
      <p class="muted name-dialog-error" id="nameDialogError" role="status" aria-live="polite"></p>
      <div class="button-row">
        <button type="button" class="name-dialog-cancel">Cancel</button>
        <button type="button" class="name-dialog-regenerate">Regenerate</button>
        <button type="submit" class="name-dialog-confirm"></button>
      </div>
    </form>`;
  document.body.appendChild(element);
  return element;
}

/** Ask for a profile name, and commit it from inside the dialog. Resolves to the chosen name, or null
 *  when the person dismissed it with Escape (there is no backdrop dismissal: a native <dialog> does not
 *  close on backdrop click, and adding it would throw away a typed name on a stray drag-select).
 *
 *  `commit(name)` does the read-modify-write and may throw — its message is shown and the dialog stays
 *  open so the name can be fixed or rerolled. It MUST call loadSettings() itself, here inside the submit
 *  handler: the dialog can sit open for minutes, so anything read before it opened may be stale and must
 *  never be written back (another tab may have saved meanwhile).
 *
 *  `takenIds` is what Regenerate avoids — every id the commit would reject, the active one included.
 *  `canCancel` false = the thing being named already exists, so there is nothing to cancel. */
export function askProfileName({ title, name, takenIds = [], confirmLabel = "Save name", canCancel = false, commit }) {
  if (pending) return pending; // a second ask while one is open joins it rather than throwing InvalidStateError
  dialog = dialog || buildDialog();
  const form = dialog.querySelector("form");
  const input = dialog.querySelector("#nameDialogInput");
  const error = dialog.querySelector("#nameDialogError");
  const cancelButton = dialog.querySelector(".name-dialog-cancel");
  const regenerateButton = dialog.querySelector(".name-dialog-regenerate");
  const confirmButton = dialog.querySelector(".name-dialog-confirm");

  dialog.querySelector("#nameDialogTitle").textContent = title;
  confirmButton.textContent = confirmLabel;
  cancelButton.hidden = !canCancel;
  input.value = name || "";
  error.textContent = "";

  pending = new Promise((resolve) => {
    let chosen = null; // set by a commit that went through; anything else is a dismissal

    const onSubmit = (event) => {
      event.preventDefault();
      error.textContent = "";
      try {
        chosen = commit(input.value) ?? input.value.trim();
      } catch (problem) {
        error.textContent = problem.message; // stay open: without a Cancel button, closing here is a dead end
        input.focus();
        return;
      }
      dialog.close();
    };
    const onCancel = () => dialog.close();
    const onRegenerate = () => {
      input.value = unusedProfileName(takenIds);
      error.textContent = "";
      input.focus();
    };
    const onClose = () => {
      form.removeEventListener("submit", onSubmit);
      cancelButton.removeEventListener("click", onCancel);
      regenerateButton.removeEventListener("click", onRegenerate);
      dialog.removeEventListener("close", onClose);
      pending = null;
      resolve(chosen);
    };

    form.addEventListener("submit", onSubmit);
    cancelButton.addEventListener("click", onCancel);
    regenerateButton.addEventListener("click", onRegenerate);
    dialog.addEventListener("close", onClose);
    dialog.showModal();
    input.focus();
    input.select();
  });
  return pending;
}
