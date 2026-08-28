// Drawing a My Fort seed: the DOM builders every seed-fed page shares.
//
// This module exists because the My Fort rendering outgrew its first page. myfort.astro was the only place
// that drew a seed, so the builders lived in its inline script — but a fortnight, a season card and the year
// wheel are wanted on more than one page, and an inline <script> cannot be imported. The builders are here,
// once, and each page wires them to its own shell.
//
// Framework-free on purpose, like everything the site draws with. The site has no UI framework and no build
// step for its JavaScript (AGENTS.md: KISS, and tsconfig.json excludes src/lib from astro check — the tests
// driving these functions through node are their safety net). A builder here is a function that takes seed
// data and returns a detached element; what a page does with that element is the page's business.
//
// The styles these classes rely on are NOT here: they are global, because this DOM is built with
// document.createElement and Astro's scoped styles cannot reach it. They live in
// src/components/MyFortStyles.astro, whose header says why is:global is load-bearing.

/** The colours the year wheel paints its seasons, in the order they are handed out. These are the five
 *  values the old household-keyed map held, kept verbatim because the accessibility gate certified their
 *  contrast on the rendered page — changing a value here is an accessibility change, not a palette tweak. */
export const SEASON_PALETTE = ["#4d7c0f", "#c2410c", "#6d28d9", "#9f1239", "#1d4ed8"];

/** What a slice beyond the palette wears. Neutral by design: running out of colours is a data surprise,
 *  not an error, and a grey slice beside a correct key reads as "one more season", not as a failure. */
export const NEUTRAL_SLICE_COLOUR = "#78716c";

/** One colour per slice, assigned by position of FIRST APPEARANCE rather than by season id. The map this
 *  replaced was keyed to one household's five season ids, which made every other household's wheel grey.
 *  A seed's slices arrive in year order, so position is the household-independent fact to key on; keying on
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
  const panel = element("section", "panel myfort-day");
  panel.appendChild(element("h3", null, day.label ?? day.dayKey));
  if (day.mainFocusLabel) panel.appendChild(element("p", "myfort-focus", day.mainFocusLabel));

  const meals = day.meals ?? {};
  const named = [["Brunch", meals.brunch], ["Snack", meals.snack], ["Dinner", meals.dinner]]
    .filter(([, dish]) => typeof dish === "string" && dish.length > 0);
  if (named.length) {
    const list = element("ul", "myfort-meals");
    for (const [name, dish] of named) {
      const item = element("li", "myfort-meal");
      item.appendChild(element("span", "myfort-meal-name muted", name));
      item.appendChild(element("span", "myfort-meal-dish", dish));
      list.appendChild(item);
    }
    panel.appendChild(list);
  }

  const appointments = Array.isArray(day.appointments) ? day.appointments : [];
  if (appointments.length) {
    const list = element("ul", "myfort-appointments");
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
    const list = element("ul", "myfort-blocks");
    for (const block of blocks) {
      const focus = typeof block.focus === "string" && block.focus ? ` — ${block.focus}` : "";
      list.appendChild(element("li", "myfort-block muted", `${block.name}${focus}`));
    }
    panel.appendChild(list);
  }
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
 *  not a panel at all, and the caller draws the rest of the seed without it. */
export function renderYearPanel(year) {
  const slices = drawableSlices(year);
  if (!slices.length) return null;
  const colours = sliceColours(slices);
  const panel = element("section", "panel");
  panel.appendChild(element("h2", null, `${year.year}`));

  const row = element("div", "myfort-wheel-row");
  // conic-gradient IS the wheel here. Focus Key draws it from nested rotated Views because React Native has
  // no such thing; a browser does, and the seed already carries the degrees, so there is nothing to
  // compute. Decorative: the same numbers are in the list beside it, which is what a reader gets.
  const stops = slices
    .map((slice, index) => `${colours[index]} ${slice.startDegree}deg ${slice.startDegree + slice.sweepDegree}deg`)
    .join(", ");
  const wheel = element("div", "myfort-wheel");
  wheel.style.background = `conic-gradient(${stops})`;
  wheel.setAttribute("role", "presentation");
  row.appendChild(wheel);

  const key = element("ul", "myfort-key");
  for (const [index, slice] of slices.entries()) {
    const item = element("li");
    const swatch = element("span", "myfort-swatch");
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
      `This seed covers ${year.daysCovered} of ${year.year}'s ${year.daysInYear} days.`));
  }
  return panel;
}
