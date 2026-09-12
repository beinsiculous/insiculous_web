"""The import document (docs/importers.md, data/schema/import.schema.json): a person's existing system, as
their assistant read it, in a shape the person can check. Version 2 is written for the reader
("repeats": "monthly on the 2nd tuesday", "start": "7:00 PM", "lasts": "2 h"); this module turns it into the
canonical objects the rest of FortKnight consumes. Its JavaScript twin, src/lib/shared/import-document.js,
was removed on 2026-08-30 with the creation chain and is preserved at the tag `creation-chain-parked`,
along with tests/test_import_document.py, which used to run both on the same fixture. The clock half below
still has a live twin in src/lib/shared/clock.js — keep those two in sync (nothing exercises the pair any
more; beinsiculous/insiculous_web#10 owns that gap)."""
import copy
import re

from . import keys
from .timeconv import round_up_to_grid

IMPORT_SCHEMA_VERSIONS = (1, 2)
SOURCE_KINDS = ("text", "photo", "xlsx", "ics", "google-calendar", "other")
TIME_OF_DAY_MINUTES = {"morning": "09:00", "midday": "12:00", "afternoon": "15:00", "evening": "19:00", "night": "21:00"}
TIME_OF_DAY_WORDS = list(TIME_OF_DAY_MINUTES) + ["anytime"]
_ORDINALS = {"1st": 1, "first": 1, "2nd": 2, "second": 2, "3rd": 3, "third": 3, "4th": 4, "fourth": 4, "last": -1}
_ORDINAL_WORDS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", -1: "last"}


def _tidy(text):
    return re.sub(r"\s+", " ", str(text if text is not None else "").strip().lower())


# ----- clock times and durations (src/lib/shared/clock.js) -----

def minutes_to_time_string(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_clock_time(text):
    """"2:00 PM", "2 pm", "14:00", "9:30am" -> "HH:MM"; None when it is not a clock time."""
    match = re.match(r"^\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])?\.?[Mm]?\.?\s*$", str(text if text is not None else ""))
    if not match:
        return None
    hours = int(match.group(1))
    minutes = int(match.group(2) or "0")
    period = match.group(3).lower() if match.group(3) else None
    if minutes > 59:
        return None
    if period:
        if hours < 1 or hours > 12:
            return None
        hours = hours % 12 + (12 if period == "p" else 0)
    elif hours > 23 or match.group(2) is None:
        return None  # "14" alone is not a time; "14:00" is
    return minutes_to_time_string(hours * 60 + minutes)


def parse_duration(text):
    """"2 h 15 min", "90 min", "1 h", "1.5 h", "45", 45 -> integer minutes; None when unreadable."""
    if isinstance(text, bool):
        return None
    if isinstance(text, int) and text >= 0:
        return text
    source = _tidy(text)
    if re.fullmatch(r"\d+", source):
        return int(source)
    hours_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b", source)
    minutes_match = re.search(r"(\d+)\s*(?:m|min|mins|minute|minutes)\b", source)
    if not hours_match and not minutes_match:
        return None
    leftover = source.replace(hours_match.group(0) if hours_match else "", "", 1).replace(minutes_match.group(0) if minutes_match else "", "", 1)
    if re.sub(r"[\s,and]+", "", leftover):
        return None
    return round(float(hours_match.group(1) if hours_match else 0) * 60) + int(minutes_match.group(1) if minutes_match else 0)


def describe_duration(minutes):
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours} h {remainder} min"
    if hours:
        return f"{hours} h"
    return f"{remainder} min"


def format_clock_time(time_string):
    """"22:00" -> "10:00 PM"; anything that is not HH:MM comes back unchanged."""
    match = re.match(r"^(\d{1,2}):(\d{2})$", str(time_string if time_string is not None else ""))
    if not match:
        return time_string if time_string is not None else ""
    hours24 = int(match.group(1)) % 24
    period = "AM" if hours24 < 12 else "PM"
    hours12 = 12 if hours24 % 12 == 0 else hours24 % 12
    return f"{hours12}:{match.group(2)} {period}"


# ----- weekdays, categories, cadence phrases -----

def resolve_weekday(text):
    """"Mon", "monday", "Tuesdays" -> the weekday id; None when unknown."""
    word = re.sub(r"s$", "", _tidy(text))
    if len(word) < 3:
        return None
    return next((weekday for weekday in keys.WEEKDAY_NAMES if weekday == word or weekday.startswith(word)), None)


def resolve_category(text, categories=None):
    """A key ("friends-family") or a label ("Friends & Family", "spirituality and development") -> the key."""
    wanted = _tidy(text)
    if not wanted:
        return None
    for key in (categories or {}).get("order", []):
        label = _tidy(categories["categories"][key].get("label"))
        candidates = {key, label, label.replace("&", "and"), re.sub(r"\s*&\s*", "-", label), re.sub(r"\s*&\s*", " and ", label)}
        if wanted in candidates or wanted.replace("-", " ") in candidates:
            return key
    if categories is None and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", wanted):
        return wanted
    return None


def parse_repeats(phrase):
    """The `repeats` phrase -> {"cadence": …, "weekdays"?: […]} or {"problem": …}."""
    text = _tidy(phrase)
    if text in ("every week", "weekly"):
        return {"cadence": {"kind": "weekly"}}
    match = re.fullmatch(r"every other week(?: (?:from|starting|since) (\d{4}-\d{2}-\d{2}))?", text)
    if match:
        if not match.group(1):
            return {"problem": 'every other week needs a date: "every other week from YYYY-MM-DD"'}
        return {"cadence": {"kind": "every-other-week", "firstDate": match.group(1)}}
    match = re.fullmatch(r"monthly on the (1st|first|2nd|second|3rd|third|4th|fourth|last) ([a-z]+)", text)
    if match:
        weekday = resolve_weekday(match.group(2))
        if not weekday:
            return {"problem": f'unknown weekday "{match.group(2)}" in "{phrase}"'}
        return {"cadence": {"kind": "monthly-nth-weekday", "nth": _ORDINALS[match.group(1)]}, "weekdays": [weekday]}
    match = re.fullmatch(r"monthly on (?:day |the )?(\d{1,2})(?:st|nd|rd|th)?", text)
    if match:
        day_of_month = int(match.group(1))
        if day_of_month < 1 or day_of_month > 31:
            return {"problem": f'day of month must be 1–31 in "{phrase}"'}
        return {"cadence": {"kind": "monthly-date", "dayOfMonth": day_of_month}}
    match = re.fullmatch(r"(?:once|one-off|one off)(?: on)? (\d{4}-\d{2}-\d{2})", text)
    if match:
        return {"cadence": {"kind": "one-off", "date": match.group(1)}}
    return {"problem": f'cannot read "{phrase}" — use "every week", "every other week from YYYY-MM-DD", "monthly on the 2nd tuesday", "monthly on day 15" or "once on YYYY-MM-DD"'}


def _capitalize(word):
    return word[:1].upper() + word[1:] if word else word


def describe_weekdays(weekdays):
    names = [f"{_capitalize(weekday)}s" for weekday in (weekdays or [])]
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def describe_cadence(cadence, weekdays=()):
    """The canonical cadence + weekdays back as a phrase: "every week on Mondays and Thursdays"."""
    days = describe_weekdays(weekdays)
    kind = (cadence or {}).get("kind")
    if kind == "weekly":
        return f"every week{f' on {days}' if days else ''}"
    if kind == "every-other-week":
        return f"every other week{f' on {days}' if days else ''} from {cadence['firstDate']}"
    if kind == "monthly-nth-weekday":
        return f"monthly on the {_ORDINAL_WORDS.get(cadence.get('nth'), cadence.get('nth'))} {' / '.join(_capitalize(weekday) for weekday in weekdays) or 'weekday'}"
    if kind == "monthly-date":
        return f"monthly on day {cadence['dayOfMonth']}"
    if kind == "one-off":
        return f"once on {cadence['date']}"
    return ""


# ----- readable records -> canonical -----

def _read_item(item, categories, needs_start, allow_when):
    if not isinstance(item, dict):
        return {"problem": "not an object"}
    title = str(item.get("title") if item.get("title") is not None else "").strip()
    if not title:
        return {"problem": "needs a title"}
    repeats = parse_repeats(item.get("repeats"))
    if "problem" in repeats:
        return {"problem": repeats["problem"]}
    listed = item.get("weekdays")
    listed_weekdays = listed if isinstance(listed, list) else ([listed] if listed else [])
    weekdays = []
    for entry in listed_weekdays:
        weekday = resolve_weekday(entry)
        if not weekday:
            return {"problem": f"unknown weekday {_json(entry)}"}
        if weekday not in weekdays:
            weekdays.append(weekday)
    for weekday in repeats.get("weekdays", []):
        if weekday not in weekdays:
            weekdays.append(weekday)
    raw_start = item.get("start")
    start = None if raw_start in (None, "") else parse_clock_time(raw_start)
    if raw_start and not start:
        return {"problem": f'cannot read the start time {_json(raw_start)} — write it like "2:00 PM" or "14:00"'}
    if needs_start and not start:
        return {"problem": "needs a start time"}
    time_of_day = _tidy(item["when"]) if allow_when and item.get("when") else None
    if time_of_day and time_of_day not in TIME_OF_DAY_WORDS:
        return {"problem": f"unknown time of day {_json(item.get('when'))} — one of {', '.join(TIME_OF_DAY_WORDS)}"}
    raw_lasts = item.get("lasts")
    duration = (None if needs_start else 0) if raw_lasts in (None, "") else parse_duration(raw_lasts)
    if duration is None:
        return {"problem": "needs how long it lasts" if needs_start and "lasts" not in item else f'cannot read the duration {_json(raw_lasts)} — write it like "1 h 30 min" or "45 min"'}
    category = resolve_category(item.get("category"), categories)
    if not category:
        return {"problem": f"unknown category {_json(item.get('category'))}"}
    record = {"title": title, "weekdays": weekdays, "cadence": repeats["cadence"], "category": category}
    if start:
        record["start"] = start
    record["durationMinutes"] = round_up_to_grid(duration)  # an assistant's "37 min" books as 40
    if allow_when:
        record["timeOfDay"] = time_of_day if time_of_day else (None if start else "anytime")
    if isinstance(item.get("from"), str) and item["from"].strip():
        record["from"] = item["from"].strip()
    return {"record": record}


def _json(value):
    import json
    return json.dumps(value, ensure_ascii=False)


def commitment_to_standing_appointment(commitment, categories=None):
    """A version-2 commitment -> the canonical standing appointment, or {"problem": …}."""
    read = _read_item(commitment, categories, needs_start=True, allow_when=False)
    if "problem" in read:
        return read
    record = read["record"]
    return {"record": {field: record[field] for field in ("title", "weekdays", "start", "durationMinutes", "category", "cadence")}}


def task_to_record(task, categories=None):
    """A version-2 task -> the canonical task ({title, weekdays, cadence, timeOfDay, start?, durationMinutes, category, from?})."""
    return _read_item(task, categories, needs_start=False, allow_when=True)


def normalize_import_document(document, categories=None):
    """Any supported document -> (normalized copy, problems). Version 1 passes through (+ empty `tasks`);
    version 2's readable `commitments` become canonical `standingAppointments` (appended to any it carries) and
    its `tasks` canonical task records. The stored document is never this copy — readers normalize on read."""
    problems = []
    if not isinstance(document, dict):
        return {"schemaVersion": None, "standingAppointments": [], "tasks": []}, ["not an import document"]
    normalized = copy.deepcopy(document)
    normalized["standingAppointments"] = list(document.get("standingAppointments") or [])
    normalized["tasks"] = []
    version = document.get("schemaVersion")
    if isinstance(version, bool) or version not in IMPORT_SCHEMA_VERSIONS:
        problems.append(f"schemaVersion {_json(version)} is not supported ({' or '.join(map(str, IMPORT_SCHEMA_VERSIONS))})")
        return normalized, problems
    if version >= 2:
        for index, commitment in enumerate(document.get("commitments") or []):
            read = commitment_to_standing_appointment(commitment, categories)
            if "problem" in read:
                problems.append(f"commitments #{index + 1} {_json((commitment or {}).get('title', '') if isinstance(commitment, dict) else '')}: {read['problem']}")
            else:
                normalized["standingAppointments"].append(read["record"])
        for index, task in enumerate(document.get("tasks") or []):
            read = task_to_record(task, categories)
            if "problem" in read:
                problems.append(f"tasks #{index + 1} {_json((task or {}).get('title', '') if isinstance(task, dict) else '')}: {read['problem']}")
            else:
                normalized["tasks"].append(read["record"])
    return normalized, problems


def import_review_rows(document, categories=None):
    """The review a person reads after Apply (mirror of importReviewRows): readable rows for what the document carries."""
    normalized, problems = normalize_import_document(document, categories)

    def label(key):
        return ((categories or {}).get("categories", {}).get(key) or {}).get("label", key)

    return {
        "commitments": [
            {"title": appointment["title"], "repeats": describe_cadence(appointment["cadence"], appointment.get("weekdays", [])), "start": format_clock_time(appointment["start"]),
             "lasts": describe_duration(appointment["durationMinutes"]), "category": label(appointment["category"])}
            for appointment in normalized["standingAppointments"]
        ],
        "tasks": [
            {"title": task["title"], "repeats": describe_cadence(task["cadence"], task.get("weekdays", [])), "when": format_clock_time(task["start"]) if task.get("start") else task.get("timeOfDay"),
             "lasts": describe_duration(task["durationMinutes"]) if task["durationMinutes"] else "", "category": label(task["category"])}
            for task in normalized["tasks"]
        ],
        "skipped": [{"title": str((entry or {}).get("title", "")), "why": str((entry or {}).get("why", ""))} for entry in (document or {}).get("skipped") or []],
        "review": [str(line) for line in (document or {}).get("review") or []],
        "notes": [str(line) for line in (document or {}).get("notes") or []],
        "problems": problems,
    }
