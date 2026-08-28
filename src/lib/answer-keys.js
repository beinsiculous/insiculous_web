// Which page owns which questionnaire answer keys. Two pages write into the one shared profile — FortKnight's
// Build page (the menu, the commitments and the tasks) and FortKnight's Questionnaire (everything else) — so each
// save reads the profile as stored at that moment and writes only its own keys over it (docs/app.md). Naming the
// sets here keeps the pages from drifting apart; the picking itself is the shared `pickAnswers`.
import { MEAL_ANSWER_KEYS } from "./shared/weights-rules.js";

/** The fortnight menu, nothing else. */
export const MENU_ANSWER_KEYS = ["mealPlan"];
/** FortKnight's Build page: the menu plus the commitments and tasks. */
export const BUILD_ANSWER_KEYS = ["mealPlan", "standingAppointments", "tasks"];
/** What FortKnight's Questionnaire owns nothing of and must carry through untouched on every save. */
export const NOT_FORTKNIGHT_QUESTIONNAIRE_KEYS = [...new Set([...MEAL_ANSWER_KEYS, ...BUILD_ANSWER_KEYS])];
