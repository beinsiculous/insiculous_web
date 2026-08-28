// Reading the stored My Fort seed at page boot: what is in storage, made safe to act on.
//
// This module exists because a seed-fed page's boot sequence is the same everywhere — read the stored
// value, decide whether it can be drawn, and report honestly when it cannot — while the pages themselves
// differ. It was myfort.astro's inline boot until a second page needed the same path; the storage helpers
// stay in myfort-store.js and the validation stays in myfort.js, so this module's one job is the decision
// between them.
//
// Boot goes through the SAME validator as a picked file. Reloading the display is the ordinary path, so
// it must not be the one nothing checks: a truncated value in storage would otherwise throw at boot, on a
// screen with no developer tools attached.
//
// The raw value is read rather than loadMyFortSeed()'s parsed one, because the two READ failures need a
// different ending from a VALIDATION refusal. Storage that will not parse is not "no seed":
// loadMyFortSeed reports null for it, which would leave the wreckage in storage, invisible to the page
// AND to /profile/ — whose delete button hides when it believes there is nothing stored. So unreadable
// storage is cleared here, and the display comes back on the next reload instead of failing quietly
// forever.
//
// A seed that reads fine but fails validation is the opposite case, and is KEPT. A refusal means the
// document is intact but not drawable — wrong file, newer format, no days — and none of those is
// wreckage. The sharpest case is a newer Focus Key export: the remedy is a website deploy, which the
// person holding the phone cannot do, and a seed forgotten at boot would be gone by the time the update
// shipped. Keeping costs nothing: the seed stays deletable, from My Fort's Forget button or /profile/.
import { validateMyFortSeed } from "./myfort.js";
import { MYFORT_SEED_KEY, clearMyFortSeed } from "./myfort-store.js";

/** The stored seed, adjudicated. One of:
 *    { status: "seed", seed }  — validated by the same validateMyFortSeed a picked file goes through;
 *    { status: "none" }        — nothing stored, or a browser that refuses storage (which has nothing to show);
 *    { status: "cleared", reason }  — storage could not be READ (unparseable, or a literal null), so the
 *                                     wreckage was forgotten and `reason` says so;
 *    { status: "kept", reason }     — read fine, but the validator refuses to draw it; the seed is NOT
 *                                     deleted (the header says why keeping matters), and `reason` says
 *                                     why it cannot be drawn AND that nothing was deleted, because the
 *                                     person cannot see storage to check. */
export function readStoredMyFortSeed() {
  let storedText = null;
  try {
    storedText = localStorage.getItem(MYFORT_SEED_KEY);
  } catch (error) {
    storedText = null; // a browser refusing storage has nothing to show
  }
  if (storedText === null) return { status: "none" };

  let parsed;
  let readable = true;
  try {
    parsed = JSON.parse(storedText);
  } catch (error) {
    readable = false;
  }
  // A stored literal `null` parses perfectly and is not a seed. Treated as unreadable rather than as
  // "nothing stored", because "nothing stored" is the one answer that leaves it there for good: the page
  // would ignore it and /profile/ hides its delete button when it believes there is nothing to delete.
  if (!readable || parsed === null || parsed === undefined) {
    clearMyFortSeed();
    return { status: "cleared", reason: "The stored seed could not be read, so it has been forgotten. Load it again." };
  }

  const check = validateMyFortSeed(parsed);
  if (!check.ok) {
    return { status: "kept", reason: `${check.reason} It has been kept, not forgotten — nothing was deleted.` };
  }
  return { status: "seed", seed: check.seed };
}
