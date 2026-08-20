// JavaScript port of scripts/fk_core/dates.py + keys.py (keep in sync; tests live on the Python side).
// Pure functions only — no DOM, no fetch.
//
// A season (workbook or a person's own, docs/questionnaire.md "Section start rules") starts by a
// structured rule: {kind, ...kind fields, offsetDays, snap}. Evaluation for a year: the kind's base
// date -> + offsetDays -> snap to a weekday (on-or-after / on-or-before) or none. Anything that cannot
// be resolved (Feb 30, the 13th new moon of a 12-moon year, a manual season without a typed date for
// that year, no rule at all) yields null: that season simply does not restart the fortnight that year.
import { newMoonDatesInYear, solarTermDate } from "./astronomy.js";

export const WEEKDAY_NAMES = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
export const FLEXIBLE_FOCUS = "flexible"; // the pseudo-focus (categories.json flexibleFocus)

export const DAY_KEY_ORDER = [
  "sun-a", "mon-b", "tue-a", "wed-b", "thu-a", "fri-b", "sat-a",
  "sun-b", "mon-a", "tue-b", "wed-a", "thu-b", "fri-a", "sat-b",
];
export const CYCLE_LENGTH_DAYS = DAY_KEY_ORDER.length;
export const SUBJECT_CADENCES = ["fortnight", "section"];

/** What a subject contributes to its category's raw minutes, per day. The slider always means "how long in a
 *  single day"; the cadence says how many days. Everyday subjects contribute their midpoint; a fortnight subject
 *  contributes it on `daysPerPeriod` of the cycle's 14 days. A subject on the section cadence, and one marked
 *  "not often" (peripheral), contribute nothing — they are done in the fortnight's flexible time rather than in
 *  its rhythm, and it is their absence from the declaration that leaves that time free. Twin of
 *  fk_core.keys.subject_daily_minutes; lives here so the generator can read it without importing weights-rules. */
export function subjectDailyMinutes(subjectAnswer) {
  if (subjectAnswer.peripheral) return 0;
  const midpoint = (subjectAnswer.minutesPerDay.min + subjectAnswer.minutesPerDay.max) / 2;
  if (subjectAnswer.everyday ?? true) return midpoint;
  if (subjectAnswer.cadence === "fortnight") return (midpoint * Number(subjectAnswer.daysPerPeriod || 0)) / CYCLE_LENGTH_DAYS;
  return 0;
}
export const START_RULE_KINDS = ["fixed-date", "nth-weekday", "easter", "solar", "new-moon", "manual"];
export const SNAP_DIRECTIONS = ["on-or-after", "on-or-before"];
export const NTH_OCCURRENCES = [1, 2, 3, 4, -1]; // -1 = the last one in the month
export const NEW_MOON_MAX_INDEX = 13;
const MILLISECONDS_PER_DAY = 86400000;

/** 'sunday' -> 0 ... 'saturday' -> 6 (Date.getUTCDay convention, shared by both ports). */
export function weekdayNumber(weekdayName) {
  return WEEKDAY_NAMES.indexOf(weekdayName);
}

/** ('monday', 'b') -> 'mon-b'. */
export function dayKeyFromWeekdayAndVariant(weekdayName, variant) {
  return `${weekdayName.slice(0, 3)}-${variant.toLowerCase()}`;
}

/** DAY_KEY_ORDER rotated so it begins on the first key of that weekday (display only; the canonical order stays). */
export function dayKeyOrderStartingOn(weekdayName) {
  const firstIndex = DAY_KEY_ORDER.findIndex((dayKey) => dayKey.startsWith(weekdayName.slice(0, 3)));
  return [...DAY_KEY_ORDER.slice(firstIndex), ...DAY_KEY_ORDER.slice(0, firstIndex)];
}

function utcDate(year, monthIndex, day) {
  return new Date(Date.UTC(year, monthIndex, day));
}

function addDays(date, days) {
  return new Date(date.getTime() + days * MILLISECONDS_PER_DAY);
}

export function weekdayOnOrAfter(date, targetWeekdayNumber) {
  return addDays(date, (targetWeekdayNumber - date.getUTCDay() + 7) % 7);
}

export function weekdayOnOrBefore(date, targetWeekdayNumber) {
  return addDays(date, -((date.getUTCDay() - targetWeekdayNumber + 7) % 7));
}

/** occurrence 1..4 = the nth such weekday; -1 = the last one. `month` is 1-12. */
export function nthWeekdayOfMonth(year, month, targetWeekdayNumber, occurrence) {
  if (occurrence === -1) {
    const lastOfMonth = addDays(utcDate(year, month, 1), -1); // month index `month` = the next month’s first day
    return weekdayOnOrBefore(lastOfMonth, targetWeekdayNumber);
  }
  return addDays(weekdayOnOrAfter(utcDate(year, month - 1, 1), targetWeekdayNumber), 7 * (occurrence - 1));
}

export function easterSunday(year) {
  const a = year % 19, b = Math.floor(year / 100), c = year % 100;
  const d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return utcDate(year, month - 1, day);
}

function baseDateForRule(rule, year, knownStarts) {
  switch (rule.kind) {
    case "fixed-date": {
      const date = utcDate(year, rule.month - 1, rule.day);
      // Date.UTC rolls Feb 30 over to March; Python raises instead — both must yield "no start".
      return date.getUTCMonth() === rule.month - 1 && date.getUTCDate() === rule.day ? date : null;
    }
    case "nth-weekday":
      return nthWeekdayOfMonth(year, rule.month, weekdayNumber(rule.weekday), rule.occurrence);
    case "easter":
      return easterSunday(year);
    case "solar":
      return solarTermDate(rule.term, year);
    case "new-moon": {
      const dates = newMoonDatesInYear(year);
      return rule.index >= 1 && rule.index <= dates.length ? dates[rule.index - 1] : null;
    }
    case "manual": {
      const typed = knownStarts ? knownStarts[String(year)] : null;
      return typed ? parseIsoDate(typed) : null;
    }
    default:
      throw new Error(`unknown start rule kind: ${rule.kind}`);
  }
}

/** The ONE evaluator: rule -> Date for `year`, or null when the rule cannot resolve that year. */
export function startDateForRule(rule, year, knownStarts = null) {
  if (!rule) return null;
  let date = baseDateForRule(rule, year, knownStarts);
  if (date === null) return null;
  date = addDays(date, rule.offsetDays || 0);
  if (rule.snap) {
    const target = weekdayNumber(rule.snap.weekday);
    date = rule.snap.direction === "on-or-after" ? weekdayOnOrAfter(date, target) : weekdayOnOrBefore(date, target);
  }
  return date;
}

export function seasonStartDate(season, year) {
  return startDateForRule(season.startRule, year, season.knownStarts || null);
}

/** [{startDate, season}] sorted by date for one calendar year (unresolvable seasons skipped). */
export function seasonStartsForYear(seasons, year) {
  return seasons
    .map((season) => ({ startDate: seasonStartDate(season, year), season }))
    .filter((entry) => entry.startDate !== null)
    .sort((left, right) => left.startDate - right.startDate);
}

/** The season whose most recent start is on or before `date` (looks back into the prior year);
 *  null when no season has started by then. Ties: the later one in the list. */
export function seasonForDate(seasons, date) {
  const year = date.getUTCFullYear();
  const candidates = [...seasonStartsForYear(seasons, year - 1), ...seasonStartsForYear(seasons, year)];
  let current = null;
  for (const candidate of candidates) {
    if (candidate.startDate <= date) current = candidate;
  }
  return current;
}

/** The date the fortnight is anchored on: the startDayKey's weekday on or before the season start,
 *  so a calendar weekday always carries a day key of the same weekday (a no-op when they already agree). */
export function seasonAnchorDate(startDate, startDayKey) {
  const weekdayShort = startDayKey.split("-")[0];
  const target = WEEKDAY_NAMES.findIndex((name) => name.startsWith(weekdayShort));
  return weekdayOnOrBefore(startDate, target);
}

export function cycleIndexForDate(date, anchorDate, anchorDayKey) {
  const daysSinceAnchor = Math.round((date - anchorDate) / MILLISECONDS_PER_DAY);
  return (((DAY_KEY_ORDER.indexOf(anchorDayKey) + daysSinceAnchor) % CYCLE_LENGTH_DAYS) + CYCLE_LENGTH_DAYS) % CYCLE_LENGTH_DAYS;
}

/** Season-anchored resolution: {dayKey, startDate, season} or null when no season has started by `date`. */
export function dayKeyForDateInSeason(date, seasons) {
  const found = seasonForDate(seasons, date);
  if (found === null) return null;
  const anchorDate = seasonAnchorDate(found.startDate, found.season.startDayKey);
  return { dayKey: DAY_KEY_ORDER[cycleIndexForDate(date, anchorDate, found.season.startDayKey)], startDate: found.startDate, season: found.season };
}

/** The day key by the person's own seasons when one has started by `date`, else by the workbook seasons. */
export function dayKeyForDatePersonFirst(date, personSeasons, workbookSeasons) {
  const resolved = (personSeasons && personSeasons.length ? dayKeyForDateInSeason(date, personSeasons) : null) || dayKeyForDateInSeason(date, workbookSeasons);
  return resolved.dayKey;
}

export function parseIsoDate(text) {
  const [year, month, day] = text.split("-").map(Number);
  return utcDate(year, month - 1, day);
}

export function formatIsoDate(date) {
  return date.toISOString().slice(0, 10);
}

/** Same result shape as scripts/resolve_date.py. epochOverride = {date, dayKey} or null; `seasons` = the
 *  person's own seasons (seasonsFromYearSplit) — used when one of them has started by `date`, else the workbook's. */
export function resolveDate(bundle, date, epochOverride = null, seasons = null) {
  const personCurrent = seasons && seasons.length ? seasonForDate(seasons, date) : null;
  const seasonSource = personCurrent ? "person" : "workbook";
  const seasonList = personCurrent ? seasons : bundle.seasons.seasons;
  const { startDate, season } = seasonForDate(seasonList, date);
  const anchorDate = epochOverride ? parseIsoDate(epochOverride.date) : seasonAnchorDate(startDate, season.startDayKey);
  const anchorDayKey = epochOverride ? epochOverride.dayKey : season.startDayKey;
  const cycleIndex = cycleIndexForDate(date, anchorDate, anchorDayKey);
  const dayKey = DAY_KEY_ORDER[cycleIndex];
  return {
    date: formatIsoDate(date),
    dayKey,
    dayLabel: bundle.days.days[dayKey].label,
    cycleIndex,
    week: bundle.days.days[dayKey].week,
    anchor: epochOverride ? "epoch-override" : "season-start",
    seasonSource,
    season: { id: season.id, name: season.name, startDate: formatIsoDate(startDate), seasonMode: season.seasonMode, focus: season.focus },
  };
}
