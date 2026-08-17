// ForkKnife page helpers shared by its Overview, Spoon Feed and Assistant pages (docs/meal-plan.md): the active
// profile's meals + menu, the next date of every day key (for Create tasks), and the meal-plan template.
import { loadSettings } from "./shared/user-settings.js";
import { activeWeights, defaultAnswers, mealsWithDefaults, personDayKeyResolver } from "./shared/weights-rules.js";
import { MEAL_PLAN_KIND, MEAL_PLAN_SCHEMA_VERSION, allowedSecondDays, normalizeMealPlan } from "./shared/meal-plan.js";
import { DAY_KEY_ORDER, formatIsoDate, parseIsoDate } from "./shared/fortknight-rules.js";
import { localTodayIsoDate } from "./shared/clock.js";

/** The active profile's answers (or the typical-person defaults), its meals with defaults filled, and its menu
 *  normalised against them (`problems` lists stored items that no longer match the meals). */
export function loadMealPlan(bundle, settings = loadSettings()) {
  const profile = activeWeights(settings);
  const answers = profile?.questionnaire?.answers ?? defaultAnswers(bundle.questionnaire, bundle.categories);
  const meals = mealsWithDefaults(answers.meals ?? defaultAnswers(bundle.questionnaire, bundle.categories).meals, bundle.questionnaire).meals;
  const { normalized, problems } = normalizeMealPlan(answers.mealPlan || { items: [] }, meals);
  return { settings, saved: Boolean(profile), answers, meals, items: normalized.items, problems };
}

/** The next calendar date of every day key, by the person's own seasons (today + 0…13 days). */
export function datesByDayKey(answers, bundle, settings) {
  const resolve = personDayKeyResolver(answers, bundle, settings.epochOverride?.date ? settings.epochOverride : null);
  const start = parseIsoDate(localTodayIsoDate());
  const dates = {};
  for (let offset = 0; offset < DAY_KEY_ORDER.length; offset += 1) {
    const date = new Date(start.getTime() + offset * 24 * 60 * 60 * 1000);
    const isoDate = formatIsoDate(date);
    const dayKey = resolve(isoDate);
    if (!(dayKey in dates)) dates[dayKey] = isoDate;
  }
  return dates;
}

/** A meal-plan document with the person's meals filled in and one example item per meal (docs/meal-plan.md). */
export function mealPlanTemplate(meals, bundle) {
  return {
    schemaVersion: MEAL_PLAN_SCHEMA_VERSION,
    kind: MEAL_PLAN_KIND,
    source: { kind: "assistant", description: "fill in: where this menu came from" },
    notes: ["One dish per meal per day. days = [first serving, leftovers day?]; the leftovers day is never the next day and at most three days later (the fortnight wraps). Meals: " + meals.map((meal) => meal.name).join(", ") + ". Days: sun-a … sat-b or Sunday A … Saturday B."],
    items: meals.map((meal, index) => ({ meal: meal.name, dish: `example ${meal.name.toLowerCase()} dish`, days: [bundle.days.order[index % 14], allowedSecondDays(bundle.days.order[index % 14])[0]] })),
  };
}
