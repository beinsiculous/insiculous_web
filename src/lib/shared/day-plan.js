// One day of a person's fortnight, from their active profile: their blocks with the focus their grid gives them (own or imported), the
// imported fixed activities of that day key, the standing appointments that land on it, and the menu
// entries the import carried. Pure; canonical module, mirrored by scripts/fk_core/derive.py and rendered by the
// /days/<dayKey>/ page. Nothing here reads the bundle's own activities — those are the data set's, not
// the person's (docs/app.md).
import { recurringItemActivities, standingAppointmentActivities, timeStringToMinutes } from "./weights-rules.js";
import { blockKeyForTime } from "./clock.js";
import { TIME_OF_DAY_MINUTES } from "./import-document.js";
import { menuForDay } from "./meal-plan.js";

// blockKeyForTime lives in clock.js (the generator needs it too); re-exported so existing importers keep working.
export { blockKeyForTime };

/** The imported menu entries for a day: the reserved `meals` array carries either `dayKey` or `days` (menu meals). */
export function mealsForDay(importDocument, dayKey) {
  const meals = Array.isArray(importDocument?.meals) ? importDocument.meals : [];
  return meals
    .filter((meal) => meal && (meal.dayKey === dayKey || (Array.isArray(meal.days) && meal.days.includes(dayKey))))
    .map((meal) => ({ slot: meal.slot || null, menu: meal.menu ?? meal.title ?? meal.raw?.menu ?? "", cookExtra: Boolean(meal.cookExtra) }));
}

/** The imported fixed activities of a day, in start order (untimed ones last, then by priority). */
export function importedActivitiesForDay(importDocument, dayKey) {
  const activities = Array.isArray(importDocument?.fixedActivities) ? importDocument.fixedActivities : [];
  return activities
    .filter((activity) => activity && activity.dayKey === dayKey)
    .map((activity) => ({
      id: activity.id,
      title: activity.title,
      priority: activity.priority ?? null,
      categories: activity.categories || [],
      block: activity.block ?? null,
      start: activity.timing?.estimatedStart ?? activity.timing?.timeStart ?? null,
      end: activity.timing?.estimatedEnd ?? activity.timing?.timeFinished ?? null,
      detail: activity.detail?.raw ?? activity.detail?.text ?? null,
      source: "import",
    }))
    .sort(activityOrder);
}

/** The standing appointments that land on a day key (weekly / every-other-week; pooled cadences have no day). */
export function standingAppointmentsForDay(standingAppointments, days, dayKey, resolveDayKey = null) {
  const appointments = standingAppointments || [];
  const { activities } = standingAppointmentActivities(appointments, days, resolveDayKey);
  return activities
    .filter((activity) => activity.dayKey === dayKey)
    .map((activity) => {
      const index = Number(/--(\d+)$/.exec(activity.id)?.[1]) - 1; // standing--<slug>--<index+1> (slugs never contain "--")
      const appointment = appointments[index] || {};
      return {
        id: activity.id,
        title: appointment.title || "Appointment",
        priority: 1,
        categories: activity.categories,
        block: null,
        start: activity.timing.estimatedStart,
        end: activity.timing.estimatedEnd,
        detail: null,
        source: "standing-appointment",
      };
    })
    .sort(activityOrder);
}

/** The tasks (`answers.tasks`: typed in Startup 2 or merged from an applied import document) that land on a
 *  day key. A task is placed by its start when it has one, else by its time-of-day word (`timeOfDay`, mapped
 *  to a clock time by TIME_OF_DAY_MINUTES; "anytime" stays unplaced) — never an anchor. */
export function tasksForDay(answerTasks, days, dayKey, resolveDayKey = null) {
  const tasks = [...(answerTasks || [])];
  const { activities } = recurringItemActivities(tasks, days, resolveDayKey, { idPrefix: "task", source: "task", priority: 2, flexibility: "yes" });
  return activities
    .filter((activity) => activity.dayKey === dayKey)
    .map((activity) => {
      const index = Number(/--(\d+)$/.exec(activity.id)?.[1]) - 1; // task--<slug>--<index+1> (slugs never contain "--")
      const task = tasks[index] || {};
      return {
        id: activity.id,
        title: task.title || "Task",
        priority: 2,
        categories: activity.categories,
        block: null,
        start: activity.timing?.estimatedStart ?? null,
        end: activity.timing?.estimatedEnd ?? null,
        timeOfDay: activity.timing ? null : task.timeOfDay ?? "anytime",
        placeBy: activity.timing ? null : TIME_OF_DAY_MINUTES[task.timeOfDay] ?? null,
        detail: task.from ?? null,
        source: "task",
      };
    })
    .sort(activityOrder);
}

function activityOrder(left, right) {
  const leftStart = left.start ? timeStringToMinutes(left.start) : Number.POSITIVE_INFINITY;
  const rightStart = right.start ? timeStringToMinutes(right.start) : Number.POSITIVE_INFINITY;
  if (leftStart !== rightStart) return leftStart - rightStart;
  return (left.priority ?? 9) - (right.priority ?? 9);
}

/** A generator-proposed activity (weights.proposal.activities / generateActivities) as a day-plan item. */
export function proposedActivityItem(activity) {
  return {
    id: activity.id,
    title: activity.title,
    priority: activity.priority ?? null,
    categories: activity.categories || [],
    block: activity.block ?? null,
    start: activity.timing?.estimatedStart ?? null,
    end: activity.timing?.estimatedEnd ?? null,
    minutes: activity.minutes ?? null,
    detail: activity.reason ?? null,
    source: "proposed",
  };
}

/** The whole day: {dayKey, label, week, weekday, hasImport, blocks: [{key, start, end, carriesFocus, focus,
 *  isAppointmentBlock, activities}], unplaced: [activities no block holds], meals, menu}. `weights` is the profile's
 *  weights (its blocks/grid/appointment blocks), `answers` its questionnaire answers (import + appointments);
 *  `proposedActivities` are the generator's records for this profile (any day; filtered here), listed after
 *  the person's own items with source "proposed". */
export function dayPlan({ weights, answers, dayKey, days, resolveDayKey = null, proposedActivities = [] }) {
  const day = days.days[dayKey];
  const importDocument = answers?.startup?.import || null;
  const blocks = (weights?.blocks || []).map((block) => ({
    key: block.key, start: block.start, end: block.end, carriesFocus: Boolean(block.carriesFocus),
    focus: weights?.blockFocusGrid?.[dayKey]?.[block.key] ?? null,
    isAppointmentBlock: weights?.appointmentBlocks?.[dayKey] === block.key,
    activities: [],
  }));
  const blockKeys = new Set(blocks.map((block) => block.key));
  const unplaced = [];
  const place = (activity) => {
    const placeBy = activity.start ?? activity.placeBy ?? null;
    const key = (activity.block && blockKeys.has(activity.block) ? activity.block : null) ?? (placeBy ? blockKeyForTime(blocks, placeBy) : null);
    const target = blocks.find((block) => block.key === key);
    if (target) target.activities.push(activity); else unplaced.push(activity);
  };
  for (const activity of importedActivitiesForDay(importDocument, dayKey)) place(activity);
  for (const activity of standingAppointmentsForDay(answers?.standingAppointments, days, dayKey, resolveDayKey)) place(activity);
  for (const activity of tasksForDay(answers?.tasks, days, dayKey, resolveDayKey)) place(activity);
  for (const activity of proposedActivities) if (activity.dayKey === dayKey) place(proposedActivityItem(activity));
  for (const block of blocks) block.activities.sort(activityOrder);
  return {
    dayKey, label: day.label, week: day.week, weekday: day.weekday,
    hasImport: Boolean(importDocument),
    blocks, unplaced: unplaced.sort(activityOrder),
    meals: mealsForDay(importDocument, dayKey),
    // The fortnight menu (the meal-plan document): one entry per named meal, dish null when unplanned.
    menu: menuForDay(answers?.mealPlan, weights?.meals?.meals, dayKey),
  };
}
