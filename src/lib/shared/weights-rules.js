// Questionnaire answers -> weights. Pure port of scripts/fk_core/weights.py — keep both in sync;
// tests/test_weights.py runs both on the same fixture and asserts identical output.
// No DOM, no fetch: takes the bundle's `categories` and `questionnaire` (+ `days` for standing
// appointments) as inputs; anchors come from the answers themselves (applied import + standing
// appointments), the optional `activities` argument is only an extra-anchors hook.
import { CYCLE_LENGTH_DAYS, DAY_KEY_ORDER, FLEXIBLE_FOCUS, NEW_MOON_MAX_INDEX, NTH_OCCURRENCES, SNAP_DIRECTIONS, START_RULE_KINDS, WEEKDAY_NAMES, dayKeyForDatePersonFirst, dayKeyFromWeekdayAndVariant, parseIsoDate, resolveDate } from "./fortknight-rules.js";
import { SOLAR_TERM_ORDER } from "./astronomy.js";
import { MINUTES_PER_DAY, formatClockRange, formatClockTime, localTodayIsoDate, minutesToTimeString, timeStringToMinutes } from "./clock.js";
import { TIME_OF_DAY_WORDS, normalizeImportDocument } from "./import-document.js";
import { proposalFromWeights } from "./generator-rules.js";
import { mealPlanProblem, mealSlug, mergeMealPlan, normalizeMealPlan } from "./meal-plan.js";

// Clock helpers live in clock.js; re-exported so existing importers of this module keep working.
export { formatClockRange, formatClockTime, minutesToTimeString, timeStringToMinutes };

const SHARE_DECIMALS = 4;
const UNSCHEDULED_BLOCK_KEY = "unscheduled";
export const FLEXIBLE_BLOCK_KEY = "flexible"; // the single focus block of a 2-block day (a block key, not the "flexible" focus)
export const DEFAULT_AGENDA_SCOPE = "categories";
export const DEFAULT_ENERGY_PEAK = "varies";
const IMPORT_ANCHOR_SOURCE = "import";

/** Deterministic half-up rounding, identical to fk_core.weights.round_half_up. */
export function roundHalfUp(value, decimals = 0) {
  const factor = 10 ** decimals;
  return Math.floor(value * factor + 0.5) / factor;
}

/** A typical person's answers: each subject at its `default` range with `peripheralByDefault`,
 *  the questionnaire's pre-ticked category boxes, and the default unscheduled block. */
export function defaultAnswers(questionnaire, categories) {
  const subjectTime = {};
  for (const subjectId of Object.keys(categories.subjects)) {
    const slider = questionnaire.subjectSliders[subjectId];
    subjectTime[subjectId] = { minutesPerDay: { ...slider.default }, peripheral: Boolean(slider.peripheralByDefault), more: false, goal: false };
  }
  const preset = questionnaire.defaultAnswers || {};
  return {
    startup: { groupSize: 1, importJson: "", import: null },
    subjectTime,
    sentiment: { ...(preset.sentiment || {}) },
    delegable: [...(preset.delegable || [])],
    essential: [...(preset.essential || [])],
    wakingWindow: { ...questionnaire.wakingWindow.default },
    meals: deepCopy(preset.meals || { perDay: questionnaire.mealsPerDay.default, meals: [] }),
    yearSplit: yearSplitFromScheme(questionnaire, preset.yearSplitScheme || "quarters"),
    weekStart: preset.weekStart || DEFAULT_WEEK_START,
    standingAppointments: deepCopy(preset.standingAppointments || []),
    tasks: deepCopy(preset.tasks || []),
    appointmentWeekdays: [...(preset.appointmentWeekdays || [])],
    practices: [...(preset.practices || [])],
    agendaScope: preset.agendaScope || DEFAULT_AGENDA_SCOPE,
    restDays: [...(preset.restDays || [])],
    energyPeak: preset.energyPeak || DEFAULT_ENERGY_PEAK,
    context: preset.context ?? "",
    // ForkKnife's questionnaire (docs/meal-plan.md): the assistant prompt embeds these; nothing here moves shares.
    eaters: preset.eaters ?? 1,
    dietaryRules: [...(preset.dietaryRules || [])],
    allergiesAndDislikes: preset.allergiesAndDislikes ?? "",
    favouriteCuisines: [...(preset.favouriteCuisines || [])],
    favouriteDishes: preset.favouriteDishes ?? "",
    cookingSkill: preset.cookingSkill ?? "comfortable",
    foodBudget: preset.foodBudget ?? "moderate",
    kitchenKit: [...(preset.kitchenKit || [])],
    shoppingCadence: preset.shoppingCadence ?? "weekly",
  };
}

/** The ForkKnife questionnaire's answer keys: which option list each select answer must come from (null = free text /
 *  number). A missing key means the default (profiles saved before ForkKnife had a questionnaire). */
export const MEAL_PREFERENCE_ANSWERS = {
  eaters: null,
  dietaryRules: "dietaryRules",
  allergiesAndDislikes: null,
  favouriteCuisines: "cuisines",
  favouriteDishes: null,
  cookingSkill: "cookingSkills",
  foodBudget: "foodBudgets",
  kitchenKit: "kitchenKit",
  shoppingCadence: "shoppingCadences",
};

/** The answer keys ForkKnife's questionnaire owns (its meals question, the menu, the preferences above). The two
 *  questionnaire pages write the same profile: each saves its own keys over the answers *stored at save time* and
 *  carries the other face's keys through untouched (docs/app.md). */
export const FORKKNIFE_ANSWER_KEYS = ["meals", "mealPlan", ...Object.keys(MEAL_PREFERENCE_ANSWERS)];

/** The subset of `answers` under `keys` (keys absent from answers stay absent). */
export function pickAnswers(answers, keys) {
  const picked = {};
  for (const key of keys) if (answers && answers[key] !== undefined) picked[key] = deepCopy(answers[key]);
  return picked;
}

/** The meal-preference answers checked against their option lists (undefined = default, always fine); a problem string or null. */
export function mealPreferencesProblem(answers, questionnaire) {
  if (answers.eaters !== undefined && !(Number.isInteger(answers.eaters) && answers.eaters >= 1)) return "Eaters must be a whole number of at least 1.";
  for (const [key, listName] of Object.entries(MEAL_PREFERENCE_ANSWERS)) {
    const value = answers[key];
    if (value === undefined) continue;
    if (listName === null) {
      if (key !== "eaters" && typeof value !== "string") return `${key} must be text.`;
      continue;
    }
    const known = questionnaire.options[listName].map((option) => option.id);
    const values = Array.isArray(value) ? value : [value];
    if (!Array.isArray(value) && Array.isArray(questionnaire.defaultAnswers?.[key])) return `${key} must be a list.`;
    const bad = values.find((optionId) => !known.includes(optionId));
    if (bad !== undefined) return `${key} must be one of ${known.join(", ")} (got ${JSON.stringify(bad)}).`;
  }
  return null;
}

/** Each meal filled out: name (Meal n when unnamed), slots, needsPrepped/needsCooked (default false) and the
 *  prep/cook minutes (questionnaire.mealPrep defaults) — the shape weights.meals carries and the meal plan keys off. */
export function mealsWithDefaults(mealsAnswer, questionnaire) {
  // A meal saved before these fields existed takes the questionnaire's default meal at the same position
  // (Breakfast / Dinner / Snack), else "Meal n" and the mealPrep defaults.
  const mealPrep = questionnaire.mealPrep || { defaultPrepMinutes: 0, defaultCookMinutes: 0 };
  const presets = questionnaire.defaultAnswers?.meals?.meals || [];
  const meals = ((mealsAnswer || {}).meals || []).map((meal, index) => {
    const preset = presets[index] || {};
    return {
      name: String(meal.name || preset.name || `Meal ${index + 1}`).trim(),
      slots: [...(meal.slots || [])],
      needsPrepped: Boolean(meal.needsPrepped ?? preset.needsPrepped ?? false),
      needsCooked: Boolean(meal.needsCooked ?? preset.needsCooked ?? false),
      prepMinutes: Math.trunc(Number(meal.prepMinutes ?? preset.prepMinutes ?? mealPrep.defaultPrepMinutes)),
      cookMinutes: Math.trunc(Number(meal.cookMinutes ?? preset.cookMinutes ?? mealPrep.defaultCookMinutes)),
    };
  });
  return { perDay: (mealsAnswer || {}).perDay ?? meals.length, meals };
}

/** The applied import document (Assistant page; shown in Startup 2), or {} when none was applied. */
export function importDocumentFromAnswers(answers) {
  return (answers.startup || {}).import || {};
}

/** The import document's fixed activities as anchor candidates (source "import"). */
export function importedAnchorActivities(importDocument) {
  return (importDocument.fixedActivities || []).map((activity) => ({ ...activity, source: IMPORT_ANCHOR_SOURCE }));
}

/** A grid (the person's own or an import's) restricted to this profile's focus blocks: { grid, warnings }. */
export function restrictedBlockFocusGrid(sourceGrid, focusBlockKeys, allowedFocus, dayKeyOrder, sourceName = "blockFocusGrid") {
  sourceGrid = sourceGrid || {};
  const grid = {};
  const warnings = [];
  const unmatched = [];
  for (const dayKey of dayKeyOrder) {
    if (!(dayKey in sourceGrid)) continue;
    const cells = {};
    for (const [blockKey, focus] of Object.entries(sourceGrid[dayKey])) {
      if (!focusBlockKeys.includes(blockKey)) {
        if (!unmatched.includes(blockKey)) unmatched.push(blockKey);
        continue;
      }
      if (!allowedFocus.includes(focus)) {
        warnings.push(`${sourceName}: ${dayKey}.${blockKey} has unknown focus ${pythonRepr(focus)}; dropped`);
        continue;
      }
      cells[blockKey] = focus;
    }
    grid[dayKey] = cells;
  }
  if (unmatched.length) {
    warnings.unshift(`${sourceName}: focus for ${unmatched.length === 1 ? "block" : "blocks"} ${unmatched.join(", ")} does not match this profile's blocks (${focusBlockKeys.join(", ")}); dropped`);
  }
  return { grid, warnings };
}

/** The grid the weights show: the person's own (answers.blockFocusGrid, an adopted proposal) when present, else the
 *  applied import's; either restricted to this profile's focus blocks. Returns { grid, warnings }. */
export function personBlockFocusGrid(answers, importDocument, focusBlockKeys, allowedFocus, dayKeyOrder) {
  if (answers.blockFocusGrid && Object.keys(answers.blockFocusGrid).length) {
    return restrictedBlockFocusGrid(answers.blockFocusGrid, focusBlockKeys, allowedFocus, dayKeyOrder, "blockFocusGrid (your own)");
  }
  return restrictedBlockFocusGrid(importDocument.blockFocusGrid, focusBlockKeys, allowedFocus, dayKeyOrder, "blockFocusGrid (imported)");
}

/** Python's repr() for the string/other values that show up in warnings (parity with the Python twin). */
function pythonRepr(value) {
  return typeof value === "string" ? `'${value}'` : String(value);
}

function deepCopy(value) {
  return JSON.parse(JSON.stringify(value));
}

export const DEFAULT_WEEK_START = "sunday";
export const DEFAULT_START_VARIANT = "a";

/** The baseline's seasons (bundle.seasons) as year-split sections — the 'custom' scheme's starting point.
 *  Lossless with seasonsFromYearSplit: the start rule, its words, the start half and knownStarts survive. */
export function yearSplitFromSeasons(seasons, scheme = "custom") {
  const sections = seasons.seasons.map((season) => {
    const section = {
      title: season.name,
      kind: season.seasonMode,
      gregorianEquivalent: season.gregorianRange,
      durationWeeks: { ...season.durationWeeks },
      start: { marker: "rule", description: season.startDescription, rule: deepCopy(season.startRule) },
      startVariant: season.startDayKey.split("-")[1],
    };
    if (season.knownStarts && Object.keys(season.knownStarts).length) section.knownStarts = { ...season.knownStarts };
    return section;
  });
  return { scheme, sectionLabel: "season", sections };
}

/** A preset scheme's template as a year split (the read-only presets; presets carry rules only where the marker is exact). */
export function yearSplitFromScheme(questionnaire, schemeId) {
  const scheme = questionnaire.options.yearSplitSchemes.find((candidate) => candidate.id === schemeId);
  return { scheme: schemeId, sectionLabel: scheme.sectionLabel, sections: deepCopy(scheme.template) };
}

/** A person's year split as seasons.json-shaped seasons (in-memory only; the date resolver reads
 *  startRule / startDayKey / knownStarts). Duplicate titles get -2, -3, ... suffixes. */
export function seasonsFromYearSplit(yearSplit, weekStart = DEFAULT_WEEK_START) {
  const usedIds = new Set();
  return (yearSplit.sections || []).map((section) => {
    const baseId = slugify(section.title) || "section";
    let seasonId = baseId;
    for (let suffix = 2; usedIds.has(seasonId); suffix += 1) seasonId = `${baseId}-${suffix}`;
    usedIds.add(seasonId);
    const start = section.start || {};
    return {
      id: seasonId,
      name: section.title,
      gregorianRange: section.gregorianEquivalent ?? null,
      durationWeeks: section.durationWeeks ? { ...section.durationWeeks } : null,
      startRule: start.rule ? deepCopy(start.rule) : null,
      startDescription: start.description || "",
      startDayKey: dayKeyFromWeekdayAndVariant(weekStart, section.startVariant || DEFAULT_START_VARIANT),
      seasonMode: "mixed",
      outdoorWindow: { uvAbove4: null },
      focus: [],
      menuId: null,
      knownStarts: { ...(section.knownStarts || {}) },
    };
  });
}

/** The seasons a person's answers imply (their year split + week start), for date resolution. */
export function seasonsForAnswers(answers, questionnaire, categories) {
  const defaults = defaultAnswers(questionnaire, categories);
  const weekStart = answers.weekStart ?? defaults.weekStart;
  return seasonsFromYearSplit(yearSplitWithDefaults(answers.yearSplit ?? defaults.yearSplit, weekStart), weekStart);
}

/** A copy with every section carrying start.rule (null when absent) and startVariant (default a);
 *  a rule that snaps always snaps to the person's week start (the snap weekday is never stored stale). */
function yearSplitWithDefaults(yearSplit, weekStart = DEFAULT_WEEK_START) {
  const copy = deepCopy(yearSplit);
  for (const section of copy.sections || []) {
    section.start = section.start || { marker: "manual", description: "" };
    if (section.start.rule === undefined) section.start.rule = null;
    if (!section.startVariant) section.startVariant = DEFAULT_START_VARIANT;
    if (section.start.rule && section.start.rule.snap) section.start.rule.snap.weekday = weekStart;
  }
  return copy;
}

/** Lowercase kebab-case slug, identical to fk_core.keys.slugify. */
export function slugify(text) {
  return String(text).trim().toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

/** Standing appointments as pseudo-activities so they anchor the block split like fixed activities.
 *  weekly -> every listed weekday, both fortnight day keys; every-other-week -> the variant (A/B) that
 *  `firstDate` resolves to (both + warning without a resolver); monthly-* / one-off -> pooled, no day key.
 *  Returns { activities, warnings }. */
export function standingAppointmentActivities(standingAppointments, days, resolveDayKey = null) {
  return recurringItemActivities(standingAppointments, days, resolveDayKey, { idPrefix: "standing", source: "standing-appointment", priority: 1, flexibility: "no" });
}

/** The cadence expansion behind standing appointments, shared with import-document tasks (day-plan.js):
 *  each item ({title, weekdays, cadence, start?, durationMinutes}) becomes one pseudo-activity per day key
 *  it lands on (id `<idPrefix>--<slug>--<index+1>`; timing only when it has a start). */
export function recurringItemActivities(items, days, resolveDayKey = null, { idPrefix, source, priority, flexibility }) {
  const dayKeysByWeekday = {};
  for (const dayKey of days.order) {
    const day = days.days[dayKey];
    dayKeysByWeekday[day.weekday] = dayKeysByWeekday[day.weekday] || {};
    dayKeysByWeekday[day.weekday][day.variant.toLowerCase()] = dayKey;
  }
  const activities = [];
  const warnings = [];
  items.forEach((item, index) => {
    let timing = null;
    if (item.start) {
      const startMinutes = timeStringToMinutes(item.start);
      timing = { estimatedStart: item.start, estimatedEnd: minutesToTimeString(Math.min(startMinutes + (item.durationMinutes || 0), MINUTES_PER_DAY)) };
    }
    const cadence = item.cadence;
    const kind = cadence.kind;
    const identifier = `${idPrefix}--${slugify(item.title) || "appointment"}--${index + 1}`;
    const weekdays = [...(item.weekdays || [])];
    let dayKeys = [];
    if (kind === "weekly") {
      for (const weekday of weekdays) {
        const variants = dayKeysByWeekday[weekday] || {};
        dayKeys.push(variants.a ?? null, variants.b ?? null);
      }
    } else if (kind === "every-other-week") {
      let resolvedVariant = null;
      if (resolveDayKey && cadence.firstDate) {
        const resolvedDayKey = resolveDayKey(cadence.firstDate);
        resolvedVariant = resolvedDayKey ? days.days[resolvedDayKey].variant.toLowerCase() : null;
      }
      if (resolvedVariant === null) {
        warnings.push(`${identifier}: every-other-week could not be placed on week A or B (no date resolver); counted in both weeks`);
      }
      for (const weekday of weekdays) {
        const variants = dayKeysByWeekday[weekday] || {};
        if (resolvedVariant) dayKeys.push(variants[resolvedVariant] ?? null);
        else dayKeys.push(variants.a ?? null, variants.b ?? null);
      }
    } else {
      dayKeys = Array.from({ length: Math.max(1, weekdays.length) }, () => null);
    }
    for (const dayKey of dayKeys) {
      activities.push({ id: identifier, dayKey, priority, flexibility, categories: [item.category], timing, source });
    }
  });
  return { activities, warnings };
}

export function subjectMidpointMinutes(subjectAnswer) {
  if (subjectAnswer.peripheral) return 0;
  return (subjectAnswer.minutesPerDay.min + subjectAnswer.minutesPerDay.max) / 2;
}

// ---------- waking window and block split ----------

/** The answered waking window {start, end} with its length; wraps midnight when end < start (end == start is a full day). */
export function wakingWindowFromAnswer(wakingWindow) {
  const startMinutes = timeStringToMinutes(wakingWindow.start);
  const endMinutes = timeStringToMinutes(wakingWindow.end);
  const minutesPerDay = ((endMinutes - startMinutes) % MINUTES_PER_DAY + MINUTES_PER_DAY) % MINUTES_PER_DAY || MINUTES_PER_DAY;
  return {
    start: minutesToTimeString(startMinutes),
    end: minutesToTimeString(endMinutes),
    minutesPerDay,
    minutesPerCycle: minutesPerDay * CYCLE_LENGTH_DAYS,
  };
}

/** The unscheduled block (wind-down + sleep + wake-up): the complement of the waking window. */
export function unscheduledBlockFromWindow(wakingWindow) {
  return { start: wakingWindow.end, end: wakingWindow.start, minutes: MINUTES_PER_DAY - wakingWindow.minutesPerDay };
}

/** Categories whose share stands above the mean non-peripheral share, best first, capped. */
export function standoutCategories(categoryOrder, weightsCategories, rawMinutes, blockSplit) {
  const considered = categoryOrder.filter((categoryKey) => rawMinutes[categoryKey] > 0);
  if (!considered.length) return [];
  const meanShare = considered.reduce((sum, categoryKey) => sum + weightsCategories[categoryKey].share, 0) / considered.length;
  const threshold = blockSplit.standoutMultiplier * meanShare;
  const standouts = considered.filter((categoryKey) => weightsCategories[categoryKey].share >= threshold);
  standouts.sort((left, right) => (weightsCategories[right].share - weightsCategories[left].share) || (categoryOrder.indexOf(left) - categoryOrder.indexOf(right)));
  return standouts.slice(0, blockSplit.maxFocusBlocks);
}

export function isAnchor(activity) {
  return Boolean(activity.timing) && (activity.priority === 1 || activity.flexibility === "no");  // tolerant of missing fields (imports)
}

/** Fixed activities as offsets (minutes since the waking window starts); flags out-of-scope ones. */
export function anchorOffsets(activities, wakingWindow) {
  const wakingStart = timeStringToMinutes(wakingWindow.start);
  const wakingMinutes = wakingWindow.minutesPerDay;
  const anchors = [];
  const warnings = [];
  for (const activity of activities) {
    if (!isAnchor(activity)) continue;
    const timing = activity.timing;
    const startOffset = (((timeStringToMinutes(timing.estimatedStart) - wakingStart) % MINUTES_PER_DAY) + MINUTES_PER_DAY) % MINUTES_PER_DAY;
    const duration = timeStringToMinutes(timing.estimatedEnd) - timeStringToMinutes(timing.estimatedStart);
    let endOffset = startOffset + duration;
    const anchor = { activityId: activity.id, dayKey: activity.dayKey, start: timing.estimatedStart, end: timing.estimatedEnd, categories: [...activity.categories], source: activity.source || "activity" };
    if (startOffset >= wakingMinutes) {
      warnings.push(`${activity.id} starts inside the unscheduled block (${timing.estimatedStart})`);
      anchor.block = null;
      anchors.push(anchor);
      continue;
    }
    if (endOffset > wakingMinutes) {
      warnings.push(`${activity.id} runs into the unscheduled block (ends ${timing.estimatedEnd})`);
      endOffset = wakingMinutes;
    }
    anchor.startOffset = startOffset;
    anchor.endOffset = endOffset;
    anchors.push(anchor);
  }
  return { anchors, warnings };
}

function rankingLess(left, right) {
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) return left[index] < right[index];
  }
  return false;
}

/** Even split, each cut snapped to the grid point (within the search window) with the lowest cost. */
export function chooseCuts(wakingMinutes, focusBlockCount, anchors, blockSplit) {
  const grid = blockSplit.cutGridMinutes;
  const search = blockSplit.cutSearchMinutes;
  const straddlePenalty = blockSplit.straddlePenalty ?? 0;
  const edgeBonus = blockSplit.edgeBonus ?? 0;
  const inScope = anchors.filter((anchor) => anchor.startOffset !== undefined);
  const cuts = [];
  let previous = 0;
  for (let cutIndex = 1; cutIndex < focusBlockCount; cutIndex += 1) {
    const ideal = (wakingMinutes * cutIndex) / focusBlockCount;
    let best = null;
    const lowest = Math.floor((ideal - search) / grid) * grid;
    const highest = Math.ceil((ideal + search) / grid) * grid;
    for (let candidate = lowest; candidate <= highest; candidate += grid) {
      if (candidate <= previous || candidate >= wakingMinutes || Math.abs(candidate - ideal) > search) continue;
      const straddles = inScope.filter((anchor) => anchor.startOffset < candidate && candidate < anchor.endOffset).length;
      const edges = inScope.filter((anchor) => candidate === anchor.startOffset || candidate === anchor.endOffset).length;
      const cost = Math.abs(candidate - ideal) / grid + straddlePenalty * straddles - edgeBonus * edges;
      const ranking = [cost, Math.abs(candidate - ideal), candidate];
      if (best === null || rankingLess(ranking, best.ranking)) best = { ranking, candidate };
    }
    const chosen = best ? best.candidate : roundHalfUp(ideal);
    cuts.push(chosen);
    previous = chosen;
  }
  return cuts;
}

export function blocksFromCuts(wakingWindow, unscheduledBlock, cuts, focusBlockKeys) {
  const wakingStart = timeStringToMinutes(wakingWindow.start);
  const boundaries = [0, ...cuts, wakingWindow.minutesPerDay];
  const blocks = [{ key: UNSCHEDULED_BLOCK_KEY, start: unscheduledBlock.start, end: wakingWindow.start, durationMinutes: unscheduledBlock.minutes, carriesFocus: false }];
  focusBlockKeys.forEach((key, index) => {
    const startOffset = boundaries[index];
    const endOffset = boundaries[index + 1];
    blocks.push({
      key,
      start: minutesToTimeString((wakingStart + startOffset) % MINUTES_PER_DAY),
      end: minutesToTimeString((wakingStart + endOffset) % MINUTES_PER_DAY),
      durationMinutes: endOffset - startOffset,
      carriesFocus: true,
    });
  });
  return blocks;
}

function assignAnchorBlocks(anchors, cuts, focusBlockKeys, wakingMinutes) {
  const boundaries = [0, ...cuts, wakingMinutes];
  for (const anchor of anchors) {
    if (anchor.startOffset === undefined) continue;
    anchor.block = focusBlockKeys[focusBlockKeys.length - 1];
    for (let index = 0; index < focusBlockKeys.length; index += 1) {
      if (boundaries[index] <= anchor.startOffset && anchor.startOffset < boundaries[index + 1]) {
        anchor.block = focusBlockKeys[index];
        break;
      }
    }
  }
}

/** Blocks ordered by how many anchors of the category start there (ties keep block order). */
export function preferredBlocksFromAnchors(categoryOrder, anchors, focusBlockKeys) {
  const votes = {};
  for (const categoryKey of categoryOrder) votes[categoryKey] = Object.fromEntries(focusBlockKeys.map((blockKey) => [blockKey, 0]));
  for (const anchor of anchors) {
    if (anchor.block === null || anchor.block === undefined) continue;
    for (const categoryKey of anchor.categories) {
      if (votes[categoryKey]) votes[categoryKey][anchor.block] += 1;
    }
  }
  const preferred = {};
  for (const [categoryKey, blockVotes] of Object.entries(votes)) {
    const ranked = Object.entries(blockVotes).sort((left, right) => (right[1] - left[1]) || (focusBlockKeys.indexOf(left[0]) - focusBlockKeys.indexOf(right[0])));
    preferred[categoryKey] = ranked.filter(([, count]) => count > 0).map(([blockKey]) => blockKey);
  }
  return preferred;
}

/** Waking window + block split for a profile. `agendaScope` defaults to "categories" (Focus 6's default),
 *  which adds one focus block beyond the standouts — pass "subjects" for the standouts-only day. */
export function splitBlocks(categoryOrder, weightsCategories, rawMinutes, wakingWindowAnswer, activities, questionnaire, agendaScope = DEFAULT_AGENDA_SCOPE) {
  const blockSplit = questionnaire.blockSplit;
  const wakingWindow = wakingWindowFromAnswer(wakingWindowAnswer);
  const unscheduled = unscheduledBlockFromWindow(wakingWindow);
  const standouts = standoutCategories(categoryOrder, weightsCategories, rawMinutes, blockSplit);
  let focusBlockCount = Math.max(1, standouts.length);
  if (agendaScope === "categories") focusBlockCount = Math.min(blockSplit.maxFocusBlocks, focusBlockCount + 1);
  const focusBlockKeys = [...blockSplit.focusBlockKeys[String(focusBlockCount)]];
  const { anchors, warnings } = anchorOffsets(activities, wakingWindow);
  const cuts = chooseCuts(wakingWindow.minutesPerDay, focusBlockCount, anchors, blockSplit);
  assignAnchorBlocks(anchors, cuts, focusBlockKeys, wakingWindow.minutesPerDay);
  const blocks = blocksFromCuts(wakingWindow, unscheduled, cuts, focusBlockKeys);
  const anchorRecords = anchors.map(({ activityId, dayKey, start, end, categories, block, source }) => ({ activityId, dayKey, start, end, categories, block, source }));
  const split = {
    standoutCategories: [...standouts].sort((left, right) => categoryOrder.indexOf(left) - categoryOrder.indexOf(right)),
    focusBlockCount,
    agendaScope,
    anchors: anchorRecords,
    warnings,
  };
  return { wakingWindow, unscheduled, blocks, split, preferredBlocks: preferredBlocksFromAnchors(categoryOrder, anchors, focusBlockKeys) };
}

// ---------- the whole rule ----------

/** Turn a questionnaire answers object into a weights object (weights.schema.json). */
export function weightsFromAnswers(answers, categories, questionnaire, { weightsId, answeredAt = null, activities = [], days = null, resolveDayKey = null, seasonFocus = null, seasonId = null } = {}) {
  const categoryOrder = categories.order;
  const defaults = defaultAnswers(questionnaire, categories);
  const subjectTime = { ...defaults.subjectTime, ...(answers.subjectTime || {}) };
  // A category "wants more" when any of its subjects is a goal (Focus Q2 was folded into the goal toggle).
  const wantMore = new Set(categoryOrder.filter((categoryKey) =>
    categories.categories[categoryKey].subjects.some((subjectId) => subjectTime[subjectId].goal)));
  const sentiment = answers.sentiment || {};
  const delegable = new Set(answers.delegable || []);
  const essential = new Set(answers.essential || []);
  const wakingWindowAnswer = { ...defaults.wakingWindow, ...(answers.wakingWindow || {}) };
  const multiplier = questionnaire.wantMoreMultiplier;
  const standingAppointments = deepCopy(answers.standingAppointments ?? defaults.standingAppointments);
  const standing = days ? standingAppointmentActivities(standingAppointments, days, resolveDayKey) : { activities: [], warnings: [] };
  const agendaScope = answers.agendaScope ?? defaults.agendaScope;
  const importDocument = importDocumentFromAnswers(answers);
  const allActivities = [...activities, ...importedAnchorActivities(importDocument), ...standing.activities];

  const rawMinutes = {};
  for (const categoryKey of categoryOrder) {
    const subjectIds = categories.categories[categoryKey].subjects;
    const total = subjectIds.reduce((sum, subjectId) => sum + subjectMidpointMinutes(subjectTime[subjectId]), 0);
    rawMinutes[categoryKey] = total * (wantMore.has(categoryKey) ? multiplier : 1);
  }
  const grandTotal = Object.values(rawMinutes).reduce((sum, value) => sum + value, 0);

  const weightsCategories = {};
  for (const categoryKey of categoryOrder) {
    const share = grandTotal ? roundHalfUp(rawMinutes[categoryKey] / grandTotal, SHARE_DECIMALS) : 0;
    weightsCategories[categoryKey] = {
      share,
      wantMore: wantMore.has(categoryKey),
      sentiment: sentiment[categoryKey] || "neutral",
      delegable: delegable.has(categoryKey),
      essential: essential.has(categoryKey),
    };
  }
  const { wakingWindow, unscheduled, blocks, split, preferredBlocks } = splitBlocks(categoryOrder, weightsCategories, rawMinutes, wakingWindowAnswer, allActivities, questionnaire, agendaScope);
  const focusBlockKeys = blocks.filter((block) => block.carriesFocus).map((block) => block.key);
  const { grid: blockFocusGrid, warnings: gridWarnings } = personBlockFocusGrid(answers, importDocument, focusBlockKeys, [...categoryOrder, FLEXIBLE_FOCUS], DAY_KEY_ORDER);
  split.warnings = [...standing.warnings, ...split.warnings, ...gridWarnings];
  for (const categoryKey of categoryOrder) {
    const category = weightsCategories[categoryKey];
    weightsCategories[categoryKey] = {
      share: category.share,
      minutesPerCycle: roundHalfUp(category.share * wakingWindow.minutesPerCycle),
      preferredBlocks: preferredBlocks[categoryKey],
      wantMore: category.wantMore,
      sentiment: category.sentiment,
      delegable: category.delegable,
      essential: category.essential,
    };
  }
  const weightsSubjects = {};
  for (const subjectId of Object.keys(categories.subjects)) {
    const subjectAnswer = subjectTime[subjectId];
    const goal = Boolean(subjectAnswer.goal);
    weightsSubjects[subjectId] = {
      minutesPerDay: { ...subjectAnswer.minutesPerDay },
      peripheral: Boolean(subjectAnswer.peripheral),
      goal,
      currentMinutesPerDay: goal ? (subjectAnswer.currentMinutesPerDay ?? null) : null,
    };
  }
  const questionnaireRecord = answeredAt
    ? { version: questionnaire.schemaVersion, answeredAt, answers }
    : { version: questionnaire.schemaVersion, answers };
  const weights = {
    $schema: "./schema/weights.schema.json",
    schemaVersion: 1,
    id: weightsId,
    source: "questionnaire",
    cycleLengthDays: CYCLE_LENGTH_DAYS,
    wakingWindow,
    categories: weightsCategories,
    subjects: weightsSubjects,
    // Not an input: the questionnaire assigns the whole waking window. This is the rounding remainder
    // (1 when every subject is peripheral) so category shares + flexibleShare still sum to 1.
    flexibleShare: Math.max(0, roundHalfUp(1 - Object.values(weightsCategories).reduce((sum, category) => sum + category.share, 0), SHARE_DECIMALS)),
    unscheduledBlock: unscheduled,
    blocks,
    blockSplit: split,
    blockFocusGrid,
    appointmentBlocks: deepCopy(importDocument.appointmentBlocks || {}),
    agendaScope,
    meals: mealsWithDefaults(answers.meals ?? defaults.meals, questionnaire),
    mealPlan: deepCopy(answers.mealPlan || { items: [] }),
    yearSplit: yearSplitWithDefaults(answers.yearSplit ?? defaults.yearSplit, answers.weekStart ?? defaults.weekStart),
    weekStart: answers.weekStart ?? defaults.weekStart,
    standingAppointments,
    tasks: deepCopy(answers.tasks ?? defaults.tasks),
    appointmentWeekdays: [...(answers.appointmentWeekdays ?? defaults.appointmentWeekdays)],
    practices: [...(answers.practices ?? defaults.practices)],
    restDays: [...(answers.restDays ?? defaults.restDays)],
    energyPeak: answers.energyPeak ?? defaults.energyPeak,
    context: answers.context ?? defaults.context,
    questionnaire: questionnaireRecord,
    notes: ["Derived from questionnaire answers by the rule in fk_core/weights.py / app/shared/weights-rules.js."],
  };
  weights.proposal = proposalFromWeights(weights, questionnaire, { seasonFocus, seasonId, categories, dayKeyOrder: DAY_KEY_ORDER });
  return weights;
}

/** Lowercase kebab-case id from a free-text name (weights ids are immutable once published). */
export function slugifyId(text) {
  return String(text).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "username";
}

// ----- answer checks shared by the questionnaire pages and the assistant pages (mirror fk_core.validate) -----

/** Cadence kind -> the extra field it needs (null when none); mirror of fk_core.validate.check_standing_appointment. */
export const CADENCE_REQUIRED_FIELD = { weekly: null, "every-other-week": "firstDate", "monthly-nth-weekday": "nth", "monthly-date": "dayOfMonth", "one-off": "date" };

/** Returns a problem string or null. `categoryKeys` = categories.order, `weekdayIds` = questionnaire.options.weekdays ids. */
export function standingAppointmentProblem(appointment, categoryKeys, weekdayIds) {
  const kinds = Object.keys(CADENCE_REQUIRED_FIELD);
  if (!appointment || typeof appointment.title !== "string" || !Array.isArray(appointment.weekdays) || !appointment.cadence) return "not an appointment";
  if (!kinds.includes(appointment.cadence.kind)) return `unknown cadence ${appointment.cadence.kind}`;
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(appointment.start || "")) return "needs a start time";
  if (!Number.isInteger(appointment.durationMinutes) || appointment.durationMinutes < 0) return "needs a duration";
  if (!categoryKeys.includes(appointment.category)) return `unknown category ${appointment.category}`;
  if (appointment.weekdays.some((weekday) => !weekdayIds.includes(weekday))) return "unknown weekday";
  const requiredField = CADENCE_REQUIRED_FIELD[appointment.cadence.kind];
  if (requiredField && (appointment.cadence[requiredField] === undefined || appointment.cadence[requiredField] === null || appointment.cadence[requiredField] === "")) return `${appointment.cadence.kind} needs ${requiredField}`;
  if (["weekly", "every-other-week", "monthly-nth-weekday"].includes(appointment.cadence.kind) && appointment.weekdays.length === 0) return `${appointment.cadence.kind} needs at least one weekday`;
  if (appointment.cadence.kind === "monthly-nth-weekday" && appointment.cadence.nth === 0) return "nth must be 1–4 or -1 (last)";
  return null;
}

/** A hand-typed task (Startup 2): the appointment rules minus the start time, plus a known time-of-day word. */
export function taskProblem(task, categoryKeys, weekdayIds) {
  if (!task || typeof task !== "object") return "not a task";
  const timeOfDay = task.timeOfDay ?? null;
  if (timeOfDay !== null && !TIME_OF_DAY_WORDS.includes(timeOfDay)) return `unknown time of day ${JSON.stringify(timeOfDay)}`;
  if (task.start !== undefined && task.start !== null && !/^([01]\d|2[0-3]):[0-5]\d$/.test(task.start)) return "start must be HH:MM";
  return standingAppointmentProblem({ ...task, start: task.start ?? "00:00" }, categoryKeys, weekdayIds);
}

/** Deduplication key for standing appointments: title + start + weekdays (tasks: title + time of day + weekdays). */
export function appointmentSignature(appointment) {
  return `${appointment.title}|${appointment.start ?? appointment.timeOfDay ?? ""}|${[...(appointment.weekdays || [])].sort().join(",")}`;
}

/** Merge a list of canonical records into an existing list, deduplicated on appointmentSignature; each record
 *  is checked with `problemOf` first. Returns { items, added, rejected }; the input list is not mutated. */
function mergeRecords(existing, incoming, problemOf, label) {
  const items = [...existing];
  const seen = new Set(items.map(appointmentSignature));
  let added = 0;
  const rejected = [];
  incoming.forEach((record, index) => {
    const problem = problemOf(record);
    if (problem) { rejected.push(`${label} #${index + 1} ${record?.title || ""}: ${problem}`); return; }
    const signature = appointmentSignature(record);
    if (seen.has(signature)) return;
    items.push(deepCopy(record));
    seen.add(signature);
    added += 1;
  });
  return { items, added, rejected };
}

/** Merge an import document's commitments and tasks into the person's lists (docs/importers.md). Version-2
 *  documents are normalized first (readable `commitments`/`tasks` -> canonical records; `categories` is the
 *  bundle's categories.json for label lookup). Returns { appointments, added, listed, tasks, tasksAdded,
 *  tasksListed, rejected: [reason], applied: ["64 fixed activities", "block focus for 14 days"], ignored: ["3 meals"],
 *  skipped: <the assistant's own skipped list length> }; the input lists are not mutated. */
export function mergeImportedAppointments(existingAppointments, importDocument, categoryKeys, weekdayIds, categories = null, existingTasks = []) {
  const normalized = normalizeImportDocument(importDocument, categories);
  const merged = mergeRecords(existingAppointments, normalized.document.standingAppointments || [], (record) => standingAppointmentProblem(record, categoryKeys, weekdayIds), "commitments");
  const mergedTasks = mergeRecords(existingTasks, normalized.document.tasks || [], (record) => taskProblem(record, categoryKeys, weekdayIds), "tasks");
  const rejected = [...normalized.problems, ...merged.rejected, ...mergedTasks.rejected];
  const applied = [];
  const fixedCount = (importDocument.fixedActivities || []).length;
  if (fixedCount) applied.push(`${fixedCount} fixed activit${fixedCount === 1 ? "y" : "ies"}`);
  const gridDays = Object.keys(importDocument.blockFocusGrid || {}).length;
  if (gridDays) applied.push(`block focus for ${gridDays} day${gridDays === 1 ? "" : "s"}`);
  const ignored = ["meals"].filter((key) => (importDocument[key] || []).length).map((key) => `${importDocument[key].length} ${key}`);
  return {
    appointments: merged.items, added: merged.added, listed: (normalized.document.standingAppointments || []).length,
    tasks: mergedTasks.items, tasksAdded: mergedTasks.added, tasksListed: (normalized.document.tasks || []).length,
    rejected, applied, ignored, skipped: (importDocument.skipped || []).length,
  };
}

/** Apply an import document to an answers object (Assistant page, *Apply from assistant*): merges its standing
 *  appointments and tasks (version 2: its readable commitments and tasks) and records the document itself — as pasted, never
 *  the normalized copy — as `startup.import` (raw text stays in `startup.importJson`); readers normalize
 *  again (`normalizeImportDocument`). Mutates `answers`; returns the merge summary. */
export function applyImportDocument(answers, importDocument, categoryKeys, weekdayIds, rawText = null, categories = null, questionnaire = null) {
  const merged = mergeImportedAppointments(answers.standingAppointments || [], importDocument, categoryKeys, weekdayIds, categories, answers.tasks || []);
  answers.standingAppointments = merged.appointments;
  answers.tasks = merged.tasks;
  // The ForkKnife tasks document carries the menu too: merged into the profile's meal plan (docs/meal-plan.md).
  merged.mealPlanApplied = 0;
  merged.mealPlanProblems = [];
  if (importDocument.mealPlan && questionnaire) {
    const meals = mealsWithDefaults(answers.meals ?? defaultAnswers(questionnaire, categories).meals, questionnaire).meals;
    const { normalized, problems } = normalizeMealPlan(importDocument.mealPlan, meals);
    answers.mealPlan = { items: mergeMealPlan(answers.mealPlan?.items || [], normalized.items) };
    merged.mealPlanApplied = normalized.items.length;
    merged.mealPlanProblems = problems;
  }
  answers.startup = { ...(answers.startup || { groupSize: 1 }), importJson: rawText ?? JSON.stringify(importDocument), import: deepCopy(importDocument) };
  return merged;
}

/** The waking window answer must be two HH:MM times whose span (wrapping midnight) is within the questionnaire's bounds. */
export function wakingWindowProblem(wakingWindow, questionnaire) {
  if (wakingWindow === undefined) return null; // the default applies
  const bounds = questionnaire.wakingWindow.minutes;
  const isTime = (value) => typeof value === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(value);
  if (!wakingWindow || !isTime(wakingWindow.start) || !isTime(wakingWindow.end)) return "The waking window needs a start and an end time (HH:MM).";
  const minutesPerDay = wakingWindowFromAnswer(wakingWindow).minutesPerDay;
  if (minutesPerDay < bounds.min || minutesPerDay > bounds.max) {
    return `The waking window must be ${bounds.min / 60}–${bounds.max / 60} hours (${formatClockTime(wakingWindow.start)} – ${formatClockTime(wakingWindow.end)} is ${Math.round(minutesPerDay / 6) / 10}).`;
  }
  return null;
}

/** The person's own grid (an adopted proposal), when present, must be {dayKey: {blockKey: focus}} over known day keys and focus values. */
export function blockFocusGridProblem(grid, categoryOrder) {
  if (grid === undefined || grid === null) return null;
  if (typeof grid !== "object" || Array.isArray(grid)) return "Your block focus grid must be an object keyed by day key.";
  const allowedFocus = [...categoryOrder, FLEXIBLE_FOCUS];
  for (const [dayKey, cells] of Object.entries(grid)) {
    if (!DAY_KEY_ORDER.includes(dayKey)) return `Your block focus grid names an unknown day key (${dayKey}).`;
    if (typeof cells !== "object" || cells === null || Array.isArray(cells)) return `Your block focus grid's ${dayKey} must map block keys to a focus.`;
    for (const [blockKey, focus] of Object.entries(cells)) {
      if (!allowedFocus.includes(focus)) return `Your block focus grid's ${dayKey}.${blockKey} has an unknown focus (${focus}).`;
    }
  }
  return null;
}

/** Meal names must be given and distinct once slugified (they key the meal plan's items). */
export function mealNamesProblem(meals) {
  const seen = new Set();
  for (const [index, meal] of meals.entries()) {
    const slug = mealSlug(meal.name ?? "");
    if (!slug) return `Meal ${index + 1}: give it a name.`;
    if (seen.has(slug)) return `Meal ${index + 1}: the name ${meal.name} is already used by another meal.`;
    seen.add(slug);
  }
  return null;
}

/** Whole-answers check before deriving weights: returns a problem string or null. */
export function answersProblem(answers, questionnaire, categories) {
  const essentialBounds = questionnaire.essentialCategories || { min: 1, max: 3 };
  const essential = answers.essential || [];
  if (essential.length < essentialBounds.min || essential.length > essentialBounds.max) {
    return `Mark ${essentialBounds.min}–${essentialBounds.max} categories you have to do personally (${essential.length} marked).`;
  }
  const weekdayIds = questionnaire.options.weekdays.map((weekday) => weekday.id);
  for (const [index, appointment] of (answers.standingAppointments || []).entries()) {
    const problem = standingAppointmentProblem(appointment, categories.order, weekdayIds);
    if (problem) return `Commitment ${index + 1} (${appointment?.title ?? ""}): ${problem}.`;
  }
  for (const [index, task] of (answers.tasks || []).entries()) {
    const problem = taskProblem(task, categories.order, weekdayIds);
    if (problem) return `Task ${index + 1} (${task?.title ?? ""}): ${problem}.`;
  }
  const wakingProblem = wakingWindowProblem(answers.wakingWindow, questionnaire);
  if (wakingProblem) return wakingProblem;
  const gridProblem = blockFocusGridProblem(answers.blockFocusGrid, categories.order);
  if (gridProblem) return gridProblem;
  const yearBounds = questionnaire.yearSections;
  const sectionCount = answers.yearSplit?.sections?.length ?? 0;
  if (sectionCount < yearBounds.min || sectionCount > yearBounds.max) {
    return `Split your year into ${yearBounds.min}–${yearBounds.max} sections (${sectionCount} now).`;
  }
  for (const [index, section] of (answers.yearSplit?.sections || []).entries()) {
    const problem = startRuleProblem(section.start?.rule) || knownStartsProblem(section.knownStarts, section.start?.rule);
    if (problem) return `Section ${index + 1} (${section.title ?? ""}): ${problem}.`;
    if (section.startVariant && !["a", "b"].includes(section.startVariant)) return `Section ${index + 1} (${section.title ?? ""}): start half must be A or B.`;
  }
  if (answers.weekStart !== undefined && !weekdayIds.includes(answers.weekStart)) {
    return `Week start must be one of ${weekdayIds.join(", ")} (got ${JSON.stringify(answers.weekStart)}).`;
  }
  const agendaScopes = questionnaire.options.agendaScopes.map((scope) => scope.id);
  if (answers.agendaScope !== undefined && !agendaScopes.includes(answers.agendaScope)) {
    return `Agenda scope must be one of ${agendaScopes.join(", ")} (got ${JSON.stringify(answers.agendaScope)}).`;
  }
  const energyPeaks = questionnaire.options.energyPeaks.map((peak) => peak.id);
  if (answers.energyPeak !== undefined && !energyPeaks.includes(answers.energyPeak)) {
    return `Energy peak must be one of ${energyPeaks.join(", ")} (got ${JSON.stringify(answers.energyPeak)}).`;
  }
  const badRestDay = (answers.restDays || []).find((weekday) => !weekdayIds.includes(weekday));
  if (badRestDay !== undefined) return `Rest days must be weekdays (got ${JSON.stringify(badRestDay)}).`;
  if (answers.context !== undefined && typeof answers.context !== "string") return "Context must be text.";
  const preferencesProblem = mealPreferencesProblem(answers, questionnaire);
  if (preferencesProblem) return preferencesProblem;
  const slotBounds = questionnaire.slotsPerMeal;
  const badMeal = (answers.meals?.meals || []).findIndex((meal) => meal.slots.length < slotBounds.min || meal.slots.length > slotBounds.max);
  if (badMeal >= 0) return `Meal ${badMeal + 1}: pick ${slotBounds.min}–${slotBounds.max} times of day.`;
  // Meals are checked with their defaults filled (a profile saved before meals had names passes as "Meal n").
  const filledMeals = mealsWithDefaults(answers.meals ?? defaultAnswers(questionnaire, categories).meals, questionnaire).meals;
  const mealsProblem = mealNamesProblem(filledMeals);
  if (mealsProblem) return mealsProblem;
  const planProblem = mealPlanProblem(answers.mealPlan, filledMeals);
  if (planProblem) return `Meal plan: ${planProblem} — fix it on ForkKnife's Questionnaire.`;
  return null;
}

/** A structured start rule has the fields its kind needs, in range (mirror of fk_core.validate.check_start_rule). */
export function startRuleProblem(rule) {
  if (rule === null || rule === undefined) return null;
  if (!START_RULE_KINDS.includes(rule.kind)) return `unknown start rule kind ${JSON.stringify(rule.kind)}`;
  const needs = { "fixed-date": ["month", "day"], "nth-weekday": ["month", "weekday", "occurrence"], solar: ["term"], "new-moon": ["index"] }[rule.kind] || [];
  for (const field of needs) if (rule[field] === undefined || rule[field] === null || rule[field] === "") return `${rule.kind} rule needs ${field}`;
  if (rule.month !== undefined && !(rule.month >= 1 && rule.month <= 12)) return `month ${rule.month} out of range`;
  if (rule.day !== undefined && !(rule.day >= 1 && rule.day <= 31)) return `day ${rule.day} out of range`;
  if (rule.weekday !== undefined && !WEEKDAY_NAMES.includes(rule.weekday)) return `unknown weekday ${JSON.stringify(rule.weekday)}`;
  if (rule.occurrence !== undefined && !NTH_OCCURRENCES.includes(rule.occurrence)) return `occurrence ${rule.occurrence} is not one of ${NTH_OCCURRENCES.join(", ")}`;
  if (rule.term !== undefined && !SOLAR_TERM_ORDER.includes(rule.term)) return `unknown solar term ${JSON.stringify(rule.term)}`;
  if (rule.index !== undefined && !(rule.index >= 1 && rule.index <= NEW_MOON_MAX_INDEX)) return `new-moon index ${rule.index} out of range 1–${NEW_MOON_MAX_INDEX}`;
  if (rule.snap && (!WEEKDAY_NAMES.includes(rule.snap.weekday) || !SNAP_DIRECTIONS.includes(rule.snap.direction))) return "snap needs a weekday and a direction";
  return null;
}

/** knownStarts entries are ISO dates of their year (mirror of fk_core.validate.check_known_starts, minus the computed-date check). */
export function knownStartsProblem(knownStarts, rule) {
  for (const [yearText, isoDate] of Object.entries(knownStarts || {})) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(isoDate))) return `known start ${JSON.stringify(isoDate)} is not a date`;
    if (!isoDate.startsWith(`${yearText}-`)) return `known start ${isoDate} is not in ${yearText}`;
  }
  return null;
}

/** Shape check before deriving: answers must at least carry a subjectTime object (a stringy or empty
 *  "answers" from an assistant must fail with a message, not a TypeError). */
export function isAnswersObject(answers) {
  return typeof answers === "object" && answers !== null && !Array.isArray(answers)
    && typeof answers.subjectTime === "object" && answers.subjectTime !== null;
}

/** App convenience (no Python twin): the day-key resolver a person's answers imply — their own seasons first
 *  (year split + week start), the workbook's when none of theirs has started; an epoch override wins over both. */
export function personDayKeyResolver(answers, bundle, epochOverride = null) {
  const personSeasons = seasonsForAnswers(answers, bundle.questionnaire, bundle.categories);
  return (isoDate) => {
    const date = parseIsoDate(isoDate);
    if (epochOverride) return resolveDate(bundle, date, epochOverride, personSeasons).dayKey;
    return dayKeyForDatePersonFirst(date, personSeasons, bundle.seasons.seasons);
  };
}

/** The default (and first) profile id of a device's settings. */
export const DEFAULT_WEIGHTS_ID = "username";

/** App convenience (no Python twin): the active profile's weights of a device's settings (docs/app.md
 *  "User settings": `weightsProfiles` keyed by weights id + `activeWeightsId`), or null when that
 *  profile has not been saved yet. Lives here, not in user-settings.js, so workspace-docs.js can read
 *  it without an import cycle. */
export function activeWeights(settings) {
  const profiles = settings?.weightsProfiles;
  if (!profiles || typeof profiles !== "object") return null;
  return profiles[settings.activeWeightsId] || null;
}

/** App convenience (no Python twin): what a device's saved settings say about the calendar —
 *  {weekStart, seasons} with the person's seasons (null when nothing is saved). */
export function personCalendarFromSettings(settings, bundle) {
  const answers = activeWeights(settings)?.questionnaire?.answers;
  if (!answers || !bundle) return { weekStart: DEFAULT_WEEK_START, seasons: null };
  const weekStart = WEEKDAY_NAMES.includes(answers.weekStart) ? answers.weekStart : DEFAULT_WEEK_START;
  return { weekStart, seasons: seasonsForAnswers(answers, bundle.questionnaire, bundle.categories) };
}

/** App convenience (no Python twin): the device's weights from answers + the built bundle, resolving
 *  every-other-week appointments by the person's own seasons (cycle anchor override wins). Throws with a
 *  readable message when answers are unusable. */
export function userWeightsFromAnswers(answers, bundle, { weightsId, epochOverride = null, answeredAt = null, date = null }) {
  if (!isAnswersObject(answers)) throw new Error("answers must be an object with subjectTime (see questionnaire.md → Answers file)");
  const problem = answersProblem(answers, bundle.questionnaire, bundle.categories);
  if (problem) throw new Error(problem);
  const season = currentSeasonForAnswers(answers, bundle, date, epochOverride);
  return weightsFromAnswers(answers, bundle.categories, bundle.questionnaire, {
    weightsId,
    answeredAt,
    days: bundle.days,
    resolveDayKey: personDayKeyResolver(answers, bundle, epochOverride),
    seasonFocus: season?.focus ?? null,
    seasonId: season?.id ?? null,
  });
}

/** App convenience (no Python twin): the season `date` (ISO; default today, local time) falls in by the person's
 *  own seasons first, the workbook's otherwise — what the generator's proposal is made for. */
export function currentSeasonForAnswers(answers, bundle, date = null, epochOverride = null) {
  const personSeasons = seasonsForAnswers(answers, bundle.questionnaire, bundle.categories);
  const resolved = resolveDate(bundle, parseIsoDate(date || localTodayIsoDate()), epochOverride, personSeasons);
  return resolved.season;
}
