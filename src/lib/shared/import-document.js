// The import document (docs/importers.md, data/schema/import.schema.json): a person's existing system —
// as their assistant read it — in a shape the person can check. Version 2 is written for the reader
// ("repeats": "monthly on the 2nd tuesday", "start": "7:00 PM", "lasts": "2 h"); this module turns it
// into the canonical objects the rest of the app consumes (standing appointments, tasks). Pure port
// of scripts/fk_core/import_document.py — keep both in sync (tests/test_import_document.py).
import { WEEKDAY_NAMES } from "./fortknight-rules.js";
import { describeDuration, formatClockTime, parseClockTime, parseDuration, roundUpToGrid } from "./clock.js";

export const IMPORT_SCHEMA_VERSIONS = [1, 2];
export const SOURCE_KINDS = ["text", "photo", "xlsx", "ics", "google-calendar", "other"];
/** A task's time-of-day word -> the clock time it is placed by (the block containing it, docs/importers.md). */
export const TIME_OF_DAY_MINUTES = { morning: "09:00", midday: "12:00", afternoon: "15:00", evening: "19:00", night: "21:00" };
export const TIME_OF_DAY_WORDS = [...Object.keys(TIME_OF_DAY_MINUTES), "anytime"];
const ORDINALS = { "1st": 1, first: 1, "2nd": 2, second: 2, "3rd": 3, third: 3, "4th": 4, fourth: 4, last: -1 };
const ORDINAL_WORDS = { 1: "1st", 2: "2nd", 3: "3rd", 4: "4th", "-1": "last" };

function tidy(text) {
  return String(text ?? "").trim().toLowerCase().replace(/\s+/g, " ");
}

function capitalize(word) {
  return word ? word[0].toUpperCase() + word.slice(1) : word;
}

/** "Mon", "monday", "Tuesdays" -> the weekday id; null when unknown. */
export function resolveWeekday(text) {
  const word = tidy(text).replace(/s$/, "");
  if (word.length < 3) return null;
  return WEEKDAY_NAMES.find((weekday) => weekday === word || weekday.startsWith(word)) ?? null;
}

/** A category as a key ("friends-family") or a label ("Friends & Family", "spirituality and development")
 *  -> the key; null when unknown. `categories` is the bundle's categories.json object (optional: keys only). */
export function resolveCategory(text, categories = null) {
  const wanted = tidy(text);
  if (!wanted) return null;
  const keys = categories?.order ?? [];
  for (const key of keys) {
    const label = tidy(categories.categories[key]?.label);
    const candidates = [key, label, label.replace(/&/g, "and"), label.replace(/\s*&\s*/g, "-"), label.replace(/\s*&\s*/g, " and ")];
    if (candidates.includes(wanted) || candidates.includes(wanted.replace(/-/g, " "))) return key;
  }
  if (!categories && /^[a-z0-9]+(-[a-z0-9]+)*$/.test(wanted)) return wanted;
  return null;
}

/** The `repeats` phrase of a version-2 commitment or task -> { cadence, weekdays? } or { problem }:
 *  "every week" · "every other week from YYYY-MM-DD" · "monthly on the 2nd tuesday" · "monthly on day 15" ·
 *  "once on YYYY-MM-DD" (case-insensitive; "monthly on the last friday" and "monthly on the 15th" also read). */
export function parseRepeats(phrase) {
  const text = tidy(phrase);
  if (text === "every week" || text === "weekly") return { cadence: { kind: "weekly" } };
  let match = /^every other week(?: (?:from|starting|since) (\d{4}-\d{2}-\d{2}))?$/.exec(text);
  if (match) {
    if (!match[1]) return { problem: 'every other week needs a date: "every other week from YYYY-MM-DD"' };
    return { cadence: { kind: "every-other-week", firstDate: match[1] } };
  }
  match = /^monthly on the (1st|first|2nd|second|3rd|third|4th|fourth|last) ([a-z]+)$/.exec(text);
  if (match) {
    const weekday = resolveWeekday(match[2]);
    if (!weekday) return { problem: `unknown weekday "${match[2]}" in "${phrase}"` };
    return { cadence: { kind: "monthly-nth-weekday", nth: ORDINALS[match[1]] }, weekdays: [weekday] };
  }
  match = /^monthly on (?:day |the )?(\d{1,2})(?:st|nd|rd|th)?$/.exec(text);
  if (match) {
    const dayOfMonth = Number(match[1]);
    if (dayOfMonth < 1 || dayOfMonth > 31) return { problem: `day of month must be 1–31 in "${phrase}"` };
    return { cadence: { kind: "monthly-date", dayOfMonth } };
  }
  match = /^(?:once|one-off|one off)(?: on)? (\d{4}-\d{2}-\d{2})$/.exec(text);
  if (match) return { cadence: { kind: "one-off", date: match[1] } };
  return { problem: `cannot read "${phrase}" — use "every week", "every other week from YYYY-MM-DD", "monthly on the 2nd tuesday", "monthly on day 15" or "once on YYYY-MM-DD"` };
}

/** The canonical cadence + weekdays back as a phrase for people: "every week on Mondays and Thursdays". */
export function describeCadence(cadence, weekdays = []) {
  const days = describeWeekdays(weekdays);
  switch (cadence?.kind) {
    case "weekly": return `every week${days ? ` on ${days}` : ""}`;
    case "every-other-week": return `every other week${days ? ` on ${days}` : ""} from ${cadence.firstDate}`;
    case "monthly-nth-weekday": return `monthly on the ${ORDINAL_WORDS[String(cadence.nth)] ?? cadence.nth} ${weekdays.map(capitalize).join(" / ") || "weekday"}`;
    case "monthly-date": return `monthly on day ${cadence.dayOfMonth}`;
    case "one-off": return `once on ${cadence.date}`;
    default: return "";
  }
}

export function describeWeekdays(weekdays) {
  const names = (weekdays || []).map((weekday) => `${capitalize(weekday)}s`);
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** One readable commitment or task -> the canonical record, or a problem string. Shared by both lists:
 *  a commitment needs a `start`; a task may carry `when` (a time-of-day word) or a `start`. */
function readItem(item, categories, { needsStart, allowWhen }) {
  if (!item || typeof item !== "object") return { problem: "not an object" };
  const title = String(item.title ?? "").trim();
  if (!title) return { problem: "needs a title" };
  const repeats = parseRepeats(item.repeats);
  if (repeats.problem) return { problem: repeats.problem };
  const listedWeekdays = Array.isArray(item.weekdays) ? item.weekdays : (item.weekdays ? [item.weekdays] : []);
  const weekdays = [];
  for (const entry of listedWeekdays) {
    const weekday = resolveWeekday(entry);
    if (!weekday) return { problem: `unknown weekday ${JSON.stringify(entry)}` };
    if (!weekdays.includes(weekday)) weekdays.push(weekday);
  }
  for (const weekday of repeats.weekdays ?? []) if (!weekdays.includes(weekday)) weekdays.push(weekday);
  const start = item.start === undefined || item.start === null || item.start === "" ? null : parseClockTime(item.start);
  if (item.start && !start) return { problem: `cannot read the start time ${JSON.stringify(item.start)} — write it like "2:00 PM" or "14:00"` };
  if (needsStart && !start) return { problem: "needs a start time" };
  const timeOfDay = allowWhen && item.when ? tidy(item.when) : null;
  if (timeOfDay && !TIME_OF_DAY_WORDS.includes(timeOfDay)) return { problem: `unknown time of day ${JSON.stringify(item.when)} — one of ${TIME_OF_DAY_WORDS.join(", ")}` };
  const durationMinutes = item.lasts === undefined || item.lasts === null || item.lasts === "" ? (needsStart ? null : 0) : parseDuration(item.lasts);
  if (durationMinutes === null) return { problem: needsStart && item.lasts === undefined ? "needs how long it lasts" : `cannot read the duration ${JSON.stringify(item.lasts)} — write it like "1 h 30 min" or "45 min"` };
  const category = resolveCategory(item.category, categories);
  if (!category) return { problem: `unknown category ${JSON.stringify(item.category)}` };
  const record = { title, weekdays, cadence: repeats.cadence, category };
  if (start) record.start = start;
  record.durationMinutes = roundUpToGrid(durationMinutes); // an assistant's "37 min" books as 40
  if (allowWhen) record.timeOfDay = timeOfDay ?? (start ? null : "anytime");
  if (typeof item.from === "string" && item.from.trim()) record.from = item.from.trim();
  return { record };
}

/** A version-2 commitment -> the canonical standing appointment ({title, weekdays, start, durationMinutes, category, cadence}). */
export function commitmentToStandingAppointment(commitment, categories = null) {
  const read = readItem(commitment, categories, { needsStart: true, allowWhen: false });
  if (read.problem) return read;
  const { title, weekdays, start, durationMinutes, category, cadence } = read.record;
  return { record: { title, weekdays, start, durationMinutes, category, cadence } };
}

/** A version-2 task -> the canonical task ({title, weekdays, cadence, timeOfDay, start?, durationMinutes, category, from?}). */
export function taskToRecord(task, categories = null) {
  return readItem(task, categories, { needsStart: false, allowWhen: true });
}

/** Any supported import document -> a normalized copy the app reads: version 1 passes through (plus an
 *  empty `tasks`); version 2's readable `commitments` become canonical `standingAppointments` (appended
 *  to any it already carries) and its `tasks` canonical task records. `skipped`, `review`, `notes` and
 *  the machine sections travel unchanged. Returns { document, problems } — a problem names the list and
 *  the item ("commitments #2 'Choir': …"); the item is left out. The stored document is never this copy:
 *  the app keeps what was pasted and normalizes on read. */
export function normalizeImportDocument(document, categories = null) {
  const problems = [];
  if (!document || typeof document !== "object") return { document: { schemaVersion: null, standingAppointments: [], tasks: [] }, problems: ["not an import document"] };
  const normalized = JSON.parse(JSON.stringify(document));
  normalized.standingAppointments = [...(document.standingAppointments || [])];
  normalized.tasks = [];
  if (!IMPORT_SCHEMA_VERSIONS.includes(document.schemaVersion)) {
    problems.push(`schemaVersion ${JSON.stringify(document.schemaVersion)} is not supported (${IMPORT_SCHEMA_VERSIONS.join(" or ")})`);
    return { document: normalized, problems };
  }
  if (document.schemaVersion >= 2) {
    (document.commitments || []).forEach((commitment, index) => {
      const read = commitmentToStandingAppointment(commitment, categories);
      if (read.problem) problems.push(`commitments #${index + 1} ${JSON.stringify(commitment?.title ?? "")}: ${read.problem}`);
      else normalized.standingAppointments.push(read.record);
    });
    (document.tasks || []).forEach((task, index) => {
      const read = taskToRecord(task, categories);
      if (read.problem) problems.push(`tasks #${index + 1} ${JSON.stringify(task?.title ?? "")}: ${read.problem}`);
      else normalized.tasks.push(read.record);
    });
  }
  return { document: normalized, problems };
}

/** The review a person reads after Apply: readable rows for what the document carries. */
export function importReviewRows(document, categories = null) {
  const { document: normalized, problems } = normalizeImportDocument(document, categories);
  const label = (key) => categories?.categories?.[key]?.label ?? key;
  return {
    commitments: normalized.standingAppointments.map((appointment) => ({
      title: appointment.title,
      repeats: describeCadence(appointment.cadence, appointment.weekdays),
      start: formatClockTime(appointment.start),
      lasts: describeDuration(appointment.durationMinutes),
      category: label(appointment.category),
    })),
    tasks: normalized.tasks.map((task) => ({
      title: task.title,
      repeats: describeCadence(task.cadence, task.weekdays),
      when: task.start ? formatClockTime(task.start) : task.timeOfDay,
      lasts: task.durationMinutes ? describeDuration(task.durationMinutes) : "",
      category: label(task.category),
    })),
    skipped: (document?.skipped || []).map((entry) => ({ title: String(entry?.title ?? ""), why: String(entry?.why ?? "") })),
    review: [...(document?.review || [])].map(String),
    notes: [...(document?.notes || [])].map(String),
    problems,
  };
}
