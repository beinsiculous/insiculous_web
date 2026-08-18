"""Parse the free-text "Link/Tasks" column of the Schedule sheet into structured detail.

Grammar observed in the workbook (kept alongside the raw text, never replacing it):
  meal-prep:  "Snack Fri_A+Sun_A & Dinner Sun_B+Wed_A"   -> mealRefs
  url:        "https://..."                              -> url
  text:       "Knowledge & Family Baguas"                -> text (kept whole; "&" is part of names)
"""
import re

from .keys import meal_key_days, normalize_meal_key

MEAL_REFERENCE_PATTERN = re.compile(
    r"^(?P<slot>Brunch|Snack|Dinner)\s+(?P<meal_key>[A-Za-z]{3}_[AB](?:\+[A-Za-z]{3}_[AB])*)$"
)
URL_PATTERN = re.compile(r"^https?://\S+$")


def parse_detail(raw_text):
    """Return a detail dictionary; raw text is always preserved under "raw"."""
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return {"raw": "", "kind": None}
    if URL_PATTERN.match(raw_text):
        return {"raw": raw_text, "kind": "url", "url": raw_text}
    parts = [part.strip() for part in raw_text.split(" & ")]
    meal_references = []
    for part in parts:
        match = MEAL_REFERENCE_PATTERN.match(part)
        if not match:
            break
        meal_key = normalize_meal_key(match.group("meal_key"))
        meal_references.append({
            "slot": match.group("slot").lower(),
            "mealKey": meal_key,
            "days": meal_key_days(meal_key),
        })
    if meal_references and len(meal_references) == len(parts):
        return {"raw": raw_text, "kind": "meal-prep", "mealRefs": meal_references}
    return {"raw": raw_text, "kind": "text", "text": raw_text}
