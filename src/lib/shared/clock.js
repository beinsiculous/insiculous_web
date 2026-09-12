// Clock times: the data contract is "HH:MM" (24 h); people see 12-hour AM/PM. Mirror of the
// helpers in scripts/fk_core/import_document.py (parse) — keep both in sync.

export const MINUTES_PER_DAY = 24 * 60;

/** Every minutes answer lands on a five-minute mark: a person's unrounded input rounds *up* to the next one
 *  (a 12-minute walk is booked as 15). The questionnaire's sliders already step by this; typed and imported
 *  minutes come through here. Mirror of fk_core.timeconv.round_up_to_grid — keep both in sync. */
export const MINUTE_GRID_MINUTES = 5;

export function roundUpToGrid(minutes, grid = MINUTE_GRID_MINUTES) {
  const value = Number(minutes);
  if (!Number.isFinite(value)) return value;
  return Math.ceil(value / grid) * grid;
}

export function timeStringToMinutes(timeString) {
  const [hours, minutes] = timeString.split(":").map(Number);
  return hours * 60 + minutes;
}

export function minutesToTimeString(minutes) {
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

/** A stored "HH:MM" (24 h, the data contract) shown to a person as 12-hour clock time: "22:00" → "10:00 PM",
 *  "00:30" → "12:30 AM", "12:00" → "12:00 PM". Anything that is not HH:MM comes back unchanged. */
export function formatClockTime(timeString) {
  const match = /^(\d{1,2}):(\d{2})$/.exec(timeString ?? "");
  if (!match) return timeString ?? "";
  const hours24 = Number(match[1]) % 24;
  const period = hours24 < 12 ? "AM" : "PM";
  const hours12 = hours24 % 12 === 0 ? 12 : hours24 % 12;
  return `${hours12}:${match[2]} ${period}`;
}

/** "HH:MM–HH:MM" for people: both ends through formatClockTime. */
export function formatClockRange(start, end) {
  return `${formatClockTime(start)}–${formatClockTime(end)}`;
}

/** A clock time as a person (or their assistant) writes it — "2:00 PM", "2 pm", "14:00", "9:30am" — as
 *  canonical "HH:MM"; null when it is not a clock time. */
export function parseClockTime(text) {
  const match = /^\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])?\.?[Mm]?\.?\s*$/.exec(String(text ?? ""));
  if (!match) return null;
  let hours = Number(match[1]);
  const minutes = Number(match[2] ?? "0");
  const period = match[3] ? match[3].toLowerCase() : null;
  if (minutes > 59) return null;
  if (period) {
    if (hours < 1 || hours > 12) return null;
    hours = (hours % 12) + (period === "p" ? 12 : 0);
  } else if (hours > 23 || match[2] === undefined) {
    return null; // "14" alone is not a time; "14:00" is
  }
  return minutesToTimeString(hours * 60 + minutes);
}

/** A duration as written — "2 h 15 min", "90 min", "1 h", "1.5 h", "45", 45 — as integer minutes; null when unreadable. */
export function parseDuration(text) {
  if (Number.isInteger(text) && text >= 0) return text;
  const source = String(text ?? "").trim().toLowerCase();
  if (/^\d+$/.test(source)) return Number(source);
  const hoursMatch = /(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b/.exec(source);
  const minutesMatch = /(\d+)\s*(?:m|min|mins|minute|minutes)\b/.exec(source);
  if (!hoursMatch && !minutesMatch) return null;
  const leftover = source.replace(hoursMatch?.[0] ?? "", "").replace(minutesMatch?.[0] ?? "", "").replace(/[\s,and]+/g, "");
  if (leftover) return null;
  return Math.round(Number(hoursMatch?.[1] ?? 0) * 60) + Number(minutesMatch?.[1] ?? 0);
}

/** Integer minutes for people: "2 h 15 min", "1 h", "45 min", "0 min". */
export function describeDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (hours && remainder) return `${hours} h ${remainder} min`;
  if (hours) return `${hours} h`;
  return `${remainder} min`;
}

/** Today's date as ISO YYYY-MM-DD in the device's local time (a page's "today", not UTC's). */
export function localTodayIsoDate(now = new Date()) {
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/** Which of `blocks` ({key, start, end}) contains the wall time `time` (HH:MM); wraps past midnight. Null when none.
 *  Twin of tests/champion_reference.py's block_key_for_time, which the resolver's parity suite
 *  compares it against over every minute of the day (tests/test_clock.py). */
export function blockKeyForTime(blocks, time) {
  const minutes = timeStringToMinutes(time);
  for (const block of blocks) {
    const start = timeStringToMinutes(block.start);
    let end = timeStringToMinutes(block.end);
    if (end <= start) end += MINUTES_PER_DAY; // a block that runs past midnight
    if (minutes >= start && minutes < end) return block.key;
    if (minutes + MINUTES_PER_DAY >= start && minutes + MINUTES_PER_DAY < end) return block.key;
  }
  return null;
}
