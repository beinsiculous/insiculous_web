// The docs/schemas of the assistant workspace: synced into src/data/workspace/ by scripts/sync-assets.mjs and
// inlined at build time; the list of what belongs there is WORKSPACE_STATIC_DOCUMENTS (app/shared/workspace-docs.js).
import { WORKSPACE_STATIC_DOCUMENTS } from "./shared/workspace-docs.js";

const rawTexts = import.meta.glob("../data/workspace/*", { query: "?raw", import: "default", eager: true });

/** file name -> text ("" when the file did not sync). */
export const staticTexts = Object.fromEntries(Object.keys(WORKSPACE_STATIC_DOCUMENTS).map((fileName) => {
  const match = Object.entries(rawTexts).find(([path]) => path.endsWith(`/${fileName}`));
  return [fileName, match ? match[1] : ""];
}));

/** The names that did not sync (a warning for the person: run npm run dev/build again). */
export const missingStaticTexts = Object.keys(WORKSPACE_STATIC_DOCUMENTS).filter((fileName) => !staticTexts[fileName]);
