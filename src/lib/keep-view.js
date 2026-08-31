// Drawing a keep: the DOM builders every keep-fed page shares.
//
// This module exists because the Keep rendering outgrew its first page. keep.astro was the only place
// that drew a keep, so the builders lived in its inline script — but a fortnight, a season card and the year
// wheel are wanted on more than one page, and an inline <script> cannot be imported. The builders are here,
// once, and each page wires them to its own shell.
//
// Framework-free on purpose, like everything the site draws with. The site has no UI framework and no build
// step for its JavaScript (AGENTS.md: KISS, and tsconfig.json excludes src/lib from astro check — the tests
// driving these functions through node are their safety net). A builder here is a function that takes keep
// data and returns a detached element; what a page does with that element is the page's business.
//
// The styles these classes rely on are NOT here: they are global, because this DOM is built with
// document.createElement and Astro's scoped styles cannot reach it. They live in
// src/components/KeepStyles.astro, whose header says why is:global is load-bearing.

/** The colours the year wheel paints its seasons, in the order they are handed out. These are the five
 *  values the old household-keyed map held, kept verbatim because the accessibility gate certified their
 *  contrast on the rendered page — changing a value here is an accessibility change, not a palette tweak. */
export const SEASON_PALETTE = ["#4d7c0f", "#c2410c", "#6d28d9", "#9f1239", "#1d4ed8"];

/** What a slice beyond the palette wears. Neutral by design: running out of colours is a data surprise,
 *  not an error, and a grey slice beside a correct key reads as "one more season", not as a failure. */
export const NEUTRAL_SLICE_COLOUR = "#78716c";

/** One colour per slice, assigned by position of FIRST APPEARANCE rather than by season id. The map this
 *  replaced was keyed to one household's five season ids, which made every other household's wheel grey.
 *  A keep's slices arrive in year order, so position is the household-independent fact to key on; keying on
 *  first appearance (by key, else name) keeps a repeated slice the same colour rather than spending a new
 *  one on it. Returns an array parallel to `slices`. */
export function sliceColours(slices) {
  const positions = new Map();
  for (const slice of slices) {
    const identity = slice?.key ?? slice?.name;
    if (!positions.has(identity)) positions.set(identity, positions.size);
  }
  return slices.map((slice) => SEASON_PALETTE[positions.get(slice?.key ?? slice?.name)] ?? NEUTRAL_SLICE_COLOUR);
}

/** The smallest builder: a tag, an optional class, optional text. Shared by the three panels below. */
export function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

/** One day of the fortnight: heading, focus, meals, appointments, blocks — whatever the day carries. */
export function renderDayPanel(day) {
  const panel = element("section", "panel keep-day");
  panel.appendChild(element("h3", null, day.label ?? day.dayKey));
  if (day.mainFocusLabel) panel.appendChild(element("p", "keep-focus", day.mainFocusLabel));

  const meals = day.meals ?? {};
  const named = [["Brunch", meals.brunch], ["Snack", meals.snack], ["Dinner", meals.dinner]]
    .filter(([, dish]) => typeof dish === "string" && dish.length > 0);
  if (named.length) {
    const list = element("ul", "keep-meals");
    for (const [name, dish] of named) {
      const item = element("li", "keep-meal");
      item.appendChild(element("span", "keep-meal-name muted", name));
      item.appendChild(element("span", "keep-meal-dish", dish));
      list.appendChild(item);
    }
    panel.appendChild(list);
  }

  const appointments = Array.isArray(day.appointments) ? day.appointments : [];
  if (appointments.length) {
    const list = element("ul", "keep-appointments");
    for (const appointment of appointments) {
      const timing = appointment?.timing ?? {};
      const when = timing.timeStart && timing.timeFinished ? ` · ${timing.timeStart}–${timing.timeFinished}` : "";
      list.appendChild(element("li", null, `${appointment?.title ?? "Appointment"}${when}`));
    }
    panel.appendChild(list);
  }

  // Named blocks only. "What a page can draw, it draws" cuts both ways: a block with neither a label nor
  // a key is not a thing to draw, and interpolating it would put the word "undefined" on a television.
  const blocks = (Array.isArray(day.blocks) ? day.blocks : [])
    .map((block) => ({ name: block?.label ?? block?.key, focus: block?.focus }))
    .filter((block) => typeof block.name === "string" && block.name.length > 0);
  if (blocks.length) {
    const list = element("ul", "keep-blocks");
    for (const block of blocks) {
      const focus = typeof block.focus === "string" && block.focus ? ` — ${block.focus}` : "";
      list.appendChild(element("li", "keep-block muted", `${block.name}${focus}`));
    }
    panel.appendChild(list);
  }
  return panel;
}

/** The menu's slots, in the order a day runs. The keep names its own slots — a household may call
 *  brunch "First Meal" — so this orders by KEY and prints the keep's LABEL. Anything the keep carries
 *  under an unknown key still draws, after these, in the order the file gives it. */
const MENU_SLOT_ORDER = ["brunch", "snack", "dinner"];

/** The menu's non-empty slots in the order a day runs. Exported because it is a rule, not drawing:
 *  everything else in this module needs a document, and a rule that cannot be tested without a browser
 *  is a rule nothing checks (tests/test_keep.py drives this through node). */
export function orderedSlots(menu) {
  const slots = (Array.isArray(menu) ? menu : []).filter((slot) => Array.isArray(slot?.entries) && slot.entries.length);
  const rank = (slot) => {
    const position = MENU_SLOT_ORDER.indexOf(slot?.slot);
    return position === -1 ? MENU_SLOT_ORDER.length : position;
  };
  return slots.map((slot, index) => ({ slot, index })) // a stable sort by rank, then by file order
    .sort((left, right) => rank(left.slot) - rank(right.slot) || left.index - right.index)
    .map(({ slot }) => slot);
}

/** The menu regrouped by day key: `[[dayKey, [{slotLabel, dish, kind}, …]], …]`, canonical order first
 *  and anything the order does not know after it, so an unexpected day key shows its dish rather than
 *  losing it silently. `kind` is "cooked" or "leftovers" — one entry produces up to two rows, which is
 *  exactly the fact this view exists to show. A rule, like orderedSlots, and tested like one. */
export function menuByDayKey(menu, dayOrder) {
  const byDay = new Map();
  for (const slot of orderedSlots(menu)) {
    const slotLabel = slot.label ?? slot.slot;
    for (const entry of slot.entries) {
      const dish = entry?.menu ?? "Unnamed dish";
      for (const [dayKey, kind] of [[entry?.cookDay, "cooked"], [entry?.leftoversDay, "leftovers"]]) {
        if (typeof dayKey !== "string" || !dayKey) continue;
        if (!byDay.has(dayKey)) byDay.set(dayKey, []);
        byDay.get(dayKey).push({ slotLabel, dish, kind });
      }
    }
  }
  const known = (Array.isArray(dayOrder) ? dayOrder : []).filter((key) => byDay.has(key));
  const extra = [...byDay.keys()].filter((key) => !known.includes(key));
  return [...known, ...extra].map((dayKey) => [dayKey, byDay.get(dayKey)]);
}

/** By dish: every dish once, with the day it is cooked and the day its leftovers land.
 *
 *  This is the view that makes Fork Knife's argument visible — a handful of dishes covering fourteen
 *  days, because most of them are cooked once and eaten twice. A dish with no leftovers day says so
 *  rather than showing a blank: "cooked fresh" is a real answer, not missing data. */
export function renderMenuByDish(menu) {
  const slots = orderedSlots(menu);
  if (!slots.length) return null;
  const panel = element("section", "panel");
  panel.appendChild(element("h2", null, "By dish"));
  for (const slot of slots) {
    panel.appendChild(element("h3", "keep-menu-slot", slot.label ?? slot.slot));
    const list = element("ul", "keep-menu-dishes");
    for (const entry of slot.entries) {
      const item = element("li", "keep-menu-dish");
      item.appendChild(element("span", "keep-menu-name", entry?.menu ?? "Unnamed dish"));
      const cook = entry?.cookDayLabel ?? entry?.cookDay;
      const leftovers = entry?.leftoversDayLabel ?? entry?.leftoversDay;
      const when = cook
        ? (leftovers ? `Cooked ${cook}, again ${leftovers}` : `Cooked ${cook}, no leftovers`)
        : "No cook day recorded";
      item.appendChild(element("span", "keep-menu-when muted", when));
      // The note is the household's own sentence about why extra is made; it is worth the room.
      if (entry?.cookExtra && typeof entry.cookExtraNote === "string" && entry.cookExtraNote) {
        item.appendChild(element("span", "keep-menu-note muted", entry.cookExtraNote));
      } else if (entry?.cookExtra) {
        item.appendChild(element("span", "keep-menu-note muted", "Extra is made."));
      }
      list.appendChild(item);
    }
    panel.appendChild(list);
  }
  return panel;
}

/** By day: the fourteen days in canonical order, each with what is eaten and whether it is cooked
 *  that day or is the leftovers of another.
 *
 *  Built from the menu section rather than from each day's own `meals`, because the two say different
 *  things: `day.meals` is what is eaten, and this is where it came from. `dayOrder` is passed in
 *  rather than imported so this module keeps drawing and nothing else — the caller already knows the
 *  canonical order. Days the menu never mentions are skipped, not drawn empty. */
export function renderMenuByDay(menu, dayOrder, labelForDayKey = (key) => key) {
  const days = menuByDayKey(menu, dayOrder);
  if (!days.length) return null;
  const panel = element("section", "panel");
  panel.appendChild(element("h2", null, "By day"));
  const grid = element("div", "keep-menu-grid");
  for (const [dayKey, meals] of days) {
    const cell = element("div", "keep-menu-day");
    cell.appendChild(element("h3", null, labelForDayKey(dayKey)));
    const list = element("ul", "keep-menu-meals");
    for (const { slotLabel, dish, kind } of meals) {
      const item = element("li", kind === "leftovers" ? "keep-menu-meal keep-menu-again" : "keep-menu-meal");
      item.appendChild(element("span", "keep-menu-name muted", slotLabel));
      item.appendChild(element("span", null, dish));
      if (kind === "leftovers") item.appendChild(element("span", "keep-menu-when muted", "again"));
      list.appendChild(item);
    }
    cell.appendChild(list);
    grid.appendChild(cell);
  }
  panel.appendChild(grid);
  return panel;
}

/** The season card: name, range, how much of the day is safe outside, and what is in season. */
export function renderSeasonPanel(season) {
  const panel = element("section", "panel");
  panel.appendChild(element("h2", null, season.name ?? "This season"));
  if (season.gregorianRange) panel.appendChild(element("p", "muted", season.gregorianRange));
  if (typeof season.safeOutsidePercent === "number") {
    panel.appendChild(element("p", null, `${Math.round(season.safeOutsidePercent)}% of the day is safe outside.`));
  }
  const produce = Array.isArray(season.produce) ? season.produce : [];
  for (const group of produce) {
    const items = (group?.items ?? []).map((item) => item?.name).filter(Boolean);
    const label = typeof group?.label === "string" && group.label ? `${group.label}: ` : "";
    if (items.length) panel.appendChild(element("p", null, `${label}${items.join(", ")}`));
  }
  return panel;
}

/** A slice worth drawing: a name, and two degrees that are really numbers. One bad value would otherwise
 *  put "NaNdeg" in the gradient, and a browser drops an invalid declaration whole — a blank disc beside a
 *  correct key, which reads as a rendering bug rather than as missing data. */
function drawableSlices(year) {
  return (Array.isArray(year?.slices) ? year.slices : [])
    .map((slice) => ({
      key: slice?.key,
      name: slice?.name ?? slice?.key,
      percent: Number(slice?.percent),
      startDegree: Number(slice?.startDegree),
      sweepDegree: Number(slice?.sweepDegree),
      isCurrent: Boolean(slice?.isCurrent),
    }))
    .filter((slice) => typeof slice.name === "string" && slice.name.length > 0
      && Number.isFinite(slice.startDegree) && Number.isFinite(slice.sweepDegree));
}

/** The year wheel and its key, or null when the year has nothing drawable — a wheel with no slices is
 *  not a panel at all, and the caller draws the rest of the keep without it. */
export function renderYearPanel(year) {
  const slices = drawableSlices(year);
  if (!slices.length) return null;
  const colours = sliceColours(slices);
  const panel = element("section", "panel");
  panel.appendChild(element("h2", null, `${year.year}`));

  const row = element("div", "keep-wheel-row");
  // conic-gradient IS the wheel here. Fort Knight draws it from nested rotated Views because React Native has
  // no such thing; a browser does, and the keep already carries the degrees, so there is nothing to
  // compute. Decorative: the same numbers are in the list beside it, which is what a reader gets.
  const stops = slices
    .map((slice, index) => `${colours[index]} ${slice.startDegree}deg ${slice.startDegree + slice.sweepDegree}deg`)
    .join(", ");
  const wheel = element("div", "keep-wheel");
  wheel.style.background = `conic-gradient(${stops})`;
  wheel.setAttribute("role", "presentation");
  row.appendChild(wheel);

  const key = element("ul", "keep-key");
  for (const [index, slice] of slices.entries()) {
    const item = element("li");
    const swatch = element("span", "keep-swatch");
    swatch.style.background = colours[index];
    item.appendChild(swatch);
    const share = Number.isFinite(slice.percent) ? ` — ${slice.percent}%` : "";
    item.appendChild(element("span", null, `${slice.name}${share}${slice.isCurrent ? " (now)" : ""}`));
    key.appendChild(item);
  }
  row.appendChild(key);
  panel.appendChild(row);
  if (year.coversWholeYear === false) {
    panel.appendChild(element("p", "muted",
      `This keep covers ${year.daysCovered} of ${year.year}'s ${year.daysInYear} days.`));
  }
  return panel;
}
