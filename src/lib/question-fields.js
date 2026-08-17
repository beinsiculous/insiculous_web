// The questionnaire fields both questionnaire pages render through components/QuestionField.astro — the simple kinds
// (number, multi-select, single-select, text) and the meals editor: reading a question's answer out of the form and
// writing one back in. FortKnight's bespoke kinds (sliders, commitments, year split, waking window …) stay in its page.
import { mealsWithDefaults } from "./shared/weights-rules.js";

export function checkedValues(form, name) {
  return [...form.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value);
}

export function setChecked(form, name, values) {
  for (const input of form.querySelectorAll(`input[name="${name}"]`)) input.checked = values.includes(input.value);
}

/** The answer of a number / multi-select / single-select / text question (`fallback` when nothing is picked). */
export function readSimpleAnswer(form, question, fallback = undefined) {
  switch (question.kind) {
    case "number": return Number(form.elements[question.id].value) || fallback || question.min || 1;
    case "multi-select": return checkedValues(form, question.id);
    case "single-select": return form.querySelector(`input[name="${question.id}"]:checked`)?.value ?? fallback;
    case "text": return form.elements[question.id].value.trim();
    default: throw new Error(`readSimpleAnswer: ${question.kind} is not a simple kind`);
  }
}

export function populateSimpleAnswer(form, question, value) {
  switch (question.kind) {
    case "number": form.elements[question.id].value = value ?? question.default ?? question.min ?? 1; return;
    case "multi-select": setChecked(form, question.id, value || []); return;
    case "single-select": setChecked(form, question.id, value === undefined || value === null ? [] : [value]); return;
    case "text": form.elements[question.id].value = value || ""; return;
    default: throw new Error(`populateSimpleAnswer: ${question.kind} is not a simple kind`);
  }
}

// ----- the meals editor (kind "meals"): count, and per meal its name, times of day, prep / cook toggles + minutes -----
function mealRows(form) {
  return [...form.querySelectorAll(".meal-row")];
}

/** The meals answer as edited: `{perDay, meals: [{name, slots, needsPrepped, needsCooked, prepMinutes, cookMinutes}]}`. */
export function readMeals(form) {
  const perDay = Number(form.mealsPerDay.value);
  const meals = [];
  for (let index = 0; index < perDay; index += 1) {
    meals.push({
      name: form.elements[`mealName-${index}`].value.trim() || `Meal ${index + 1}`,
      slots: checkedValues(form, `mealSlots-${index}`),
      needsPrepped: form.elements[`mealPrepped-${index}`].checked,
      needsCooked: form.elements[`mealCooked-${index}`].checked,
      prepMinutes: Number(form.elements[`mealPrepMinutes-${index}`].value),
      cookMinutes: Number(form.elements[`mealCookMinutes-${index}`].value),
    });
  }
  return { perDay, meals };
}

export function populateMeals(form, mealsAnswer, questionnaire) {
  const meals = mealsWithDefaults(mealsAnswer || { perDay: questionnaire.mealsPerDay.default, meals: [] }, questionnaire);
  form.mealsPerDay.value = meals.perDay;
  const mealPrep = questionnaire.mealPrep;
  for (const row of mealRows(form)) {
    const index = Number(row.dataset.mealIndex);
    const meal = meals.meals[index] || {};
    form.elements[`mealName-${index}`].value = meal.name || "";
    setChecked(form, `mealSlots-${index}`, meal.slots || ["anytime"]);
    form.elements[`mealPrepped-${index}`].checked = Boolean(meal.needsPrepped);
    form.elements[`mealCooked-${index}`].checked = Boolean(meal.needsCooked);
    form.elements[`mealPrepMinutes-${index}`].value = meal.prepMinutes ?? mealPrep.defaultPrepMinutes;
    form.elements[`mealCookMinutes-${index}`].value = meal.cookMinutes ?? mealPrep.defaultCookMinutes;
  }
  updateMealRows(form);
}

/** Only the first `mealsPerDay` rows show; each row's sliders follow its toggles. */
export function updateMealRows(form) {
  const count = Number(form.mealsPerDay.value);
  for (const row of mealRows(form)) {
    row.hidden = Number(row.dataset.mealIndex) >= count;
    updateMealPrepCells(form, row);
  }
}

/** A meal's minute sliders follow its toggles: enabled and shown only while the meal needs prepping / cooking. */
export function updateMealPrepCells(form, row) {
  const index = row.dataset.mealIndex;
  for (const [toggle, slider] of [[`mealPrepped-${index}`, `mealPrepMinutes-${index}`], [`mealCooked-${index}`, `mealCookMinutes-${index}`]]) {
    const on = form.elements[toggle].checked;
    const range = form.elements[slider];
    range.disabled = !on;
    range.closest("label").hidden = !on;
    range.nextElementSibling.textContent = `${range.value} min`;
  }
}

/** Wire the meals editor: the count shows/hides rows, toggles and sliders redraw their cell, and each meal keeps
 *  between slotsPerMeal.min and .max times of day ticked (a tick past the max is refused, the last one cannot be
 *  unticked). `onMealsChange(previousMeals, currentMeals)` fires after any edit with the meals before and after.
 *  Returns `resync()` — call it after populating the editor so "before" is what was populated, not an older state. */
export function wireMealsEditor(form, questionnaire, onMealsChange = () => {}) {
  let previous = readMeals(form);
  const resync = () => { previous = readMeals(form); };
  const announce = () => { const current = readMeals(form); onMealsChange(previous, current); previous = current; };
  form.mealsPerDay.addEventListener("change", () => { updateMealRows(form); announce(); });
  const bounds = questionnaire.slotsPerMeal;
  for (const row of mealRows(form)) {
    row.addEventListener("input", (event) => {
      if (event.target.type === "checkbox" && event.target.name.startsWith("mealSlots-")) {
        const chosen = checkedValues(form, event.target.name);
        if (chosen.length > bounds.max) { event.target.checked = false; return; }
        if (chosen.length < bounds.min) { event.target.checked = true; return; }
      }
      if (event.target.type === "checkbox" || event.target.type === "range") updateMealPrepCells(form, row);
      announce();
    });
  }
  return resync;
}
