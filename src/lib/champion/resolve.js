// The resolver: an ISO date and a wall time in, one day's screen-ready view out of a CHAMPION'S KEEP.
//
// The input is the one document this repository never holds: a fort's complete file, a real household's
// schedule (scripts/fk_core/no_schedules.py keeps it out). This code reads it; the tests feed it an
// invented one built by tests/champion_fixture.py. Moved here from the Fort Knight phone app's
// src/lib/resolve.js on 2026-09-02 (Operation MVP, working set docs/megaseed/mvp.md; the app's last
// commit is fortknight 4612072), because the writer that needs it now lives beside the format it writes.
//
// DELIBERATE TWIN of tests/champion_reference.py, which re-implements every function here in Python. The
// parity suite runs both over every date in the fixture's calendar and asserts they agree. Never change
// one alone.
//
// The hard rule this file exists to enforce: NO CALENDAR MATH. Seasons, fortnights and A/B letters are
// looked up in `keep.calendar`, never computed. Past the calendar's range the answer is "expired", not a
// guess. Everything else here is joining rows the mason already resolved.
//
// Pure: no DOM, no fetch — and no data imports. Every function takes the keep as an argument, because
// node refuses a bare JSON import and one such import here would break the whole suite.
import { blockKeyForTime } from "../shared/clock.js";

/** Each block's primary meal is the one it actually serves, so brunch, snack and dinner each land on
 *  exactly one block of the day. Early's primary is Breakfast, which ForkKnifeSlab's Meals sheet does not
 *  carry — early simply shows no dish. Keys are lowercased block.mealPrimary; values are `meals` fields. */
const MEAL_FIELD_BY_NAME = { brunch: "brunch", snack: "snack", dinner: "dinner" };

/** The first and last date the keep can answer for. */
export function calendarRange(keep) {
  const calendar = keep.calendar;
  return { first: calendar[0].date, last: calendar[calendar.length - 1].date };
}

/** The calendar row for an ISO date, or null when the date is outside the keep's range. */
export function calendarEntryForDate(keep, isoDate) {
  return keep.calendar.find((entry) => entry.date === isoDate) ?? null;
}

/** The season record for a season key. */
export function seasonByKey(keep, seasonKey) {
  return keep.seasons.find((season) => season.key === seasonKey) ?? null;
}

/** A season key as its display name ("spooky" -> "Spooky"), falling back to the key itself. */
export function seasonName(keep, seasonKey) {
  return seasonByKey(keep, seasonKey)?.name ?? seasonKey;
}

/** The `days` row for a day key. */
export function dayByKey(keep, dayKey) {
  return keep.days.find((day) => day.dayKey === dayKey) ?? null;
}

/** A category key as its slab label ("friends-family" -> "Friends & Family"). The pseudo-focus
 *  "flexible" is not a category, so it comes back title-cased rather than looked up. */
export function categoryLabel(keep, categoryKey) {
  const category = keep.categories.find((entry) => entry.key === categoryKey);
  if (category) return category.label;
  return categoryKey ? categoryKey.charAt(0).toUpperCase() + categoryKey.slice(1) : "";
}

/** A day key's tasks for one block, in slab order, grouped by FortKnightSlab's Tasks sheet, Description column
 *  ("Cleaning", "Laundry", "Open for Appointments"...). Groups keep first-appearance order. */
export function taskGroupsFor(keep, dayKey, blockKey) {
  const groups = [];
  for (const task of keep.tasks) {
    if (task.dayKey !== dayKey || task.block !== blockKey) continue;
    let group = groups.find((candidate) => candidate.group === task.group);
    if (!group) {
      group = { group: task.group, category: task.category, tasks: [] };
      groups.push(group);
    }
    group.tasks.push({
      id: task.id,
      step: task.step,
      category: task.category,
      // Meal Prep & Store tasks only; every other task's list is empty. The day keys and gaps are the
      // exporter's — this joins the label, which is the one thing a screen should not be deriving.
      serves: (task.serves ?? []).map((serving) => ({
        role: serving?.role ?? null,
        dayKey: serving?.dayKey ?? null,
        label: dayLabel(keep, serving?.dayKey) ?? null,
        daysAfter: serving?.daysAfter ?? 0,
      })),
    });
  }
  return groups;
}

/** A day key's appointments for one block, earliest estimated start first, then by title so the order is
 *  total (two appointments may share a start). */
export function appointmentsFor(keep, dayKey, blockKey) {
  return keep.appointments
    .filter((appointment) => appointment.dayKey === dayKey && appointment.block === blockKey)
    .sort((left, right) =>
      left.timing.estimatedStart.localeCompare(right.timing.estimatedStart) || left.title.localeCompare(right.title));
}

/** The `meals` row for a day key: what ForkKnifeSlab's Meals sheet shows. "FLEXIBLE" and "OUT" are values. */
export function mealsForDayKey(keep, dayKey) {
  return keep.meals.find((meals) => meals.dayKey === dayKey) ?? null;
}

/** The dish a block serves: its primary meal's name, and the day's text for it. Null when the block's
 *  primary meal has no column on the Meals sheet (early's Breakfast). */
export function mealForBlock(keep, dayKey, block) {
  const field = MEAL_FIELD_BY_NAME[block.mealPrimary.toLowerCase()];
  if (!field) return null;
  const meals = mealsForDayKey(keep, dayKey);
  if (!meals) return null;
  return { name: block.mealPrimary, dish: meals[field] };
}

/** Every task id a day key can show, in the order the day renders them — the set a "checked everything"
 *  count is measured against. */
export function taskIdsForDayKey(keep, dayKey) {
  return keep.blocks.flatMap((block) =>
    taskGroupsFor(keep, dayKey, block.key).flatMap((group) => group.tasks.map((task) => task.id)));
}

/** The fortnight containing isoDate as [firstDate, isoDate]: from the latest calendar date at or before
 *  isoDate whose day key is sun-a (every fortnight starts sun-a; transition weeks carry null day keys, so
 *  a transition date's window is just itself and carry-over is moot — the screen renders only the
 *  headline). Clips to the calendar's first date when today predates any in-range sun-a — the calendar
 *  opens mid-fortnight (2026-01-01 is a thu-a). ISO dates compare as strings. */
export function fortnightWindowFor(keep, isoDate) {
  let start = null;
  for (const entry of keep.calendar) {
    if (entry.date > isoDate) break;
    if (entry.dayKey === "sun-a") start = entry.date;
  }
  if (start === null) start = keep.calendar[0].date;
  return [start, isoDate];
}

/** Tasks from earlier days of this fortnight that were never checked off and have not been superseded by
 *  a later assignment of the same step — the catch-up list the Flexible-focus blocks show.
 *
 *  The rules (Jesse's): unchecked when its day passes = skipped; a skip rides every later Flexible block
 *  of the fortnight until it is checked (a check under ANY date in the window counts, so a flex-block
 *  check-off sticks to the original assignment), until the task repeats — a later assignment of the same
 *  step text takes over and the skipped instance is cleared — or until the fortnight ends. Entries are in
 *  assignment order and carry the origin (fromWeekday/fromDate) so the screen never reads the keep. */
export function carriedTasksFor(keep, checkoffs, isoDate) {
  const [start] = fortnightWindowFor(keep, isoDate);
  const checkedIds = new Set();
  for (const [date, taskIds] of Object.entries(checkoffs)) {
    if (date >= start && date <= isoDate) {
      for (const taskId of taskIds) checkedIds.add(taskId);
    }
  }
  const carried = [];
  for (const entry of keep.calendar) {
    if (entry.date < start || entry.date >= isoDate || !entry.dayKey) continue;
    for (const task of keep.tasks) {
      if (task.dayKey !== entry.dayKey || checkedIds.has(task.id)) continue;
      const superseded = keep.calendar.some((later) =>
        later.date > entry.date && later.date <= isoDate && later.dayKey !== null &&
        keep.tasks.some((candidate) => candidate.dayKey === later.dayKey && candidate.step === task.step));
      if (superseded) continue;
      carried.push({
        id: task.id,
        step: task.step,
        category: task.category,
        group: task.group,
        fromDayKey: entry.dayKey,
        fromWeekday: dayByKey(keep, entry.dayKey).weekday,
        fromDate: entry.date,
      });
    }
  }
  return carried;
}

/** One date, resolved for the screen. `status` is the whole story:
 *
 *  - "expired"    — the date is past the keep's calendar. Regenerate the keep; do NOT start computing.
 *  - "transition" — a season's closing odd week. Renders `headline` and nothing else: no blocks, no
 *                   tasks, no meals (CLAUDE.md's hard rule).
 *  - "day"        — the ordinary case: the day key's focuses, blocks, tasks, appointments and meals.
 *
 *  `wallTime` ("HH:MM") only decides which block is marked current; pass null and none is. A block that
 *  wraps midnight is current from 18:00 through 07:59, and is always *this* date's too-dark row — the
 *  calendar keys off the device's date, so the small hours belong to the day that is dawning. */
export function resolveDay(keep, isoDate, wallTime = null) {
  const entry = calendarEntryForDate(keep, isoDate);
  if (!entry) return { status: "expired", date: isoDate, range: calendarRange(keep) };

  const season = seasonByKey(keep, entry.season);
  const seasonView = {
    key: entry.season,
    name: seasonName(keep, entry.season),
    weekOfSeason: entry.weekOfSeason,
    focus: (season?.focus ?? []).map((categoryKey) => ({ key: categoryKey, label: categoryLabel(keep, categoryKey) })),
  };

  if (entry.transition || entry.dayKey === null) {
    return {
      status: "transition",
      date: isoDate,
      season: seasonView,
      transitionTo: entry.transitionTo
        ? { key: entry.transitionTo, name: seasonName(keep, entry.transitionTo) }
        : null,
      headline: entry.transitionTo
        ? `${seasonView.name} Transitioning to ${seasonName(keep, entry.transitionTo)}`
        : `${seasonView.name} Transitioning`,
    };
  }

  const day = dayByKey(keep, entry.dayKey);
  const currentBlockKey = wallTime ? blockKeyForTime(keep.blocks, wallTime) : null;

  return {
    status: "day",
    date: isoDate,
    season: seasonView,
    day: {
      index: day.index,
      dayKey: day.dayKey,
      weekday: day.weekday,
      variant: day.variant,
      label: `${day.weekday} ${day.variant}`,
      week: day.index <= 7 ? 1 : 2,
      mainFocus: day.mainFocus,
      mainFocusLabel: day.mainFocusLabel,
    },
    currentBlock: currentBlockKey,
    meals: mealsForDayKey(keep, entry.dayKey),
    blocks: keep.blocks.map((block) => ({
      key: block.key,
      label: block.label,
      start: block.start,
      end: block.end,
      wrapsMidnight: block.wrapsMidnight,
      focus: day.blockFocus[block.key] ?? null,
      isCurrent: block.key === currentBlockKey,
      meal: mealForBlock(keep, entry.dayKey, block),
      appointments: appointmentsFor(keep, entry.dayKey, block.key),
      taskGroups: taskGroupsFor(keep, entry.dayKey, block.key),
    })),
  };
}

/** The fortnight menu for the Menu screen: ForkKnifeSlab's Menu sheet grouped by slot, in slot order, each
 *  row carrying the day keys it is cooked and eaten on. Content only — no date, no calendar. */
export function resolveMenu(keep) {
  const slots = [
    { slot: "brunch", label: "Brunch" },
    { slot: "snack", label: "Snack" },
    { slot: "dinner", label: "Dinner" },
  ];
  return slots.map(({ slot, label }) => ({
    slot,
    label,
    entries: keep.menu
      .filter((entry) => entry.slot === slot)
      .map((entry) => ({
        mealKey: entry.mealKey,
        menu: entry.menu,
        cookDay: entry.cookDay,
        cookDayLabel: dayLabel(keep, entry.cookDay),
        leftoversDay: entry.leftoversDay,
        leftoversDayLabel: entry.leftoversDay ? dayLabel(keep, entry.leftoversDay) : null,
        cookExtra: entry.cookExtra,
        cookExtraNote: entry.cookExtraNote,
      })),
  }));
}

/** A day key as people read it: "sun-a" -> "Sunday A". */
export function dayLabel(keep, dayKey) {
  const day = dayByKey(keep, dayKey);
  return day ? `${day.weekday} ${day.variant}` : dayKey;
}

/** FolkKnowledgeSlab ranks each produce group most important first. Ranks are held in this order rather than
 *  read off object key order, and a group that stops at tertiary (fruit does) simply yields three items. */
const PRODUCE_RANKS = ["hero", "secondary", "tertiary", "quaternary"];

/** "vegetables" -> "Vegetables". The produce groups are the only keys that need it. */
function titleCase(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

/** A season's produce as ordered lists: [{group, label, items: [{rank, name}]}]. The slab holds it as
 *  {vegetables: {hero, secondary, ...}, fruit: {...}}, which is not something a screen should be reading. */
export function produceLists(season) {
  return Object.entries(season.produce ?? {}).map(([group, ranked]) => ({
    group,
    label: titleCase(group),
    items: PRODUCE_RANKS
      .filter((rank) => ranked?.[rank])
      .map((rank) => ({ rank, name: ranked[rank] })),
  })).filter((group) => group.items.length > 0);
}

/** A season's meal ideas as [{name, text}] in slab order. Each is a single line of the sheet's own
 *  words ("Corned Beef & Cabbage"), not a list. */
export function mealIdeaLists(season) {
  return Object.entries(season.mealIdeas ?? {})
    .filter(([, text]) => typeof text === "string" && text.length > 0)
    .map(([name, text]) => ({ name, text }));
}

/** The Seasons screen: all five in wheel order, with the one containing `isoDate` marked current.
 *  Outside the calendar's range no season is current — the app is expired, not somewhere else. */
export function resolveSeasons(keep, isoDate = null) {
  const currentKey = isoDate ? (calendarEntryForDate(keep, isoDate)?.season ?? null) : null;
  return keep.seasons.map((season) => ({
    key: season.key,
    name: season.name,
    isCurrent: season.key === currentKey,
    gregorianRange: season.gregorianRange ?? null,
    startDescription: season.startDescription ?? null,
    safeOutsidePercent: season.safeOutsidePercent ?? null,
    focus: (season.focus ?? []).map((categoryKey) => ({ key: categoryKey, label: categoryLabel(keep, categoryKey) })),
    produce: produceLists(season),
    mealIdeas: mealIdeaLists(season),
  }));
}

/** One calendar year's Norse wheel: the five seasons as slices, sized by their share of the days the keep's
 *  calendar covers of that year, in wheel order — so 0 degrees is the start of Ostara, not 1 January.
 *
 *  Every number here is the exporter's — days, whole percents, whole degrees — because counting the calendar
 *  per season on the device is the calendar math CLAUDE.md forbids, and because a figure this file and
 *  tests/champion_reference.py both computed would eventually disagree on a .5 (Python rounds half to even,
 *  JavaScript rounds half up).
 *
 *  `isoDate` picks the year by its first four characters — a string match, never a parse — and marks the
 *  season containing it. Outside the calendar's range no slice is current, exactly as resolveSeasons has it:
 *  the app is expired, not somewhere else. A year the keep carries no row for comes back "missing" rather
 *  than computed, the same way resolveDay says "expired". Reads are tolerant so an older or sparser keep
 *  cannot make this throw in a reader. */
export function resolveYear(keep, isoDate = null) {
  const year = (isoDate ?? "").slice(0, 4);
  const row = (keep.years ?? []).find((entry) => entry?.year === year) ?? null;
  const currentSeasonKey = isoDate ? (calendarEntryForDate(keep, isoDate)?.season ?? null) : null;
  if (!row) {
    return {
      status: "missing",
      year,
      daysInYear: null,
      daysCovered: 0,
      coversWholeYear: false,
      firstDate: null,
      lastDate: null,
      slices: [],
    };
  }
  return {
    status: "year",
    year,
    daysInYear: row.daysInYear ?? null,
    daysCovered: row.daysCovered ?? 0,
    coversWholeYear: row.coversWholeYear ?? false,
    firstDate: row.firstDate ?? null,
    lastDate: row.lastDate ?? null,
    slices: (row.slices ?? []).map((slice) => ({
      key: slice?.key ?? null,
      name: seasonName(keep, slice?.key),
      days: slice?.days ?? 0,
      percent: slice?.percent ?? 0,
      startDegree: slice?.startDegree ?? 0,
      sweepDegree: slice?.sweepDegree ?? 0,
      isCurrent: slice?.key === currentSeasonKey,
    })),
  };
}
