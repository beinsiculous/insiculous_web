// The assistant workspace: the set of files a person uploads into their own AI workspace
// (a Claude Project, a ChatGPT/Kimi/NotebookLM workspace, ...) so an assistant there can help
// with their schedule, plus the classifier for what the assistant hands back.
// Pure: no DOM, no fetch, no storage — the same list drives src/lib/workspace-static-texts.js (which
// imports each source at build time), the /profile/ page (downloads), the two assistant pages (the guide
// rows and prompts), tests, and (later) native clients. Contract: docs/assistant-workspace.md.
import { formatIsoDate, parseIsoDate, resolveDate } from "./fortknight-rules.js";
import { activeWeights, personCalendarFromSettings } from "./weights-rules.js";

/** Published file name -> repo-relative source. `llm-guide.md` is folded into README.md, not published alone. */
export const WORKSPACE_STATIC_DOCUMENTS = {
  "llm-guide.md": "docs/llm-guide.md",
  "domain.md": "docs/domain.md",
  "data-model.md": "docs/data-model.md",
  "weights.md": "docs/weights.md",
  "questionnaire.md": "docs/questionnaire.md",
  "generator.md": "docs/generator.md",
  "importers.md": "docs/importers.md",
  "import-from-spreadsheet.md": "docs/import-from-spreadsheet.md",
  "meal-plan.md": "docs/meal-plan.md",
  "keep-format.md": "docs/keep-format.md",
  "import.schema.json": "data/schema/import.schema.json",
  "meal-plan.schema.json": "data/schema/meal-plan.schema.json",
  "weights.schema.json": "data/schema/weights.schema.json",
  "user-settings.schema.json": "data/schema/user-settings.schema.json",
  "keep.schema.json": "data/schema/keep.schema.json",
};

export const README_FILE_NAME = "README.md";
/** The spreadsheet → import-document method; the Assistant page shows its row under Apply (a standalone how-to), not in the workspace list. */
export const SPREADSHEET_GUIDE_FILE_NAME = "import-from-spreadsheet.md";
/** What the person tells their assistant along with the guide and their spreadsheet. */
export const SPREADSHEET_PROMPT = "Read import-from-spreadsheet.md, then turn the attached spreadsheet into a FortKnight import document (schemaVersion 2). Follow its steps: survey every sheet, decide commitment / task / skipped for each row, list what you skipped and why, and end with exactly one JSON code block.";
/** The meal-plan contract; the Assistant page shows its row next to the prompt below. */
export const MEAL_PLAN_GUIDE_FILE_NAME = "meal-plan.md";

const PROMPT_FREE_TEXT_LIMIT = 600;
/** Free text on its own quoted line: fences stripped so it cannot end the assistant's code block early, trimmed and capped. */
function quotedFreeText(text) {
  const cleaned = String(text).replace(/`{3,}/g, "").replace(/\s+/g, " ").trim();
  if (!cleaned) return null;
  return `"${cleaned.length > PROMPT_FREE_TEXT_LIMIT ? `${cleaned.slice(0, PROMPT_FREE_TEXT_LIMIT)}…` : cleaned}"`;
}
function optionLabels(optionIds, optionList) {
  const labels = (optionIds || []).map((optionId) => optionList.find((option) => option.id === optionId)?.label ?? optionId);
  return labels.length ? labels.join(", ") : null;
}
function mealDescription(meal, questionnaire) {
  const slots = optionLabels(meal.slots, questionnaire.options.mealSlots) || "time of day not set";
  const cooking = [meal.needsPrepped ? `prepped ${meal.prepMinutes} min` : null, meal.needsCooked ? `cooked ${meal.cookMinutes} min` : null].filter(Boolean);
  return `${meal.name} (${slots}; ${cooking.length ? cooking.join(", ") : "no prep or cooking"})`;
}
/** What the person tells their assistant to draft the fortnight menu: the meals (with defaults filled — pass
 *  mealsWithDefaults(...).meals) and every answered meal preference; blank answers are left out. */
export function mealPlanPrompt({ meals, answers, questionnaire }) {
  const options = questionnaire.options;
  const preferences = [
    answers.eaters !== undefined && answers.eaters !== 1 ? `${answers.eaters} people eat these meals` : null,
    optionLabels(answers.dietaryRules, options.dietaryRules) ? `dietary rules: ${optionLabels(answers.dietaryRules, options.dietaryRules)}` : null,
    quotedFreeText(answers.allergiesAndDislikes ?? "") ? `allergies, intolerances and foods I won’t eat: ${quotedFreeText(answers.allergiesAndDislikes)}` : null,
    optionLabels(answers.favouriteCuisines, options.cuisines) ? `cuisines I like: ${optionLabels(answers.favouriteCuisines, options.cuisines)}` : null,
    quotedFreeText(answers.favouriteDishes ?? "") ? `dishes I already cook and like (keep them in the rotation): ${quotedFreeText(answers.favouriteDishes)}` : null,
    answers.cookingSkill ? `cooking: ${optionLabels([answers.cookingSkill], options.cookingSkills)}` : null,
    answers.foodBudget ? `budget: ${optionLabels([answers.foodBudget], options.foodBudgets)}` : null,
    optionLabels(answers.kitchenKit, options.kitchenKit) ? `kitchen: ${optionLabels(answers.kitchenKit, options.kitchenKit)}` : null,
    answers.shoppingCadence ? `I shop ${optionLabels([answers.shoppingCadence], options.shoppingCadences)}` : null,
  ].filter(Boolean);
  return [
    `Read ${MEAL_PLAN_GUIDE_FILE_NAME}, then draft my fortnight menu as a meal-plan document (schemaVersion 1, kind "meal-plan").`,
    `My meals: ${meals.map((meal) => mealDescription(meal, questionnaire)).join("; ")}.`,
    preferences.length ? `Preferences: ${preferences.join("; ")}.` : null,
    "About eight dishes per meal cover the fourteen days (six eaten twice — the second day is leftovers, never the next day and at most three days later — and two eaten once); one dish per meal per day. Name each dish plainly and end with exactly one JSON code block.",
  ].filter(Boolean).join("\n");
}
export const DATA_FILE_NAME = "fortknight-data.json";
export const SETTINGS_FILE_NAME = "fortknight-user-settings.json";
/** The published weights file is the active profile's: weights.<id>.json. */
export function weightsFileName(weightsId) {
  return `weights.${weightsId}.json`;
}
export const WEIGHTS_FILE_PATTERN = "weights.<id>.json";
export const WORKSPACE_GENERATED_FILES = [README_FILE_NAME, DATA_FILE_NAME, SETTINGS_FILE_NAME, WEIGHTS_FILE_PATTERN];
export const UPCOMING_DATES_COUNT = 90;

const FILE_PURPOSES = {
  [README_FILE_NAME]: "start here — what FortKnight is, how to help, how to reply",
  "domain.md": "vocabulary: day keys, blocks, seasons, focus, categories",
  "data-model.md": "every JSON file and field in fortknight-data.json",
  "weights.md": "the weights contract (how much of the fortnight each category gets)",
  "questionnaire.md": "the questions and how answers become weights",
  "generator.md": "how the weights file’s `proposal` (a proposed block focus grid) is generated and read",
  "importers.md": "the import document: turning an existing planner/calendar into standing appointments, fixed activities and a block focus grid",
  "import-from-spreadsheet.md": "the method for reading a spreadsheet (or any calendar export) into an import document: survey, classify, map, check completeness, worked example",
  "meal-plan.md": "the fortnight menu: the meal-plan document (dishes per meal and the days they are eaten, leftovers rules) the Assistant page’s menu prompt asks for and applies",
  "import.schema.json": "JSON schema for an import document",
  "meal-plan.schema.json": "JSON schema for a meal-plan document",
  "weights.schema.json": "JSON schema for a weights file",
  "user-settings.schema.json": "JSON schema for the on-device settings file",
  [DATA_FILE_NAME]: "the built data bundle (the person-neutral vocabulary: categories, blocks, day keys, seasons — no schedule of anyone’s) plus upcomingDates",
  [SETTINGS_FILE_NAME]: "this person’s on-device settings: every saved profile under weightsProfiles (answers live inside each profile’s questionnaire.answers) and which one is active",
};
const WEIGHTS_FILE_PURPOSE = "this person’s active profile’s weights, derived from their questionnaire answers";

function jsonText(value) {
  return JSON.stringify(value, null, 2) + "\n";
}

/** The next `count` calendar dates resolved to day key / week / season, so the assistant never guesses. */
export function upcomingDates(bundle, todayIsoDate, epochOverride = null, count = UPCOMING_DATES_COUNT, seasons = null) {
  const start = parseIsoDate(todayIsoDate);
  const dates = [];
  for (let offset = 0; offset < count; offset += 1) {
    const date = new Date(start.getTime() + offset * 86400000);
    const resolution = resolveDate(bundle, date, epochOverride, seasons);
    dates.push({ date: formatIsoDate(date), dayKey: resolution.dayKey, week: resolution.week, seasonId: resolution.season.id, seasonName: resolution.season.name, seasonSource: resolution.seasonSource });
  }
  return dates;
}

function readmeText(fileNames, todayIsoDate, weightsName, llmGuideText) {
  const index = fileNames.map((fileName) => `- \`${fileName}\` — ${FILE_PURPOSES[fileName] || (fileName === weightsName ? WEIGHTS_FILE_PURPOSE : "")}`).join("\n");
  const weightsNote = weightsName
    ? ""
    : `\n> This person has not saved their Questionnaire yet, so there is no \`${WEIGHTS_FILE_PATTERN}\` file; ask them to fill in the Questionnaire in the app, or help them by proposing a weights file.\n`;
  return [
    "# 🏰🛡️ FortKnight assistant workspace",
    "",
    `Generated ${todayIsoDate} by the FortKnight app for one person’s repeating 14-day (fortnight) schedule.`,
    "Upload every file in this set to your workspace; together they are the assistant’s whole context.",
    "Nothing here was sent anywhere by the app — the person chose to upload it.",
    "The person may also send you one of the app’s prompts: the Assistant page’s spreadsheet prompt (with import-from-spreadsheet.md and their spreadsheet) or its menu prompt (their meals and preferences; answer with a meal-plan document, meal-plan.md).",
    "",
    "## Files",
    index,
    weightsNote,
    "## How to help",
    "",
    llmGuideText.replace(/^# .*\n/, "").trim(),
    "",
  ].join("\n");
}

/** Build the whole file set. `staticTexts` maps each WORKSPACE_STATIC_DOCUMENTS file name to its text. */
export function buildWorkspaceDocuments({ bundle, settings, staticTexts, todayIsoDate }) {
  const documents = [];
  const staticNames = Object.keys(WORKSPACE_STATIC_DOCUMENTS).filter((fileName) => fileName !== "llm-guide.md");
  const weights = activeWeights(settings);
  const weightsName = weights ? weightsFileName(weights.id) : null;
  const publishedNames = [README_FILE_NAME, ...staticNames, DATA_FILE_NAME, SETTINGS_FILE_NAME, ...(weightsName ? [weightsName] : [])];
  documents.push({ fileName: README_FILE_NAME, mediaType: "text/markdown", text: readmeText(publishedNames, todayIsoDate, weightsName, staticTexts["llm-guide.md"] || "") });
  for (const fileName of staticNames) {
    const mediaType = fileName.endsWith(".json") ? "application/json" : "text/markdown";
    documents.push({ fileName, mediaType, text: staticTexts[fileName] || "" });
  }
  const { questionnaire, ...data } = bundle;
  documents.push({ fileName: DATA_FILE_NAME, mediaType: "application/json", text: jsonText({ ...data, upcomingDates: upcomingDates(bundle, todayIsoDate, settings.epochOverride, UPCOMING_DATES_COUNT, personCalendarFromSettings(settings, bundle).seasons) }) });
  documents.push({ fileName: SETTINGS_FILE_NAME, mediaType: "application/json", text: jsonText(settings) });
  if (weights) documents.push({ fileName: weightsName, mediaType: "application/json", text: jsonText(weights) });
  return documents;
}

/** What kind of FortKnight document an assistant handed back: "weights" | "import-document" | "user-settings" | null.
 *  Weights files carry a string `source`; import documents an object `source`; settings files no `source` at all. */
export function classifyAssistantDocument(value) {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  if (typeof value.cycleLengthDays === "number" && typeof value.source === "string" && value.categories) return "weights";
  if (value.kind === "meal-plan" && Array.isArray(value.items)) return "meal-plan";
  if (Number.isInteger(value.schemaVersion) && typeof value.source?.kind === "string") return "import-document"; // any version; the normalizer rejects unknown ones
  if (Number.isInteger(value.schemaVersion) && value.source === undefined && value.cycleLengthDays === undefined) return "user-settings";
  return null;
}
