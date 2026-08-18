// Weights -> a proposed blockFocusGrid. Pure port of scripts/fk_core/generator.py — keep both in sync;
// tests/test_generator.py runs both on the same fixtures and asserts identical output. The rule is written
// out in the Python module's docstring and in docs/generator.md; tunables live in questionnaire.generator.
import { DAY_KEY_ORDER, FLEXIBLE_FOCUS, WEEKDAY_NAMES, subjectDailyMinutes } from "./fortknight-rules.js";
import { MINUTES_PER_DAY, blockKeyForTime, minutesToTimeString, timeStringToMinutes } from "./clock.js";
import { dayLabel, menuForDay } from "./meal-plan.js";

export const REST_DAY_REASON = "rest day";
export const OVER_SHARE_REASON = "over share";
export const PROPOSED_SOURCE = "proposed";
const SPIRITUALITY_CATEGORY = "spirituality-development";
export const DEFAULT_GENERATOR = {
  anchorPinCoverage: 0.5,
  overshootSlackCells: 0.5,
  preferredBlockWeight: 0.2,
  energyPeakWeight: 0.15,
  seasonFocusWeight: 0.1,
  alternationWeight: 0.1,
  energyPeakBlock: { morning: "first", midday: "middle", evening: "last", varies: null },
  sessionGridMinutes: 5,
  maxSessionMinutes: 120,
  practiceMinutes: 15,
  mealMinutes: 30,
  mealSlotTimes: { "early-morning": "07:00", "mid-morning": "10:00", afternoon: "13:00", evening: "18:00", "late-evening": "21:00", anytime: null },
};

function roundHalfUp(value) {
  return Math.floor(value + 0.5);
}

/** The `generator` tunables of a questionnaire file, defaults filled in. */
export function generatorSettings(questionnaire) {
  return { ...DEFAULT_GENERATOR, ...((questionnaire || {}).generator || {}) };
}

/** The profile's focus blocks in order; a thin weights file without `blocks` (the baseline) falls back to a
 *  data set's blocks.json (`fallbackBlocks`). */
export function focusBlocksOf(weights, fallbackBlocks = null) {
  const blocks = (weights.blocks || []).filter((block) => block.carriesFocus);
  if (blocks.length || !fallbackBlocks) return blocks.map((block) => ({ ...block }));
  return fallbackBlocks.order
    .filter((key) => fallbackBlocks.blocks[key].carriesFocus)
    .map((key) => {
      const block = fallbackBlocks.blocks[key];
      return { key, start: block.start, end: block.end, durationMinutes: block.durationMinutes, carriesFocus: block.carriesFocus };
    });
}

/** sun-a <-> sun-b: the same weekday in the other week. */
export function otherVariantDayKey(dayKey) {
  const [weekday, variant] = dayKey.split("-");
  return `${weekday}-${variant === "a" ? "b" : "a"}`;
}

export function weekdayOfDayKey(dayKey) {
  const short = dayKey.split("-")[0];
  return WEEKDAY_NAMES.find((name) => name.startsWith(short));
}

/** Which focus block (index) carries the demanding focus for this energy peak, or null. */
export function peakBlockIndex(energyPeak, focusBlockCount, settings) {
  const position = settings.energyPeakBlock[energyPeak];
  if (position === null || position === undefined || focusBlockCount === 0) return null;
  return { first: 0, middle: Math.floor((focusBlockCount - 1) / 2), last: focusBlockCount - 1 }[position];
}

const positiveModulo = (value, modulus) => ((value % modulus) + modulus) % modulus;

/** Minutes each category's anchors overlap `block` on `dayKey` (offsets from the waking window's start, so
 *  blocks and anchors that wrap midnight measure the same way). */
export function anchorCoverageByCategory(anchors, dayKey, block, wakingStartMinutes, categoryOrder) {
  const blockStart = positiveModulo(timeStringToMinutes(block.start) - wakingStartMinutes, MINUTES_PER_DAY);
  const blockEnd = blockStart + block.durationMinutes;
  const coverage = {};
  for (const anchor of anchors) {
    if (anchor.dayKey !== dayKey || anchor.block === null || anchor.block === undefined) continue;
    const start = positiveModulo(timeStringToMinutes(anchor.start) - wakingStartMinutes, MINUTES_PER_DAY);
    const end = start + positiveModulo(timeStringToMinutes(anchor.end) - timeStringToMinutes(anchor.start), MINUTES_PER_DAY);
    const overlap = Math.min(end, blockEnd) - Math.max(start, blockStart);
    if (overlap <= 0) continue;
    for (const categoryKey of anchor.categories || []) {
      if (!categoryOrder.includes(categoryKey)) continue;
      coverage[categoryKey] ??= { minutes: 0, activityIds: [] };
      coverage[categoryKey].minutes += overlap;
      if (!coverage[categoryKey].activityIds.includes(anchor.activityId)) coverage[categoryKey].activityIds.push(anchor.activityId);
    }
  }
  return coverage;
}

/** A proposed blockFocusGrid for a weights object: { blockFocusGrid, reasons, warnings }. */
export function generateBlockFocusGrid(weights, questionnaire, { seasonFocus = null, categoryOrder, dayKeyOrder = DAY_KEY_ORDER, fallbackBlocks = null } = {}) {
  const settings = generatorSettings(questionnaire);
  const focusBlocks = focusBlocksOf(weights, fallbackBlocks);
  const candidates = [...categoryOrder, FLEXIBLE_FOCUS];
  const warnings = [];
  for (const focus of seasonFocus || []) {
    if (!categoryOrder.includes(focus)) warnings.push(`seasonFocus: unknown category '${focus}'; ignored`);
  }
  const season = (seasonFocus || []).filter((focus) => categoryOrder.includes(focus));

  const totalMinutes = focusBlocks.reduce((sum, block) => sum + block.durationMinutes, 0) * dayKeyOrder.length;
  const categories = weights.categories || {};
  const target = Object.fromEntries(categoryOrder.map((categoryKey) => [categoryKey, (categories[categoryKey]?.share ?? 0) * totalMinutes]));
  target[FLEXIBLE_FOCUS] = (weights.flexibleShare ?? 0) * totalMinutes;
  const delivered = Object.fromEntries(candidates.map((candidate) => [candidate, 0]));
  const smallestCell = focusBlocks.length ? Math.min(...focusBlocks.map((block) => block.durationMinutes)) : 0;
  const unschedulable = categoryOrder.filter((categoryKey) => target[categoryKey] > 0 && target[categoryKey] < (1 - settings.overshootSlackCells) * smallestCell);
  for (const categoryKey of unschedulable) {
    warnings.push(`${categoryKey}: share ${categories[categoryKey].share} (${roundHalfUp(target[categoryKey])} min per fortnight) is less than a block can carry; not scheduled`);
  }

  const wakingStart = timeStringToMinutes(weights.wakingWindow?.start || (focusBlocks.length ? focusBlocks[0].start : "00:00"));
  const anchors = weights.blockSplit?.anchors || [];
  const restDays = new Set(weights.restDays || []);
  const peakIndex = peakBlockIndex(weights.energyPeak, focusBlocks.length, settings);

  const grid = Object.fromEntries(dayKeyOrder.map((dayKey) => [dayKey, {}]));
  const reasons = Object.fromEntries(dayKeyOrder.map((dayKey) => [dayKey, {}]));
  // Pass 1: pins.
  for (const dayKey of dayKeyOrder) {
    for (const block of focusBlocks) {
      if (restDays.has(weekdayOfDayKey(dayKey))) {
        grid[dayKey][block.key] = FLEXIBLE_FOCUS;
        reasons[dayKey][block.key] = REST_DAY_REASON;
        delivered[FLEXIBLE_FOCUS] += block.durationMinutes;
        continue;
      }
      const coverage = anchorCoverageByCategory(anchors, dayKey, block, wakingStart, categoryOrder);
      let bestKey = null;
      for (const categoryKey of categoryOrder) {
        if (categoryKey in coverage && (bestKey === null || coverage[categoryKey].minutes > coverage[bestKey].minutes)) bestKey = categoryKey;
      }
      if (bestKey === null) continue;
      const fraction = coverage[bestKey].minutes / block.durationMinutes;
      if (fraction >= settings.anchorPinCoverage) {
        grid[dayKey][block.key] = bestKey;
        reasons[dayKey][block.key] = `anchor: ${coverage[bestKey].activityIds.join(", ")} covers ${roundHalfUp(fraction * 100)}%`;
        delivered[bestKey] += block.durationMinutes;
      }
    }
  }
  if (delivered[FLEXIBLE_FOCUS] > target[FLEXIBLE_FOCUS] && restDays.size) {
    warnings.push(`rest days give flexible ${delivered[FLEXIBLE_FOCUS]} min, beyond its ${roundHalfUp(target[FLEXIBLE_FOCUS])} min share`);
  }

  // Pass 2: fill.
  for (const dayKey of dayKeyOrder) {
    const twinDayKey = otherVariantDayKey(dayKey);
    focusBlocks.forEach((block, blockIndex) => {
      const blockKey = block.key;
      if (blockKey in grid[dayKey]) return;
      const minutes = block.durationMinutes;
      let best = null;
      let bestScore = null;
      let bestTags = [];
      for (const candidate of candidates) {
        if (target[candidate] <= 0 || delivered[candidate] + minutes > target[candidate] + settings.overshootSlackCells * minutes) continue;
        let score = (target[candidate] - delivered[candidate] - minutes) / target[candidate];
        const tags = [];
        const preferred = candidate === FLEXIBLE_FOCUS ? [] : (categories[candidate]?.preferredBlocks || []);
        if (preferred.includes(blockKey)) {
          score += settings.preferredBlockWeight * (preferred.length - preferred.indexOf(blockKey)) / preferred.length;
          tags.push("preferred block");
        }
        if (peakIndex === blockIndex && candidate !== FLEXIBLE_FOCUS && categories[candidate]?.sentiment === "struggle") {
          score += settings.energyPeakWeight;
          tags.push("energy peak");
        }
        if (season.includes(candidate)) {
          score += settings.seasonFocusWeight * (season.length - season.indexOf(candidate)) / season.length;
          tags.push(`season focus #${season.indexOf(candidate) + 1}`);
        }
        if (grid[twinDayKey]?.[blockKey] === candidate) {
          score -= settings.alternationWeight;
          tags.push(`alternates with ${twinDayKey}`);
        }
        if (bestScore === null || score > bestScore) {
          best = candidate;
          bestScore = score;
          bestTags = tags;
        }
      }
      let primary;
      if (best === null) {
        const scheduled = candidates.filter((candidate) => target[candidate] > 0 && !unschedulable.includes(candidate));
        if (!scheduled.length) scheduled.push(FLEXIBLE_FOCUS);
        best = scheduled[0];
        for (const candidate of scheduled) {
          if (target[candidate] - delivered[candidate] > target[best] - delivered[best]) best = candidate;
        }
        primary = OVER_SHARE_REASON;
      } else {
        primary = `behind share (${roundHalfUp(delivered[best])}/${roundHalfUp(target[best])} min)`;
      }
      grid[dayKey][blockKey] = best;
      reasons[dayKey][blockKey] = [primary, ...bestTags].join("; ");
      delivered[best] += minutes;
    });
  }
  return { blockFocusGrid: grid, reasons, warnings };
}

/** Cell-by-cell comparison of two grids: { changes: [{dayKey, block, imported, proposed}], counts }. */
export function diffBlockFocusGrid(imported, proposed, dayKeyOrder = DAY_KEY_ORDER) {
  const changes = [];
  const counts = { same: 0, changed: 0, added: 0, removed: 0 };
  for (const dayKey of dayKeyOrder) {
    const proposedCells = proposed?.[dayKey] || {};
    const importedCells = imported?.[dayKey] || {};
    const blockKeys = [...Object.keys(proposedCells), ...Object.keys(importedCells).filter((blockKey) => !(blockKey in proposedCells))];
    for (const blockKey of blockKeys) {
      const before = importedCells[blockKey] ?? null;
      const after = proposedCells[blockKey] ?? null;
      if (before === after) {
        counts.same += 1;
        continue;
      }
      counts[before !== null && after !== null ? "changed" : before === null ? "added" : "removed"] += 1;
      changes.push({ dayKey, block: blockKey, imported: before, proposed: after });
    }
  }
  return { changes, counts };
}

// ---------- activities inside the cells ----------

/** Every block of the profile (unscheduled included), for placing clock times; the baseline falls back to blocks.json. */
export function allBlocksOf(weights, fallbackBlocks = null) {
  const blocks = [...(weights.blocks || [])];
  if (blocks.length || !fallbackBlocks) return blocks;
  return fallbackBlocks.order.map((key) => {
    const block = fallbackBlocks.blocks[key];
    return { key, start: block.start, end: block.end, durationMinutes: block.durationMinutes, carriesFocus: block.carriesFocus };
  });
}

/** Minutes of `block` on `dayKey` taken by anchors (each anchor once, whatever its categories). */
export function anchorMinutesInBlock(anchors, dayKey, block, wakingStartMinutes) {
  const blockStart = positiveModulo(timeStringToMinutes(block.start) - wakingStartMinutes, MINUTES_PER_DAY);
  const blockEnd = blockStart + block.durationMinutes;
  let taken = 0;
  for (const anchor of anchors) {
    if (anchor.dayKey !== dayKey || anchor.block === null || anchor.block === undefined) continue;
    const start = positiveModulo(timeStringToMinutes(anchor.start) - wakingStartMinutes, MINUTES_PER_DAY);
    const end = start + positiveModulo(timeStringToMinutes(anchor.end) - timeStringToMinutes(anchor.start), MINUTES_PER_DAY);
    taken += Math.max(0, Math.min(end, blockEnd) - Math.max(start, blockStart));
  }
  return taken;
}

/** Per category (in order): its non-peripheral subjects in categories.json order, with their range midpoints. */
export function subjectPools(weights, categories) {
  const subjects = weights.subjects || {};
  const pools = {};
  for (const categoryKey of categories.order) {
    const pool = [];
    for (const subjectId of categories.categories[categoryKey].subjects) {
      const subject = subjects[subjectId];
      if (!subject || !subject.minutesPerDay) continue;
      // The same weight that built the category's share; subjects contributing nothing (peripheral, or on the
      // section cadence) are done in flexible time, not in cells.
      const dailyMinutes = subjectDailyMinutes(subject);
      if (dailyMinutes <= 0) continue;
      pool.push([subjectId, dailyMinutes]);
    }
    pools[categoryKey] = pool;
  }
  return pools;
}

/** Proposed activities inside the cells of `grid` (the person's own or the proposal's): { activities, placedMinutes, warnings }.
 *  Exact twin of fk_core.generator.generate_activities (rule 5 of its docstring; docs/generator.md). */
export function generateActivities(weights, grid, questionnaire, { categories, dayKeyOrder = DAY_KEY_ORDER, fallbackBlocks = null }) {
  const settings = generatorSettings(questionnaire);
  const gridMinutes = settings.sessionGridMinutes;
  const focusBlocks = focusBlocksOf(weights, fallbackBlocks);
  const allBlocks = allBlocksOf(weights, fallbackBlocks);
  grid = grid || {};
  const activities = [];
  const warnings = [];
  if (!focusBlocks.length) return { activities: [], placedMinutes: {}, warnings: ["activities: no focus blocks"] };
  if (!weights.subjects || !Object.keys(weights.subjects).length) return { activities: [], placedMinutes: {}, warnings: ["activities: the weights carry no subjects; nothing to place"] };
  const focusBlockKeys = focusBlocks.map((block) => block.key);
  const wakingStart = timeStringToMinutes(weights.wakingWindow?.start || focusBlocks[0].start);
  const anchors = weights.blockSplit?.anchors || [];
  const restDays = new Set(weights.restDays || []);
  const weightsCategories = weights.categories || {};
  const subjectLabels = Object.fromEntries(Object.entries(categories.subjects).map(([subjectId, subject]) => [subjectId, subject.label]));
  const categoryLabels = Object.fromEntries(Object.entries(categories.categories).map(([categoryKey, category]) => [categoryKey, category.label]));
  const practiceLabels = Object.fromEntries(((questionnaire.options || {}).practices || []).map((option) => [option.id, option.label]));
  const focusOf = (dayKey, blockKey) => (grid[dayKey] || {})[blockKey] || FLEXIBLE_FOCUS;
  const isRestDay = (dayKey) => restDays.has(weekdayOfDayKey(dayKey));

  const capacity = Object.fromEntries(dayKeyOrder.map((dayKey) => [dayKey, Object.fromEntries(focusBlocks.map((block) => [block.key, Math.max(0, block.durationMinutes - anchorMinutesInBlock(anchors, dayKey, block, wakingStart))]))]));
  const counts = {};
  const emit = (kind, slug, title, dayKey, blockKey, priority, categoryKeys, minutes, reason, subjectId = null, timing = null) => {
    const countsKey = `${kind}|${slug}|${dayKey}|${blockKey}`;
    counts[countsKey] = (counts[countsKey] || 0) + 1;
    const number = counts[countsKey];
    activities.push({
      id: `proposed--${kind}--${slug}--${dayKey}--${blockKey}` + (number > 1 ? `--${number}` : ""),
      title: title + (number > 1 ? ` (${number})` : ""),
      kind,
      dayKey,
      block: blockKey,
      priority,
      categories: [...categoryKeys],
      subjectId,
      timing,
      minutes,
      reason,
      source: PROPOSED_SOURCE,
    });
    capacity[dayKey][blockKey] = Math.max(0, capacity[dayKey][blockKey] - minutes);
  };

  // 1. Practices, 2. meals — per day (they take capacity before the sessions are sized).
  const practices = [...(weights.practices || [])];
  const meals = weights.meals?.meals || [];
  const mealPlan = weights.mealPlan || { items: [] };
  const mealWarnings = [];
  for (const dayKey of dayKeyOrder) {
    const practiceBlock = focusBlockKeys.find((key) => focusOf(dayKey, key) === SPIRITUALITY_CATEGORY) ?? focusBlockKeys[0];
    for (const practiceId of practices) {
      emit("practice", practiceId, `Practice: ${practiceLabels[practiceId] ?? practiceId}`, dayKey, practiceBlock, 2, [SPIRITUALITY_CATEGORY], settings.practiceMinutes, "daily practice");
    }
    const menu = menuForDay(mealPlan, meals, dayKey); // the ForkKnife menu names each meal's dish (its prep/cook tasks arrive as tasks)
    meals.forEach((meal, mealIndex) => {
      const slots = [...(meal.slots || [])];
      let chosen = null;
      for (const slot of slots) {
        const slotTime = settings.mealSlotTimes[slot];
        if (slotTime === null || slotTime === undefined) continue;
        const blockKey = blockKeyForTime(allBlocks, slotTime);
        if (focusBlockKeys.includes(blockKey)) {
          chosen = { slot, slotTime, blockKey };
          break;
        }
      }
      if (chosen === null) {
        const warning = `activities: meal ${mealIndex + 1}: ${slots.length === 1 ? "slot" : "slots"} ${slots.join(", ") || "(none)"} fall outside the focus blocks; not placed`;
        if (!mealWarnings.includes(warning)) mealWarnings.push(warning);
        return;
      }
      const endMinutes = (timeStringToMinutes(chosen.slotTime) + settings.mealMinutes) % MINUTES_PER_DAY;
      const served = mealIndex < menu.length ? menu[mealIndex] : null;
      const name = meal.name || `Meal ${mealIndex + 1}`;
      const title = served && served.dish ? `${name}: ${served.dish}${served.leftovers ? " (leftovers)" : ""}` : name;
      emit("meal", `meal-${mealIndex + 1}`, title, dayKey, chosen.blockKey, 2, ["meals"], settings.mealMinutes, `meal slot ${chosen.slot}`, null,
        { estimatedStart: chosen.slotTime, estimatedEnd: minutesToTimeString(endMinutes), durationMinutes: settings.mealMinutes });
    });
  }
  warnings.push(...mealWarnings);
  // A cell whose anchors leave less room than its practices and meals need: they are still listed (a meal or a
  // daily habit is not optional), but the person should know the block is over-committed.
  const overCommitted = [];
  for (const dayKey of dayKeyOrder) {
    for (const block of focusBlocks) {
      const fixed = activities.filter((activity) => activity.dayKey === dayKey && activity.block === block.key).reduce((sum, activity) => sum + activity.minutes, 0);
      const free = block.durationMinutes - anchorMinutesInBlock(anchors, dayKey, block, wakingStart);
      if (fixed > Math.max(0, free)) overCommitted.push(`${dayLabel(dayKey)} ${block.key} (${fixed} min of practices/meals, ${Math.max(0, free)} min free)`);
    }
  }
  if (overCommitted.length) warnings.push("activities: over-committed by anchors: " + overCommitted.join("; "));

  // 3. Targets per subject: the usable minutes (non-rest cells after anchors, practices and meals) split by
  // category share, then by the subject's range midpoint within its category — multiples of the session grid.
  let usableMinutes = 0;
  for (const dayKey of dayKeyOrder) {
    if (isRestDay(dayKey)) continue;
    for (const blockKey of focusBlockKeys) usableMinutes += capacity[dayKey][blockKey];
  }
  const pools = subjectPools(weights, categories);
  const need = {};
  const target = {};
  const placed = {};
  for (const categoryKey of categories.order) {
    const share = weightsCategories[categoryKey]?.share ?? 0;
    const pool = pools[categoryKey];
    const midpointTotal = pool.reduce((sum, [, midpoint]) => sum + midpoint, 0);
    if (share > 0 && midpointTotal === 0) {
      warnings.push(`activities: ${categoryLabels[categoryKey] ?? categoryKey} has a share of ${share} but no subjects to carry it`);
      continue;
    }
    for (const [subjectId, midpoint] of pool) {
      const minutes = midpointTotal ? roundHalfUp(usableMinutes * share * midpoint / midpointTotal / gridMinutes) * gridMinutes : 0;
      need[subjectId] = minutes;
      target[subjectId] = minutes;
      placed[subjectId] = 0;
    }
  }

  /** Split a cell's minutes among subjects in proportion to their remaining need (whole grid units, largest
   *  remainders first, ties in pool order); nobody gets more than they need. */
  const proportionalSplit = (subjectIds, minutesAvailable) => {
    const needy = subjectIds.filter((subjectId) => need[subjectId] > 0);
    const totalNeed = needy.reduce((sum, subjectId) => sum + need[subjectId], 0);
    if (!needy.length || totalNeed === 0) return [];
    if (totalNeed <= minutesAvailable) return needy.map((subjectId) => [subjectId, need[subjectId]]);
    const units = Math.floor(minutesAvailable / gridMinutes);
    const exact = Object.fromEntries(needy.map((subjectId) => [subjectId, units * need[subjectId] / totalNeed]));
    const floors = Object.fromEntries(needy.map((subjectId) => [subjectId, Math.floor(exact[subjectId])]));
    const leftover = units - Object.values(floors).reduce((sum, value) => sum + value, 0);
    const byRemainder = [...needy].sort((left, right) => ((exact[right] - floors[right]) - (exact[left] - floors[left])) || (needy.indexOf(left) - needy.indexOf(right)));
    for (const subjectId of byRemainder.slice(0, leftover)) floors[subjectId] += 1;
    return needy.filter((subjectId) => floors[subjectId] > 0).map((subjectId) => [subjectId, floors[subjectId] * gridMinutes]);
  };

  // 4. Focus fill: each focus cell's capacity is split among its category's subjects by remaining need.
  for (const dayKey of dayKeyOrder) {
    if (isRestDay(dayKey)) continue;
    for (const blockKey of focusBlockKeys) {
      const focus = focusOf(dayKey, blockKey);
      if (focus === FLEXIBLE_FOCUS || !(focus in pools) || capacity[dayKey][blockKey] < gridMinutes) continue;
      for (const [subjectId, minutes] of proportionalSplit(pools[focus].map(([subjectId]) => subjectId), capacity[dayKey][blockKey])) {
        need[subjectId] -= minutes;
        placed[subjectId] += minutes;
        emit("session", subjectId, subjectLabels[subjectId] ?? subjectId, dayKey, blockKey, 3, [focus], minutes, `focus ${focus}: ${placed[subjectId]}/${target[subjectId]} min`, subjectId);
      }
    }
  }

  const neediest = (candidates) => {
    let best = null;
    for (const candidate of candidates) {
      if ((need[candidate[0]] ?? 0) <= 0) continue;
      if (best === null || need[candidate[0]] > need[best[0]]) best = candidate;
    }
    return best;
  };
  /** A spillover session for the neediest subject, at most maxSessionMinutes; the same subject still neediest
   *  extends its session instead of adding a second record to the cell. */
  const placeSpillover = (dayKey, blockKey, subjectId, categoryKey) => {
    const minutes = Math.floor(Math.min(need[subjectId], capacity[dayKey][blockKey], settings.maxSessionMinutes) / gridMinutes) * gridMinutes;
    if (minutes <= 0) return false; // a maxSessionMinutes below the grid can place nothing: stop the cell rather than loop
    need[subjectId] -= minutes;
    placed[subjectId] += minutes;
    const reason = `spillover: ${categoryKey} behind by ${need[subjectId]} min`;
    const last = activities.length ? activities[activities.length - 1] : null;
    if (last && last.kind === "session" && last.subjectId === subjectId && last.dayKey === dayKey && last.block === blockKey) {
      last.minutes += minutes;
      last.reason = reason;
      capacity[dayKey][blockKey] = Math.max(0, capacity[dayKey][blockKey] - minutes);
      return true;
    }
    emit("session", subjectId, subjectLabels[subjectId] ?? subjectId, dayKey, blockKey, 4, [categoryKey], minutes, reason, subjectId);
    return true;
  };
  // 5. Spillover into flexible cells.
  const allCandidates = categories.order.flatMap((categoryKey) => pools[categoryKey].map(([subjectId]) => [subjectId, categoryKey]));
  for (const dayKey of dayKeyOrder) {
    if (isRestDay(dayKey)) continue;
    for (const blockKey of focusBlockKeys) {
      if (focusOf(dayKey, blockKey) !== FLEXIBLE_FOCUS) continue;
      while (capacity[dayKey][blockKey] >= gridMinutes) {
        const best = neediest(allCandidates);
        if (best === null || !placeSpillover(dayKey, blockKey, best[0], best[1])) break;
      }
    }
  }
  // 6. Warnings: one line per category whose subjects did not all fit.
  for (const categoryKey of categories.order) {
    const short = pools[categoryKey].filter(([subjectId]) => subjectId in need && need[subjectId] >= gridMinutes).map(([subjectId]) => [subjectId, need[subjectId]]);
    if (short.length) {
      const unplacedTotal = short.reduce((sum, [, minutes]) => sum + minutes, 0);
      const categoryTarget = pools[categoryKey].filter(([subjectId]) => subjectId in target).reduce((sum, [subjectId]) => sum + target[subjectId], 0);
      const details = short.map(([subjectId, minutes]) => `${subjectLabels[subjectId] ?? subjectId} ${minutes}`).join(", ");
      // Not a failure — a category too small to win whole cells (errands twice a fortnight) is done in flexible time.
      warnings.push(`activities: ${categoryLabels[categoryKey] ?? categoryKey}: ${unplacedTotal} of ${categoryTarget} min left for flexible time — too little to fill a cell of its own (${details})`);
    }
  }
  const placedMinutes = Object.fromEntries(Object.keys(target).map((subjectId) => [subjectId, { target: target[subjectId], placed: placed[subjectId] }]));
  return { activities, placedMinutes, warnings };
}

/** The `proposal` a weights file carries: the generated grid, its reasons and warnings, the season it was
 *  generated for, the diff against the weights' own blockFocusGrid, and the activities proposed inside the grid. */
export function proposalFromWeights(weights, questionnaire, { seasonFocus = null, seasonId = null, categories, categoryOrder = categories?.order, dayKeyOrder = DAY_KEY_ORDER, fallbackBlocks = null }) {
  const generated = generateBlockFocusGrid(weights, questionnaire, { seasonFocus, categoryOrder, dayKeyOrder, fallbackBlocks });
  const activities = generateActivities(weights, generated.blockFocusGrid, questionnaire, { categories, dayKeyOrder, fallbackBlocks });
  return {
    blockFocusGrid: generated.blockFocusGrid,
    seasonId,
    reasons: generated.reasons,
    warnings: [...generated.warnings, ...activities.warnings],
    diff: diffBlockFocusGrid(weights.blockFocusGrid, generated.blockFocusGrid, dayKeyOrder),
    activities: activities.activities,
    placedMinutes: activities.placedMinutes,
  };
}
