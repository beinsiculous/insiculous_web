// The fortnight menu editor (docs/meal-plan.md), shared by ForkKnife's Spoon Feed page and FortKnight's Build page:
// one section per meal — a coverage line, the committed dishes (Edit reveals the remove buttons) and one entry row
// (dish, first day, leftovers day, Add). Every rule it enforces lives in app/shared/meal-plan.js; this module only
// draws it and hands back the edited items. Mount it once, then `setMeals` / `setItems` and `render`.
import { allowedSecondDays, canTakeLeftovers, coverage, dayLabel, itemServings, mealSlug, normalizeMealPlan } from "./shared/meal-plan.js";

function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/** `container` is the element the meal sections are drawn into; `dayOptions` is [{dayKey, label}] in cycle order.
 *  `onChange()` fires after every edit that changes the items. */
export function mountMealPlanEditor(container, { dayOptions, onChange = () => {} } = {}) {
  let meals = [];
  let items = [];
  const editing = {}; // meal slug -> whether its list shows the remove buttons

  function committedList(meal, slug) {
    const list_ = element("div", "committed-list");
    const mine = items.filter((item) => item.meal === slug);
    if (!mine.length) {
      list_.appendChild(element("p", "muted committed-empty", `No ${meal.name.toLowerCase()} dishes yet.`));
      return list_;
    }
    const header = element("div", "committed-header");
    header.appendChild(element("span", "muted", `${mine.length} dish${mine.length === 1 ? "" : "es"}`));
    const toggle = element("button", "link-button", editing[slug] ? "Done" : "Edit");
    toggle.type = "button";
    toggle.addEventListener("click", () => { editing[slug] = !editing[slug]; render(); });
    header.appendChild(toggle);
    list_.appendChild(header);
    const lines = element("ul", `committed-items${editing[slug] ? " editing" : ""}`);
    for (const item of mine) {
      const line = element("li");
      line.appendChild(element("strong", null, item.dish));
      const leftoversAs = item.leftoversMeal ? ` as ${meals.find((other) => mealSlug(other.name) === item.leftoversMeal)?.name ?? item.leftoversMeal}` : "";
      line.append(` · ${item.days.map(dayLabel).join(" + ")}${item.days.length === 2 ? ` (leftovers${leftoversAs})` : ""}${item.notes ? ` — ${item.notes}` : ""}`);
      if (editing[slug]) {
        const remove = element("button", "remove-committed", "×");
        remove.type = "button";
        remove.title = `Remove ${item.dish}`;
        remove.addEventListener("click", () => { items = items.filter((other) => other.id !== item.id); onChange(); render(); });
        line.appendChild(remove);
      }
      lines.appendChild(line);
    }
    list_.appendChild(lines);
    return list_;
  }

  function entryRow(meal, slug) {
    const row = element("div", "meal-entry-row");
    // A meal is eaten once a day: (meal, day) servings already in the plan leave the dropdowns.
    const takenServings = new Set(items.flatMap((item) => itemServings(item).map(([servingMeal, day]) => `${servingMeal}|${day}`)));
    const isTaken = (servingMeal, dayKey) => takenServings.has(`${servingMeal}|${dayKey}`);
    const freeDays = dayOptions.filter(({ dayKey }) => !isTaken(slug, dayKey));
    if (!freeDays.length) {
      row.appendChild(element("span", "muted", `Every day has its ${meal.name.toLowerCase()} — remove a dish to change one.`));
      return row;
    }
    const dish = document.createElement("input");
    dish.type = "text";
    dish.placeholder = `${meal.name} dish`;
    dish.setAttribute("aria-label", `${meal.name} dish`);
    const firstDay = document.createElement("select");
    firstDay.setAttribute("aria-label", `${meal.name}: first day`);
    for (const { dayKey, label } of freeDays) firstDay.appendChild(new Option(label, dayKey));
    const secondDay = document.createElement("select");
    secondDay.setAttribute("aria-label", `${meal.name}: leftovers day`);
    // Leftovers: the same meal on an allowed later day, or — from an afternoon/evening/late-evening meal — another
    // early-morning/mid-morning/afternoon meal on such a day (value "day|meal").
    const fillSecondDays = () => {
      secondDay.replaceChildren(new Option("No leftovers", ""));
      for (const dayKey of allowedSecondDays(firstDay.value)) {
        if (!isTaken(slug, dayKey)) secondDay.appendChild(new Option(`leftovers ${dayLabel(dayKey)}`, `${dayKey}|${slug}`));
        for (const other of meals) {
          const otherSlug = mealSlug(other.name);
          if (otherSlug === slug || !canTakeLeftovers(meal, other) || isTaken(otherSlug, dayKey)) continue;
          secondDay.appendChild(new Option(`leftovers ${dayLabel(dayKey)} as ${other.name}`, `${dayKey}|${otherSlug}`));
        }
      }
    };
    fillSecondDays();
    firstDay.addEventListener("change", fillSecondDays);
    const add = element("button", null, "Add");
    add.type = "button";
    const rowStatus = element("span", "muted");
    const commit = () => {
      const [secondDayKey, leftoversSlug] = secondDay.value ? secondDay.value.split("|") : [null, null];
      const days = [firstDay.value, ...(secondDayKey ? [secondDayKey] : [])];
      const candidate = { items: [...items, { meal: meal.name, dish: dish.value, days, leftoversMeal: leftoversSlug && leftoversSlug !== slug ? leftoversSlug : null }] };
      const { normalized, problems } = normalizeMealPlan(candidate, meals);
      if (!dish.value.trim()) { rowStatus.textContent = "Give the dish a name first."; return; }
      if (problems.length) { const problem = problems[problems.length - 1]; rowStatus.textContent = `${problem[0].toUpperCase()}${problem.slice(1)}.`; return; }
      items = normalized.items;
      rowStatus.textContent = "";
      dish.value = "";
      onChange();
      render();
      container.querySelector(`[data-focus-meal="${slug}"] input`)?.focus();
    };
    add.addEventListener("click", commit);
    dish.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); commit(); } });
    row.dataset.focusMeal = slug;
    row.append(dish, firstDay, secondDay, add, rowStatus);
    return row;
  }

  /** One section per meal: coverage line, the committed list (Edit → remove), one entry row. */
  function render() {
    container.replaceChildren();
    for (const meal of meals) {
      const slug = mealSlug(meal.name);
      const section = element("div", "meal-plan-section");
      const heading = element("h3", "editor-heading");
      const covered = coverage(items, slug);
      heading.textContent = `${meal.name}`;
      heading.appendChild(element("span", "muted", ` · ${covered.dishes} dish${covered.dishes === 1 ? "" : "es"} · ${covered.covered}/14 days${covered.missing.length && covered.missing.length < 14 ? ` — missing: ${covered.missing.map(dayLabel).join(", ")}` : ""}`));
      section.appendChild(heading);
      section.appendChild(committedList(meal, slug));
      section.appendChild(entryRow(meal, slug));
      container.appendChild(section);
    }
  }

  return {
    setMeals(nextMeals) { meals = nextMeals; },
    setItems(nextItems) { items = nextItems; },
    getItems() { return JSON.parse(JSON.stringify(items)); },
    render,
  };
}
