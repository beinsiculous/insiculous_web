// Which page owns which questionnaire answer keys. Four pages write into the one shared profile — ForkKnife's
// Questionnaire (meals and preferences), its Spoon Feed page (the menu), FortKnight's Build page (the menu, the
// commitments and the tasks) and FortKnight's Questionnaire (everything else) — so each save reads the profile as
// stored at that moment and writes only its own keys over it (docs/app.md). Naming the sets here keeps the four
// pages from drifting apart; the picking itself is the shared `pickAnswers`.
import { FORKKNIFE_ANSWER_KEYS } from "./shared/weights-rules.js";

/** ForkKnife's Spoon Feed page: the fortnight menu, nothing else. */
export const MENU_ANSWER_KEYS = ["mealPlan"];
/** FortKnight's Build page: the menu it shares with Spoon Feed, plus the commitments and tasks. */
export const BUILD_ANSWER_KEYS = ["mealPlan", "standingAppointments", "tasks"];
/** What FortKnight's Questionnaire owns nothing of and must carry through untouched on every save. */
export const NOT_FORTKNIGHT_QUESTIONNAIRE_KEYS = [...new Set([...FORKKNIFE_ANSWER_KEYS, ...BUILD_ANSWER_KEYS])];
