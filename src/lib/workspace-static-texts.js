// The docs and schemas of the assistant workspace, inlined at build time so /profile/ and the two
// assistant pages can hand them to the person as files. These are the repository's own documents —
// imported straight from docs/ and data/schema/ at the paths WORKSPACE_STATIC_DOCUMENTS names, so a
// renamed or deleted source fails the build here instead of shipping an empty file.
import { WORKSPACE_STATIC_DOCUMENTS } from "./shared/workspace-docs.js";

import llmGuide from "../../docs/llm-guide.md?raw";
import domain from "../../docs/domain.md?raw";
import dataModel from "../../docs/data-model.md?raw";
import weights from "../../docs/weights.md?raw";
import questionnaire from "../../docs/questionnaire.md?raw";
import generator from "../../docs/generator.md?raw";
import importers from "../../docs/importers.md?raw";
import importFromSpreadsheet from "../../docs/import-from-spreadsheet.md?raw";
import mealPlan from "../../docs/meal-plan.md?raw";
import importSchema from "../../data/schema/import.schema.json?raw";
import mealPlanSchema from "../../data/schema/meal-plan.schema.json?raw";
import weightsSchema from "../../data/schema/weights.schema.json?raw";
import userSettingsSchema from "../../data/schema/user-settings.schema.json?raw";

/** Published file name -> text. Keyed by the same names as WORKSPACE_STATIC_DOCUMENTS. */
export const staticTexts = {
  "llm-guide.md": llmGuide,
  "domain.md": domain,
  "data-model.md": dataModel,
  "weights.md": weights,
  "questionnaire.md": questionnaire,
  "generator.md": generator,
  "importers.md": importers,
  "import-from-spreadsheet.md": importFromSpreadsheet,
  "meal-plan.md": mealPlan,
  "import.schema.json": importSchema,
  "meal-plan.schema.json": mealPlanSchema,
  "weights.schema.json": weightsSchema,
  "user-settings.schema.json": userSettingsSchema,
};

// The two lists are written out separately — one as imports Vite can resolve statically, one as the
// contract the workspace modules and the Python tests read — so this guards that they still agree.
const missing = Object.keys(WORKSPACE_STATIC_DOCUMENTS).filter((fileName) => !staticTexts[fileName]);
if (missing.length) throw new Error(`workspace-static-texts.js is missing: ${missing.join(", ")}`);
