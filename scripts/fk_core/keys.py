"""Stable identifiers: slugs, the 14 day keys, block keys, category keys, and meal keys."""
import re

WEEKDAY_NAMES = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

# The fortnight order: A/B alternates every day, so week 2 is the inverse of week 1.
DAY_KEY_ORDER = [
    "sun-a", "mon-b", "tue-a", "wed-b", "thu-a", "fri-b", "sat-a",
    "sun-b", "mon-a", "tue-b", "wed-a", "thu-b", "fri-a", "sat-b",
]
DAY_KEY_INDEX = {day_key: index for index, day_key in enumerate(DAY_KEY_ORDER)}

BLOCK_KEY_ORDER = ["too-early", "early", "midday", "late", "too-late"]
FOCUS_BLOCK_KEYS = ["early", "midday", "late"]  # the blocks that carry a focus and activities

CATEGORY_KEY_ORDER = [
    "meals", "cleaning", "working", "spirituality-development",
    "friends-family", "health", "operations",
]
CATEGORY_LABELS = {
    "meals": "Meals",
    "cleaning": "Cleaning",
    "working": "Working",
    "spirituality-development": "Spirituality & Development",
    "friends-family": "Friends & Family",
    "health": "Health",
    "operations": "Operations",
}
FLEXIBLE_FOCUS = "flexible"

SUBJECT_CADENCES = ("fortnight", "section")


def subject_daily_minutes(subject_answer):
    """What a subject contributes to its category's raw minutes, per day. The slider always means "how long in a
    single day"; the cadence says how many days. Everyday subjects contribute their midpoint; a fortnight subject
    contributes it on `daysPerPeriod` of the cycle's 14 days. A subject on the section cadence, and one marked
    "not often" (peripheral), contribute nothing — they are done in the fortnight's flexible time rather than in
    its rhythm, and it is their absence from the declaration that leaves that time free. Twin of
    src/lib/shared/fortknight-rules.js subjectDailyMinutes; lives here so the generator can read it without
    importing weights.py."""
    if subject_answer.get("peripheral"):
        return 0
    minutes_range = subject_answer["minutesPerDay"]
    midpoint = (minutes_range["min"] + minutes_range["max"]) / 2
    if subject_answer.get("everyday", True):
        return midpoint
    if subject_answer.get("cadence") == "fortnight":
        return midpoint * int(subject_answer.get("daysPerPeriod") or 0) / len(DAY_KEY_ORDER)
    return 0

# Focus labels used in the Days sheet -> category (or the flexible pseudo-focus).
FOCUS_LABEL_TO_CATEGORY = {
    "meal prep": "meals",
    "meals": "meals",
    "cleaning": "cleaning",
    "working": "working",
    "learning": "spirituality-development",
    "teaching": "spirituality-development",
    "flexible": FLEXIBLE_FOCUS,
}

MEAL_SLOT_ORDER = ["brunch", "snack", "dinner"]
MEAL_HINT_KEYS = {
    "Leftovers/Dessert": "leftovers-dessert",
    "Breakfast": "breakfast",
    "Brunch": "brunch",
    "Snack": "snack",
    "Dinner": "dinner",
}


def slugify(text):
    text = text.strip().lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def category_key_from_label(label):
    """'Spirituality & Development' -> 'spirituality-development'; 'Operations/Health' -> both keys."""
    keys = []
    for part in label.split("/"):
        part = part.strip()
        for key, known_label in CATEGORY_LABELS.items():
            if known_label.lower() == part.lower():
                keys.append(key)
                break
        else:
            raise KeyError(f"unknown category label: {part!r}")
    return keys


def focus_key_from_label(label):
    return FOCUS_LABEL_TO_CATEGORY[label.strip().lower()]


def day_key_from_label(label):
    """'Sunday A' -> 'sun-a'."""
    weekday, variant = label.strip().split()
    return f"{weekday[:3].lower()}-{variant.lower()}"


def day_key_from_short_key(short_key):
    """'Sun_A' -> 'sun-a'."""
    weekday, variant = short_key.strip().split("_")
    return f"{weekday.lower()}-{variant.lower()}"


def short_key_from_day_key(day_key):
    """'sun-a' -> 'Sun_A'."""
    weekday, variant = day_key.split("-")
    return f"{weekday.capitalize()}_{variant.upper()}"


def weekday_number(weekday_name):
    """'sunday' -> 0 ... 'saturday' -> 6 (the JavaScript getUTCDay convention, shared by both ports)."""
    return WEEKDAY_NAMES.index(weekday_name)


def day_key_from_weekday_and_variant(weekday_name, variant):
    """('monday', 'b') -> 'mon-b'."""
    return f"{weekday_name[:3]}-{variant.lower()}"


def day_key_order_starting_on(weekday_name):
    """DAY_KEY_ORDER rotated so it begins on the first key of that weekday (display only; the canonical order stays)."""
    first_index = next(index for index, day_key in enumerate(DAY_KEY_ORDER) if day_key.startswith(weekday_name[:3]))
    return DAY_KEY_ORDER[first_index:] + DAY_KEY_ORDER[:first_index]


def label_from_day_key(day_key):
    """'sun-a' -> 'Sunday A'."""
    weekday_short, variant = day_key.split("-")
    weekday = next(name for name in WEEKDAY_NAMES if name.startswith(weekday_short))
    return f"{weekday.capitalize()} {variant.upper()}"


def sort_day_keys(day_keys):
    return sorted(day_keys, key=DAY_KEY_INDEX.__getitem__)


def normalize_meal_key(raw_meal_key):
    """'Tue_A+Sun_A\\t' -> 'sun-a+tue-a' (whitespace stripped, days in cycle order)."""
    day_keys = [day_key_from_short_key(part) for part in raw_meal_key.strip().split("+") if part.strip()]
    return "+".join(sort_day_keys(day_keys))


def meal_key_days(meal_key):
    return meal_key.split("+")
