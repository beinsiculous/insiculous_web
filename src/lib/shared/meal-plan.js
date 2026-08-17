// The meal plan (the fortnight menu): pure port of scripts/fk_core/meal_plan.py — keep both in sync;
// tests/test_meal_plan.py runs both on the same documents. Rules and the document contract: docs/meal-plan.md.
import { DAY_KEY_ORDER, WEEKDAY_NAMES } from "./fortknight-rules.js";

export const MEAL_PLAN_SCHEMA_VERSION = 1;
export const MEAL_PLAN_KIND = "meal-plan";
export const SECOND_DAY_OFFSETS = [2, 3, 4];
// Leftovers may cross meals: a dish eaten at a later-day meal can return at an earlier-day meal (dinner -> breakfast).
export const LEFTOVER_SOURCE_SLOTS = ["afternoon", "evening", "late-evening"];
export const LEFTOVER_TARGET_SLOTS = ["early-morning", "mid-morning", "afternoon"];

/** A meal's name as an id fragment: 'Lunch' -> 'lunch', 'Late snack' -> 'late-snack' (Python twin: meal_slug). */
export function mealSlug(name) {
  return String(name ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

/** A day key from 'sun-a', 'Sunday A', 'sunday-a' or 'Sun_A'; null when unreadable. */
export function dayKeyFromText(text) {
  const words = String(text ?? "").trim().toLowerCase().split(/[\s_-]+/).filter(Boolean);
  if (words.length !== 2 || !["a", "b"].includes(words[1])) return null;
  const weekday = WEEKDAY_NAMES.find((name) => name === words[0] || name.startsWith(words[0]));
  return weekday ? `${weekday.slice(0, 3)}-${words[1]}` : null;
}

/** 'sun-a' -> 'Sunday A'. */
export function dayLabel(dayKey) {
  const [weekday, variant] = dayKey.split("-");
  const name = WEEKDAY_NAMES.find((candidate) => candidate.startsWith(weekday));
  return `${name.charAt(0).toUpperCase()}${name.slice(1)} ${variant.toUpperCase()}`;
}

/** The days a first serving's leftovers may be eaten: 2, 3 or 4 days later, wrapping around the fortnight. */
export function allowedSecondDays(firstDayKey) {
  const index = DAY_KEY_ORDER.indexOf(firstDayKey);
  return SECOND_DAY_OFFSETS.map((offset) => DAY_KEY_ORDER[(index + offset) % DAY_KEY_ORDER.length]);
}

/** dinner--sun-a--wed-b; across meals: dinner--sun-a--breakfast--tue-a. */
export function itemId(meal, days, leftoversMeal = null) {
  if (days.length === 2 && leftoversMeal && leftoversMeal !== meal) return [meal, days[0], leftoversMeal, days[1]].join("--");
  return [meal, ...days].join("--");
}

/** May `targetMeal` eat `sourceMeal`'s leftovers? The same meal always; another meal when the source has an
 *  afternoon/evening/late-evening slot and the target an early-morning/mid-morning/afternoon slot. */
export function canTakeLeftovers(sourceMeal, targetMeal) {
  if (mealSlug(sourceMeal.name ?? "") === mealSlug(targetMeal.name ?? "")) return true;
  return (sourceMeal.slots || []).some((slot) => LEFTOVER_SOURCE_SLOTS.includes(slot)) && (targetMeal.slots || []).some((slot) => LEFTOVER_TARGET_SLOTS.includes(slot));
}

/** [[meal slug, day key]] the item occupies: the first serving at its meal, the leftovers at leftoversMeal or the same meal. */
export function itemServings(item) {
  const servings = [[item.meal, item.days[0]]];
  if (item.days.length === 2) servings.push([item.leftoversMeal || item.meal, item.days[1]]);
  return servings;
}

const pythonRepr = (value) => (typeof value === "string" ? `'${value}'` : value === undefined || value === null ? "None" : String(value));

/** A meal-plan document (or an already-stored plan) -> { normalized: {items}, problems }.
 *  `meals` = the profile's questionnaire meals (answers.meals.meals: [{name, ...}]). */
export function normalizeMealPlan(document, meals) {
  const slugs = {};
  const mealsBySlug = {};
  for (const meal of meals || []) {
    slugs[mealSlug(meal.name ?? "")] = meal.name ?? "";
    mealsBySlug[mealSlug(meal.name ?? "")] = meal;
  }
  const items = [];
  const problems = [];
  if (!document || typeof document !== "object" || Array.isArray(document) || !Array.isArray(document.items)) {
    return { normalized: { items: [] }, problems: ["a meal plan needs an items list"] };
  }
  document.items.forEach((item, index) => {
    let label = `item #${index + 1}`;
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      problems.push(`${label}: not an object`);
      return;
    }
    const slug = mealSlug(item.meal ?? "");
    const dish = String(item.dish ?? "").trim();
    if (dish) label = `${label} "${dish}"`;
    if (!slug || !(slug in slugs)) {
      problems.push(`${label}: unknown meal ${pythonRepr(item.meal)} (your meals: ${Object.values(slugs).join(", ") || "none"})`);
      return;
    }
    if (!dish) {
      problems.push(`${label}: needs a dish`);
      return;
    }
    const rawDays = item.days;
    if (!Array.isArray(rawDays) || rawDays.length < 1 || rawDays.length > 2) {
      problems.push(`${label}: days must list the first serving and optionally the leftovers day`);
      return;
    }
    const days = rawDays.map(dayKeyFromText);
    if (days.some((day) => day === null)) {
      problems.push(`${label}: cannot read day ${pythonRepr(rawDays[days.indexOf(null)])} (use sun-a … sat-b or Sunday A … Saturday B)`);
      return;
    }
    if (days.length === 2 && !allowedSecondDays(days[0]).includes(days[1])) {
      const allowed = allowedSecondDays(days[0]).map(dayLabel).join(", ");
      problems.push(`${label}: leftovers on ${dayLabel(days[1])} — after ${dayLabel(days[0])} they may be eaten on ${allowed} (never the next day, at most three days later)`);
      return;
    }
    let leftoversMeal = null;
    if (days.length === 2 && item.leftoversMeal) {
      leftoversMeal = mealSlug(item.leftoversMeal);
      if (!(leftoversMeal in slugs)) {
        problems.push(`${label}: unknown leftovers meal ${pythonRepr(item.leftoversMeal)} (your meals: ${Object.values(slugs).join(", ") || "none"})`);
        return;
      }
      if (leftoversMeal === slug) leftoversMeal = null;
      else if (!canTakeLeftovers(mealsBySlug[slug], mealsBySlug[leftoversMeal])) {
        problems.push(`${label}: ${slugs[slug]} leftovers cannot be ${slugs[leftoversMeal]} — leftovers move from an afternoon/evening/late-evening meal to an early-morning/mid-morning/afternoon meal`);
        return;
      }
    }
    const notes = item.notes;
    items.push({ id: itemId(slug, days, leftoversMeal), meal: slug, dish, days, leftoversMeal, notes: notes ? String(notes).trim() : null });
  });
  // One dish per meal per day: a later item that lands on a taken (meal, day) is reported and dropped (nothing invalid is stored).
  const seen = {};
  const kept = [];
  for (const item of items) {
    const servings = itemServings(item);
    const clash = servings.find(([meal, day]) => `${meal}|${day}` in seen);
    if (clash) {
      problems.push(`"${item.dish}" and "${seen[`${clash[0]}|${clash[1]}`]}" are both ${slugs[clash[0]]} on ${dayLabel(clash[1])} — one dish per meal per day; "${item.dish}" not applied`);
      continue;
    }
    for (const [meal, day] of servings) seen[`${meal}|${day}`] = item.dish;
    kept.push(item);
  }
  return { normalized: { items: kept }, problems };
}

/** New items replace existing ones with the same id; the rest are kept, in stored order then new order. */
export function mergeMealPlan(existingItems, newItems) {
  const byId = new Map(existingItems.map((item) => [item.id, item]));
  for (const item of newItems) byId.set(item.id, item);
  return [...byId.values()];
}

/** How the plan covers a meal: {dishes, covered, missing[]} over the 14 day keys. */
export function coverage(items, slug) {
  const covered = new Set();
  let dishes = 0;
  for (const item of items) {
    if (item.meal === slug) dishes += 1;
    for (const [meal, day] of itemServings(item)) if (meal === slug) covered.add(day);
  }
  return { dishes, covered: covered.size, missing: DAY_KEY_ORDER.filter((day) => !covered.has(day)) };
}

/** The day's menu in meal order: [{meal (name), slug, dish|null, leftovers, itemId}]. */
export function menuForDay(plan, meals, dayKey) {
  const items = plan?.items || [];
  return (meals || []).map((meal, index) => {
    const name = meal.name || `Meal ${index + 1}`; // weights saved before meals had names
    const slug = mealSlug(name);
    const entry = { meal: name, slug, dish: null, leftovers: false, itemId: null };
    for (const item of items) {
      const served = itemServings(item).findIndex(([meal, day]) => meal === slug && day === dayKey);
      if (served >= 0) {
        Object.assign(entry, { dish: item.dish, leftovers: served === 1, itemId: item.id });
        break;
      }
    }
    return entry;
  });
}

// The meal slot ids (questionnaire.options.mealSlots) as the tasks' time-of-day words (import-document TIME_OF_DAY_WORDS).
export const SLOT_TIME_OF_DAY = { "early-morning": "morning", "mid-morning": "morning", afternoon: "afternoon", evening: "evening", "late-evening": "night", anytime: "anytime" };
export const PREP_TIME_OF_DAY = "evening";
export const FORKKNIFE_SOURCE_KIND = "forkknife";

export function previousDayKey(dayKey) {
  return DAY_KEY_ORDER[(DAY_KEY_ORDER.indexOf(dayKey) - 1 + DAY_KEY_ORDER.length) % DAY_KEY_ORDER.length];
}

export function weekdayOf(dayKey) {
  const short = dayKey.split("-")[0];
  return WEEKDAY_NAMES.find((name) => name.startsWith(short));
}

/** The menu's prep and cook tasks as import-document (version 2) tasks — what ForkKnife creates for the person to
 *  paste into Apply from assistant. Per item: the meal needs cooking -> "Cook <dish> (<Meal>)" on the first serving
 *  at the meal's slot; needs prepping -> "Prep <dish> (<Meal>)" the day before, in the evening; each repeats every
 *  other week from the next date of that day key (`datesByDayKey`: day key -> ISO date), so the app's cadence lands
 *  it on the right A/B week. Returns { tasks, review }. Twin of fk_core.meal_plan.tasks_from_meal_plan. */
export function slugsToNames(meals) {
  return Object.fromEntries((meals || []).map((meal) => [mealSlug(meal.name ?? ""), meal.name ?? ""]));
}

export function tasksFromMealPlan(plan, meals, datesByDayKey) {
  const bySlug = Object.fromEntries((meals || []).map((meal) => [mealSlug(meal.name ?? ""), meal]));
  const tasks = [];
  const review = [];
  for (const item of plan?.items || []) {
    const meal = bySlug[item.meal];
    if (!meal) continue;
    const name = meal.name ?? item.meal;
    const firstDay = item.days[0];
    if (meal.needsCooked && (meal.cookMinutes ?? 0) > 0) {
      const slots = meal.slots || [];
      const when = slots.length ? (SLOT_TIME_OF_DAY[slots[0]] ?? "anytime") : "anytime";
      tasks.push({ title: `Cook ${item.dish} (${name})`, weekdays: [weekdayOf(firstDay)], repeats: `every other week from ${datesByDayKey[firstDay]}`, when, lasts: `${meal.cookMinutes} min`, category: "meals" });
      const leftoversWords = item.days.length === 2 ? `; leftovers ${dayLabel(item.days[1])}` + (item.leftoversMeal ? ` as ${slugsToNames(meals)[item.leftoversMeal] ?? item.leftoversMeal}` : "") : "";
      review.push(`Cook ${item.dish} for ${name} on ${dayLabel(firstDay)} (${meal.cookMinutes} min, ${when})${leftoversWords}`);
    }
    if (meal.needsPrepped && (meal.prepMinutes ?? 0) > 0) {
      const prepDay = previousDayKey(firstDay);
      tasks.push({ title: `Prep ${item.dish} (${name})`, weekdays: [weekdayOf(prepDay)], repeats: `every other week from ${datesByDayKey[prepDay]}`, when: PREP_TIME_OF_DAY, lasts: `${meal.prepMinutes} min`, category: "meals" });
      review.push(`Prep ${item.dish} for ${name} on ${dayLabel(prepDay)} evening (${meal.prepMinutes} min), the day before ${dayLabel(firstDay)}`);
    }
  }
  return { tasks, review };
}

/** The whole import document (version 2) ForkKnife creates: the tasks, a readable review, and the menu itself. */
export function forkknifeImportDocument(plan, meals, datesByDayKey, description = "Meal prep and cooking tasks from the ForkKnife menu") {
  const { tasks, review } = tasksFromMealPlan(plan, meals, datesByDayKey);
  return {
    schemaVersion: 2,
    source: { kind: FORKKNIFE_SOURCE_KIND, description },
    commitments: [],
    tasks,
    skipped: [],
    review,
    mealPlan: { items: (plan?.items || []).map((item) => ({ meal: item.meal, dish: item.dish, days: [...item.days], leftoversMeal: item.leftoversMeal ?? null, notes: item.notes ?? null })) },
  };
}

/** Meals renamed in the questionnaire keep their dishes: items of an old slug move to the new one (ids follow).
 *  `renames` = {oldSlug: newSlug}. */
export function retagMealPlan(plan, renames) {
  const items = (plan?.items || []).map((item) => {
    const meal = renames[item.meal] ?? item.meal;
    const leftoversMeal = item.leftoversMeal ? (renames[item.leftoversMeal] ?? item.leftoversMeal) : null;
    if (meal === item.meal && leftoversMeal === (item.leftoversMeal ?? null)) return item;
    return { ...item, meal, leftoversMeal, id: itemId(meal, item.days, leftoversMeal) };
  });
  return { items };
}

/** The stored plan re-checked against the profile's meals (renamed meals orphan items): first problem or null. */
export function mealPlanProblem(plan, meals) {
  if (plan === null || plan === undefined) return null;
  const { problems } = normalizeMealPlan(plan, meals);
  return problems.length ? problems[0] : null;
}
