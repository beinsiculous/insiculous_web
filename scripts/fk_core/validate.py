"""Validation of canonical data: a small JSON-Schema subset checker plus referential rules.

Supported schema keywords (enough for data/schema/*.schema.json): type, enum, const, properties,
required, additionalProperties, items, minItems, maxItems, minimum, maximum, pattern.
Everything else in the schema files is documentation for humans/LLMs/editors.
"""
import re

from . import import_document, keys, meal_plan
from .astronomy import SOLAR_TERM_ORDER
from .dates import NEW_MOON_MAX_INDEX, NTH_OCCURRENCES, SNAP_DIRECTIONS, START_RULE_KINDS, parse_iso_date, start_date_for_rule
from .json_io import SCHEMA_DIRECTORY, read_json
from .timeconv import time_string_to_minutes
from .weights import section_days_from_year_split

JSON_TYPE_CHECKS = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}


class ValidationReport:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, message):
        self.errors.append(message)

    def warning(self, message):
        self.warnings.append(message)

    @property
    def ok(self):
        return not self.errors

    def render(self):
        lines = [f"ERROR   {message}" for message in self.errors]
        lines += [f"WARNING {message}" for message in self.warnings]
        lines.append(f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return "\n".join(lines)


def check_schema(value, schema, path, report):
    """Recursively check `value` against the supported subset of `schema`."""
    expected_types = schema.get("type")
    if expected_types is not None:
        expected_types = [expected_types] if isinstance(expected_types, str) else expected_types
        if not any(JSON_TYPE_CHECKS[type_name](value) for type_name in expected_types):
            report.error(f"{path}: expected type {expected_types}, got {type(value).__name__}")
            return
    if "enum" in schema and value not in schema["enum"]:
        report.error(f"{path}: {value!r} not in {schema['enum']}")
    if "const" in schema and value != schema["const"]:
        report.error(f"{path}: {value!r} != {schema['const']!r}")
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        report.error(f"{path}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            report.error(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            report.error(f"{path}: {value} > maximum {schema['maximum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            report.error(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            report.error(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for index, item in enumerate(value):
                check_schema(item, schema["items"], f"{path}[{index}]", report)
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for required_key in schema.get("required", []):
            if required_key not in value:
                report.error(f"{path}: missing required key {required_key!r}")
        for key, item in value.items():
            if key in properties:
                check_schema(item, properties[key], f"{path}.{key}", report)
            elif isinstance(schema.get("additionalProperties"), dict):
                check_schema(item, schema["additionalProperties"], f"{path}.{key}", report)
            elif schema.get("additionalProperties") is False:
                report.error(f"{path}: unexpected key {key!r}")


def check_against_schema_file(value, schema_name, report, path=None):
    schema = read_json(SCHEMA_DIRECTORY / f"{schema_name}.schema.json")
    check_schema(value, schema, path or schema_name, report)


def _check_times_monotonic(activity, report):
    timing = activity.get("timing")
    if not timing:
        return
    ordered_fields = ["estimatedStart", "travelPrepComplete", "timeStart", "timeFinished", "estimatedEnd"]
    minutes = [time_string_to_minutes(timing[field]) for field in ordered_fields]
    if minutes != sorted(minutes):
        report.error(f"activities.{activity['id']}: timing not monotonic {dict(zip(ordered_fields, timing.values()))}")


def check_start_rule(rule, report, prefix):
    """A structured start rule (docs/questionnaire.md 'Section start rules') has the fields its kind needs, in range."""
    if rule is None:
        return
    kind = rule.get("kind")
    if kind not in START_RULE_KINDS:
        report.error(f"{prefix}: unknown start rule kind {kind!r}")
        return
    needs = {"fixed-date": ("month", "day"), "nth-weekday": ("month", "weekday", "occurrence"), "solar": ("term",), "new-moon": ("index",)}.get(kind, ())
    for field in needs:
        if field not in rule:
            report.error(f"{prefix}: {kind} rule needs {field!r}")
    if "month" in rule and not 1 <= rule["month"] <= 12:
        report.error(f"{prefix}: month {rule['month']} out of range")
    if "day" in rule and not 1 <= rule["day"] <= 31:
        report.error(f"{prefix}: day {rule['day']} out of range")
    if "weekday" in rule and rule["weekday"] not in keys.WEEKDAY_NAMES:
        report.error(f"{prefix}: unknown weekday {rule['weekday']!r}")
    if "occurrence" in rule and rule["occurrence"] not in NTH_OCCURRENCES:
        report.error(f"{prefix}: occurrence {rule['occurrence']} is not one of {NTH_OCCURRENCES}")
    if "term" in rule and rule["term"] not in SOLAR_TERM_ORDER:
        report.error(f"{prefix}: unknown solar term {rule['term']!r}")
    if "index" in rule and not 1 <= rule["index"] <= NEW_MOON_MAX_INDEX:
        report.error(f"{prefix}: new-moon index {rule['index']} out of range 1-{NEW_MOON_MAX_INDEX}")
    snap = rule.get("snap")
    if snap and (snap.get("weekday") not in keys.WEEKDAY_NAMES or snap.get("direction") not in SNAP_DIRECTIONS):
        report.error(f"{prefix}: snap needs a weekday and a direction {SNAP_DIRECTIONS}")


def check_known_starts(known_starts, rule, report, prefix):
    """knownStarts entries are ISO dates of their year; for computed rules they must equal the computed date."""
    for year_text, iso_date in (known_starts or {}).items():
        try:
            typed = parse_iso_date(iso_date)
        except ValueError:
            report.error(f"{prefix}.knownStarts[{year_text}]: {iso_date!r} is not a date")
            continue
        if not year_text.isdigit() or typed.year != int(year_text):
            report.error(f"{prefix}.knownStarts[{year_text}]: {iso_date} is not in that year")
        elif rule and rule.get("kind") != "manual":
            computed = start_date_for_rule(rule, int(year_text))
            if computed != typed:
                report.error(f"{prefix}.knownStarts[{year_text}]: {iso_date} but the rule gives {computed}")


def check_references(data, report):
    """Cross-file rules that a schema cannot express."""
    day_keys = set(data["days"]["order"])
    block_keys = set(data["blocks"]["order"])
    category_keys = set(data["categories"]["order"])
    days = data["days"]["days"]

    if data["days"]["order"] != keys.DAY_KEY_ORDER:
        report.error("days.order must be the canonical fortnight order")
    for day_key, day in days.items():
        if day["index"] != keys.DAY_KEY_INDEX.get(day_key):
            report.error(f"days.{day_key}: index {day['index']} does not match canonical order")
        expected_appointment_block = "midday" if day["week"] == 1 else "early"
        if day["appointmentBlock"] != expected_appointment_block:
            report.warning(f"days.{day_key}: appointmentBlock {day['appointmentBlock']!r} differs from the rule ({expected_appointment_block})")

    meals_by_slot_and_day = {}
    for menu in data["menus"].values():
        for meal in menu["meals"]:
            for day_key in meal["days"]:
                if day_key not in day_keys:
                    report.error(f"menus.{menu['id']}.{meal['id']}: unknown day key {day_key}")
                slot_key = (menu["id"], meal["slot"], day_key)
                if slot_key in meals_by_slot_and_day:
                    report.error(f"menus.{menu['id']}: {day_key} has two {meal['slot']} meals ({meals_by_slot_and_day[slot_key]}, {meal['id']})")
                meals_by_slot_and_day[slot_key] = meal["id"]
        for day_key in day_keys:
            for slot in keys.MEAL_SLOT_ORDER:
                if (menu["id"], slot, day_key) not in meals_by_slot_and_day:
                    report.error(f"menus.{menu['id']}: {day_key} has no {slot}")
    known_meal_keys = {(meal["slot"], meal["mealKey"]) for menu in data["menus"].values() for meal in menu["meals"]}

    seen_identifiers = set()
    for activity in data["activities"]["activities"]:
        prefix = f"activities.{activity['id']}"
        if activity["id"] in seen_identifiers:
            report.error(f"{prefix}: duplicate id")
        seen_identifiers.add(activity["id"])
        if activity["dayKey"] not in day_keys:
            report.error(f"{prefix}: unknown dayKey {activity['dayKey']}")
        if activity["block"] not in block_keys:
            report.error(f"{prefix}: unknown block {activity['block']}")
        for category in activity["categories"]:
            if category not in category_keys:
                report.error(f"{prefix}: unknown category {category}")
        for meal_reference in activity["detail"].get("mealRefs", []):
            if (meal_reference["slot"], meal_reference["mealKey"]) not in known_meal_keys:
                report.error(f"{prefix}: mealRef {meal_reference['slot']} {meal_reference['mealKey']} does not match any menu meal")
        if activity["title"].lower().startswith("open for appointments"):
            appointment_block = days[activity["dayKey"]]["appointmentBlock"]
            if activity["block"] != appointment_block:
                report.warning(f"{prefix}: appointment activity is in block {activity['block']!r} but {activity['dayKey']}'s appointment block is {appointment_block!r}")
        _check_times_monotonic(activity, report)

    for season in data["seasons"]["seasons"]:
        check_start_rule(season.get("startRule"), report, f"seasons.{season['id']}.startRule")
        check_known_starts(season.get("knownStarts"), season.get("startRule"), report, f"seasons.{season['id']}")
        if season["menuId"] is not None and season["menuId"] not in data["menus"]:
            report.error(f"seasons.{season['id']}: menuId {season['menuId']} has no menu file")
        for category in season["focus"]:
            if category not in category_keys:
                report.error(f"seasons.{season['id']}: unknown focus category {category}")
    if data["meta"]["epoch"]["dayKey"] not in day_keys:
        report.error("meta.epoch.dayKey unknown")

    subject_keys = set(data["categories"]["subjects"])
    if data.get("questionnaire") is not None:
        for subject_id, slider in data["questionnaire"]["subjectSliders"].items():
            if subject_id not in subject_keys:
                report.error(f"questionnaire.subjectSliders: unknown subject {subject_id}")
            bounds, default = slider["minutesPerDay"], slider["default"]
            if not bounds["min"] <= default["min"] <= default["max"] <= bounds["max"]:
                report.error(f"questionnaire.subjectSliders.{subject_id}: default {default['min']}-{default['max']} is not inside {bounds['min']}-{bounds['max']}")
        for list_name in ("wantMore", "delegable", "essential"):
            for category_key in data["questionnaire"].get("defaultAnswers", {}).get(list_name, []):
                if category_key not in category_keys:
                    report.error(f"questionnaire.defaultAnswers.{list_name}: unknown category {category_key}")
        for subject_id in subject_keys - set(data["questionnaire"]["subjectSliders"]):
            report.error(f"questionnaire.subjectSliders: no slider for subject {subject_id}")
        options = data["questionnaire"]["options"]
        # The date rules depend on these two lists matching the code's vocabulary.
        if [option["id"] for option in options["weekdays"]] != keys.WEEKDAY_NAMES:
            report.error("questionnaire.options.weekdays must list the seven weekdays, Sunday first, by their English names")
        if [option["id"] for option in options["solarTerms"]] != SOLAR_TERM_ORDER:
            report.error(f"questionnaire.options.solarTerms must be {SOLAR_TERM_ORDER}")
        default_week_start = data["questionnaire"].get("defaultAnswers", {}).get("weekStart", "sunday")
        if default_week_start not in keys.WEEKDAY_NAMES:
            report.error(f"questionnaire.defaultAnswers.weekStart: unknown weekday {default_week_start!r}")
        agenda_scopes = {option["id"] for option in options["agendaScopes"]}
        default_agenda_scope = data["questionnaire"].get("defaultAnswers", {}).get("agendaScope", "categories")
        if default_agenda_scope not in agenda_scopes:
            report.error(f"questionnaire.defaultAnswers.agendaScope: unknown scope {default_agenda_scope!r}")
        energy_peaks = {option["id"] for option in options["energyPeaks"]}
        default_energy_peak = data["questionnaire"].get("defaultAnswers", {}).get("energyPeak", "varies")
        if default_energy_peak not in energy_peaks:
            report.error(f"questionnaire.defaultAnswers.energyPeak: unknown energy peak {default_energy_peak!r}")
        scheme_ids = {scheme["id"] for scheme in options["yearSplitSchemes"]}
        default_scheme = data["questionnaire"].get("defaultAnswers", {}).get("yearSplitScheme", "quarters")
        if default_scheme not in scheme_ids:
            report.error(f"questionnaire.defaultAnswers.yearSplitScheme: unknown scheme {default_scheme!r}")
        # Every select question names an existing option list, and its typical-person default is a member of it
        # (a single-select default is one id, a multi-select default a list of ids).
        default_answers = data["questionnaire"].get("defaultAnswers", {})
        for section in data["questionnaire"]["sections"]:
            for question in section["questions"]:
                if question["kind"] not in ("single-select", "multi-select"):
                    continue
                option_list = options.get(question.get("options"))
                if option_list is None:
                    report.error(f"questionnaire.sections.{section['id']}.{question['id']}: options {question.get('options')!r} is not a list in questionnaire.options")
                    continue
                known_ids = {option["id"] for option in option_list}
                default = default_answers.get(question["id"])
                default_ids = default if isinstance(default, list) else [] if default is None else [default]
                for option_id in default_ids:
                    if option_id not in known_ids:
                        report.error(f"questionnaire.defaultAnswers.{question['id']}: unknown option {option_id!r} (not in questionnaire.options.{question['options']})")
        for scheme in options["yearSplitSchemes"]:
            for index, section in enumerate(scheme["template"]):
                check_start_rule(section["start"].get("rule"), report, f"questionnaire.yearSplitSchemes.{scheme['id']}[{index}].start.rule")
                check_known_starts(section.get("knownStarts"), section["start"].get("rule"), report, f"questionnaire.yearSplitSchemes.{scheme['id']}[{index}]")
    weights_files = {}
    if data.get("weights") is not None:
        weights_files["weights"] = data["weights"]
    for profile_id, profile in data.get("weightsProfiles", {}).items():
        weights_files[f"weights.{profile_id}"] = profile
    for prefix, weights in weights_files.items():
        check_weights_references(weights, category_keys, subject_keys, data.get("questionnaire"), report, prefix)


CADENCE_REQUIRED_FIELD = {"weekly": None, "every-other-week": "firstDate", "monthly-nth-weekday": "nth", "monthly-date": "dayOfMonth", "one-off": "date"}


def check_standing_appointment(appointment, category_keys, report, prefix):
    """Cadence-specific rules a schema cannot express (shape itself is schema-checked)."""
    if appointment["category"] not in category_keys:
        report.error(f"{prefix}: unknown category {appointment['category']}")
    cadence = appointment["cadence"]
    required_field = CADENCE_REQUIRED_FIELD.get(cadence["kind"])
    if required_field and cadence.get(required_field) is None:
        report.error(f"{prefix}: cadence {cadence['kind']!r} needs {required_field!r}")
    if cadence["kind"] in ("weekly", "every-other-week", "monthly-nth-weekday") and not appointment["weekdays"]:
        report.error(f"{prefix}: cadence {cadence['kind']!r} needs at least one weekday")
    if cadence["kind"] == "monthly-nth-weekday" and cadence.get("nth") == 0:
        report.error(f"{prefix}: nth must be 1–4 or -1 (last)")


def check_block_focus_grid(grid, focus_block_keys, category_keys, report, prefix):
    """A blockFocusGrid's day keys, block keys and focus values against the given vocabulary."""
    if not grid:
        return
    allowed_focus = set(category_keys) | {keys.FLEXIBLE_FOCUS}
    for day_key, cells in grid.items():
        if day_key not in keys.DAY_KEY_ORDER:
            report.error(f"{prefix}: unknown day key {day_key}")
        for block_key, focus in cells.items():
            if block_key not in focus_block_keys:
                report.error(f"{prefix}.{day_key}: block {block_key!r} is not one of the focus blocks {list(focus_block_keys)}")
            if focus not in allowed_focus:
                report.error(f"{prefix}.{day_key}.{block_key}: unknown focus {focus!r}")


def check_import_document(document, category_keys, report, categories=None):
    """An import document (data/schema/import.schema.json): schema, then the readable version-2 fields parsed
    (fk_core.import_document) and the same appointment/grid rules on the normalized result. `categories` is
    categories.json (label lookup for version-2 `category`; keys-only without it)."""
    check_against_schema_file(document, "import", report, path="import")
    if report.ok:
        normalized, problems = import_document.normalize_import_document(document, categories)
        for problem in problems:
            report.error(f"import.{problem}")
        for index, appointment in enumerate(normalized.get("standingAppointments", [])):
            check_standing_appointment(appointment, category_keys, report, f"import.standingAppointments[{index}]")
        for index, task in enumerate(normalized.get("tasks", [])):
            check_standing_appointment(task, category_keys, report, f"import.tasks[{index}]")
        source_blocks = document.get("blocks") or []
        focus_block_keys = [block["key"] for block in source_blocks if block.get("carriesFocus")] or list(keys.FOCUS_BLOCK_KEYS)
        block_keys = [block["key"] for block in source_blocks] or list(keys.FOCUS_BLOCK_KEYS)
        check_block_focus_grid(document.get("blockFocusGrid"), focus_block_keys, category_keys, report, "import.blockFocusGrid")
        for day_key, block_key in (document.get("appointmentBlocks") or {}).items():
            if day_key not in keys.DAY_KEY_ORDER:
                report.error(f"import.appointmentBlocks: unknown day key {day_key}")
            if block_key not in focus_block_keys:
                report.error(f"import.appointmentBlocks.{day_key}: block {block_key!r} is not one of the focus blocks {focus_block_keys}")
        for index, activity in enumerate(document.get("fixedActivities", [])):
            if activity["dayKey"] not in keys.DAY_KEY_ORDER:
                report.error(f"import.fixedActivities[{index}]: unknown day key {activity['dayKey']}")
            if activity.get("block") is not None and activity["block"] not in block_keys:
                report.error(f"import.fixedActivities[{index}]: unknown block {activity['block']!r}")
            for category_key in activity["categories"]:
                if category_key not in category_keys:
                    report.error(f"import.fixedActivities[{index}]: unknown category {category_key}")
    return report


def check_weights_references(weights, category_keys, subject_keys, questionnaire, report, prefix="weights"):
    """Cross-file rules for a weights file: known keys, shares that add up, sane essential count."""
    focus_block_keys = [block["key"] for block in weights.get("blocks", []) if block.get("carriesFocus")] or list(keys.FOCUS_BLOCK_KEYS)
    for category_key, category in weights["categories"].items():
        if category_key not in category_keys:
            report.error(f"{prefix}.categories: unknown category {category_key}")
        for block_key in category.get("preferredBlocks", []):
            if block_key not in focus_block_keys:
                report.error(f"{prefix}.categories.{category_key}: preferredBlocks {block_key!r} is not one of this profile's focus blocks {focus_block_keys}")
    if weights.get("blocks"):
        total_minutes = sum(block["durationMinutes"] for block in weights["blocks"])
        if total_minutes != 24 * 60:
            report.error(f"{prefix}.blocks: durations add up to {total_minutes} minutes, expected 1440")
    for index, appointment in enumerate(weights.get("standingAppointments", [])):
        check_standing_appointment(appointment, category_keys, report, f"{prefix}.standingAppointments[{index}]")
    for index, task in enumerate(weights.get("tasks", [])):
        check_standing_appointment(task, category_keys, report, f"{prefix}.tasks[{index}]")
        if task.get("timeOfDay") is not None and task["timeOfDay"] not in import_document.TIME_OF_DAY_WORDS:
            report.error(f"{prefix}.tasks[{index}]: unknown time of day {task['timeOfDay']!r}")
    if questionnaire and weights.get("meals"):
        meals = weights["meals"]
        meal_bounds, slot_bounds = questionnaire["mealsPerDay"], questionnaire["slotsPerMeal"]
        if not meal_bounds["min"] <= meals["perDay"] <= meal_bounds["max"] or len(meals["meals"]) != meals["perDay"]:
            report.error(f"{prefix}.meals: perDay {meals['perDay']} with {len(meals['meals'])} meals listed, expected {meal_bounds['min']}-{meal_bounds['max']} and one entry per meal")
        known_slots = {option["id"] for option in questionnaire["options"]["mealSlots"]}
        seen_meal_slugs = {}
        for index, meal in enumerate(meals["meals"]):
            slug = meal_plan.meal_slug(meal.get("name") or f"Meal {index + 1}")  # older files: unnamed meals read as "Meal n"
            if slug in seen_meal_slugs:
                report.error(f"{prefix}.meals.meals[{index}]: name {meal.get('name')!r} is already used by meal {seen_meal_slugs[slug] + 1}")
            seen_meal_slugs.setdefault(slug, index)
            if not slot_bounds["min"] <= len(meal["slots"]) <= slot_bounds["max"]:
                report.error(f"{prefix}.meals.meals[{index}]: {len(meal['slots'])} slots, expected {slot_bounds['min']}-{slot_bounds['max']}")
            for slot in meal["slots"]:
                if slot not in known_slots:
                    report.error(f"{prefix}.meals.meals[{index}]: unknown slot {slot}")
    if weights.get("mealPlan") is not None:
        _, problems = meal_plan.normalize_meal_plan(weights["mealPlan"], (weights.get("meals") or {}).get("meals", []))
        for problem in problems:
            report.error(f"{prefix}.mealPlan: {problem}")
    if questionnaire and weights.get("yearSplit"):
        year_bounds = questionnaire["yearSections"]
        schemes = {option["id"] for option in questionnaire["options"]["yearSplitSchemes"]}
        if weights["yearSplit"]["scheme"] not in schemes:
            report.error(f"{prefix}.yearSplit: unknown scheme {weights['yearSplit']['scheme']}")
        for index, section in enumerate(weights["yearSplit"]["sections"]):
            weeks = section.get("durationWeeks")
            if weeks and weeks["min"] > weeks["max"]:
                report.error(f"{prefix}.yearSplit.sections[{index}]: durationWeeks min {weeks['min']} > max {weeks['max']}")
            check_start_rule(section.get("start", {}).get("rule"), report, f"{prefix}.yearSplit.sections[{index}].start.rule")
            check_known_starts(section.get("knownStarts"), section.get("start", {}).get("rule"), report, f"{prefix}.yearSplit.sections[{index}]")
            if section.get("startVariant", "a") not in ("a", "b"):
                report.error(f"{prefix}.yearSplit.sections[{index}]: startVariant must be a or b")
        if "weekStart" in weights and weights["weekStart"] not in keys.WEEKDAY_NAMES:
            report.error(f"{prefix}.weekStart: unknown weekday {weights['weekStart']!r}")
        section_count = len(weights["yearSplit"]["sections"])
        if not year_bounds["min"] <= section_count <= year_bounds["max"]:
            report.error(f"{prefix}.yearSplit: {section_count} sections, expected {year_bounds['min']}-{year_bounds['max']}")
    if questionnaire:
        window_bounds = questionnaire["wakingWindow"]["minutes"]
        waking_minutes = weights.get("wakingWindow", {}).get("minutesPerDay")
        if weights.get("source") == "questionnaire" and waking_minutes is not None and not window_bounds["min"] <= waking_minutes <= window_bounds["max"]:
            report.error(f"{prefix}.wakingWindow: {waking_minutes} minutes per day, expected {window_bounds['min']}-{window_bounds['max']}")
        known_practices = {option["id"] for option in questionnaire["options"]["practices"]}
        for practice in weights.get("practices", []):
            if practice not in known_practices:
                report.error(f"{prefix}.practices: unknown practice {practice}")
        agenda_scopes = {option["id"] for option in questionnaire["options"]["agendaScopes"]}
        if "agendaScope" in weights and weights["agendaScope"] not in agenda_scopes:
            report.error(f"{prefix}.agendaScope: unknown scope {weights['agendaScope']!r}")
        energy_peaks = {option["id"] for option in questionnaire["options"]["energyPeaks"]}
        if "energyPeak" in weights and weights["energyPeak"] not in energy_peaks:
            report.error(f"{prefix}.energyPeak: unknown energy peak {weights['energyPeak']!r}")
    for weekday in weights.get("restDays", []):
        if weekday not in keys.WEEKDAY_NAMES:
            report.error(f"{prefix}.restDays: unknown weekday {weekday!r}")
    if "context" in weights and not isinstance(weights["context"], str):
        report.error(f"{prefix}.context: must be text")
    check_block_focus_grid(weights.get("blockFocusGrid"), focus_block_keys, category_keys, report, f"{prefix}.blockFocusGrid")
    proposal = weights.get("proposal") or {}
    check_block_focus_grid(proposal.get("blockFocusGrid"), focus_block_keys, category_keys, report, f"{prefix}.proposal.blockFocusGrid")
    for index, activity in enumerate(proposal.get("activities", [])):
        if activity.get("dayKey") not in keys.DAY_KEY_ORDER:
            report.error(f"{prefix}.proposal.activities[{index}]: unknown day key {activity.get('dayKey')!r}")
        if activity.get("block") not in focus_block_keys:
            report.error(f"{prefix}.proposal.activities[{index}]: block {activity.get('block')!r} is not one of this profile's focus blocks {focus_block_keys}")
        for category_key in activity.get("categories", []):
            if category_key not in category_keys:
                report.error(f"{prefix}.proposal.activities[{index}]: unknown category {category_key}")
    for subject_id, subject in weights.get("subjects", {}).items():
        if subject_id not in subject_keys:
            report.error(f"{prefix}.subjects: unknown subject {subject_id}")
        if subject.get("everyday", True) or subject.get("peripheral"):
            continue
        if subject.get("cadence") not in keys.SUBJECT_CADENCES:
            report.error(f"{prefix}.subjects.{subject_id}: cadence must be one of {', '.join(keys.SUBJECT_CADENCES)} when it is not everyday (got {subject.get('cadence')!r})")
            continue
        period_days = len(keys.DAY_KEY_ORDER) if subject["cadence"] == "fortnight" else round(section_days_from_year_split(weights.get("yearSplit")))
        days = subject.get("daysPerPeriod")
        if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= period_days - 1:
            report.error(f"{prefix}.subjects.{subject_id}: daysPerPeriod must be 1-{period_days - 1} for the {subject['cadence']} cadence (got {days!r})")
    share_total = sum(category["share"] for category in weights["categories"].values()) + weights.get("flexibleShare", 0)
    if abs(share_total - 1) > 0.001:
        report.warning(f"{prefix}: category shares + flexibleShare = {share_total:.4f}, expected 1")
    essential_count = sum(1 for category in weights["categories"].values() if category.get("essential"))
    if questionnaire and weights.get("source") == "questionnaire":
        bounds = questionnaire.get("essentialCategories", {"min": 1, "max": 3})
        if not bounds["min"] <= essential_count <= bounds["max"]:
            report.warning(f"{prefix}: {essential_count} essential categories, expected {bounds['min']}-{bounds['max']}")


def validate_data(data):
    """Full validation of the loaded data dictionary (see json_io.load_data_directory)."""
    report = ValidationReport()
    for name in ("meta", "seasons", "days", "blocks", "categories", "activities"):
        check_against_schema_file(data[name], name, report)
    for menu_id, menu in data["menus"].items():
        check_against_schema_file(menu, "menu", report, path=f"menus.{menu_id}")
    if data.get("questionnaire") is not None:
        check_against_schema_file(data["questionnaire"], "questionnaire", report)
    if data.get("weights") is not None:
        check_against_schema_file(data["weights"], "weights", report)
    for profile_id, profile in data.get("weightsProfiles", {}).items():
        check_against_schema_file(profile, "weights", report, path=f"weights.{profile_id}")
    if report.ok:
        check_references(data, report)
    return report
