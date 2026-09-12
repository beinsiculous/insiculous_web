"""Calendar rules: season start dates for any year, and calendar date -> fortnight day key.

Mirrored exactly by src/lib/shared/fortknight-rules.js — keep both in sync.

A season (workbook or a person's own, docs/questionnaire.md "Section start rules") starts by a
structured rule: {kind, ...kind fields, offsetDays, snap}. Evaluation for a year: the kind's base
date -> + offsetDays -> snap to a weekday (on-or-after / on-or-before) or none. Anything that cannot
be resolved (Feb 30, the 13th new moon of a 12-moon year, a manual season without a typed date for
that year, no rule at all) yields None: that season simply does not restart the fortnight that year.
"""
import datetime

from .astronomy import SOLAR_TERM_ORDER, new_moon_dates_in_year, solar_term_date
from .keys import DAY_KEY_INDEX, DAY_KEY_ORDER, WEEKDAY_NAMES, weekday_number

CYCLE_LENGTH_DAYS = 14
START_RULE_KINDS = ["fixed-date", "nth-weekday", "easter", "solar", "new-moon", "manual"]
SNAP_DIRECTIONS = ["on-or-after", "on-or-before"]
NTH_OCCURRENCES = [1, 2, 3, 4, -1]  # -1 = the last one in the month
NEW_MOON_MAX_INDEX = 13


def weekday_number_of(date):
    """Sunday=0 ... Saturday=6 (isoweekday: Monday=1 ... Sunday=7)."""
    return date.isoweekday() % 7


def weekday_on_or_after(date, target_weekday_number):
    return date + datetime.timedelta(days=(target_weekday_number - weekday_number_of(date)) % 7)


def weekday_on_or_before(date, target_weekday_number):
    return date - datetime.timedelta(days=(weekday_number_of(date) - target_weekday_number) % 7)


def nth_weekday_of_month(year, month, target_weekday_number, occurrence):
    """occurrence 1..4 = the nth such weekday; -1 = the last one."""
    if occurrence == -1:
        last_of_month = datetime.date(year + (month == 12), (month % 12) + 1, 1) - datetime.timedelta(days=1)
        return weekday_on_or_before(last_of_month, target_weekday_number)
    first_of_month = datetime.date(year, month, 1)
    return weekday_on_or_after(first_of_month, target_weekday_number) + datetime.timedelta(days=7 * (occurrence - 1))


def easter_sunday(year):
    """Anonymous Gregorian computus."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(year, month, day)


def _base_date_for_rule(rule, year, known_starts):
    kind = rule["kind"]
    if kind == "fixed-date":
        try:
            return datetime.date(year, rule["month"], rule["day"])
        except ValueError:
            return None
    if kind == "nth-weekday":
        return nth_weekday_of_month(year, rule["month"], weekday_number(rule["weekday"]), rule["occurrence"])
    if kind == "easter":
        return easter_sunday(year)
    if kind == "solar":
        return solar_term_date(rule["term"], year)
    if kind == "new-moon":
        dates = new_moon_dates_in_year(year)
        return dates[rule["index"] - 1] if 1 <= rule["index"] <= len(dates) else None
    if kind == "manual":
        typed = (known_starts or {}).get(str(year))
        return parse_iso_date(typed) if typed else None
    raise ValueError(f"unknown start rule kind: {kind}")


def start_date_for_rule(rule, year, known_starts=None):
    """The ONE evaluator: rule -> date for `year`, or None when the rule cannot resolve that year."""
    if not rule:
        return None
    date = _base_date_for_rule(rule, year, known_starts)
    if date is None:
        return None
    date += datetime.timedelta(days=rule.get("offsetDays", 0))
    snap = rule.get("snap")
    if snap:
        target = weekday_number(snap["weekday"])
        date = weekday_on_or_after(date, target) if snap["direction"] == "on-or-after" else weekday_on_or_before(date, target)
    return date


def season_start_date(season, year):
    return start_date_for_rule(season.get("startRule"), year, season.get("knownStarts"))


def season_starts_for_year(seasons, year):
    """[(start_date, season_dict)] sorted by date for one calendar year (unresolvable seasons skipped)."""
    starts = [(season_start_date(season, year), season) for season in seasons]
    return sorted(((date, season) for date, season in starts if date is not None), key=lambda pair: pair[0])


def season_for_date(seasons, date):
    """The season whose most recent start is on or before `date` (looks back into the prior year).
    Returns (start_date, season), or None when no season has started by then. Ties: the later one in the list."""
    candidates = season_starts_for_year(seasons, date.year - 1) + season_starts_for_year(seasons, date.year)
    current = None
    for start_date, season in candidates:
        if start_date <= date:
            current = (start_date, season)
    return current  # (start_date, season) or None


def season_anchor_date(start_date, start_day_key):
    """The date the fortnight is anchored on: the startDayKey's weekday on or before the season start,
    so a calendar weekday always carries a day key of the same weekday (a no-op when they already agree)."""
    weekday_short = start_day_key.split("-")[0]
    target = next(index for index, name in enumerate(WEEKDAY_NAMES) if name.startswith(weekday_short))
    return weekday_on_or_before(start_date, target)


def cycle_index_for_date(date, epoch_date, epoch_day_key):
    """0..13 position of `date` in the fortnight, anchored so that epoch_date == epoch_day_key."""
    days_since_epoch = (date - epoch_date).days
    return (DAY_KEY_INDEX[epoch_day_key] + days_since_epoch) % CYCLE_LENGTH_DAYS


def day_key_for_date(date, epoch_date, epoch_day_key):
    return DAY_KEY_ORDER[cycle_index_for_date(date, epoch_date, epoch_day_key)]


def day_key_for_date_in_season(date, seasons):
    """Season-anchored resolution: each season restarts the fortnight on its startDayKey.

    This is what the workbook's per-season "2026 Start Day" column implies (Ostara and
    Fimbulsumar begin on Sunday B, the other three on Sunday A). Returns (day_key, start_date, season),
    or None when no season of the list has started by `date`."""
    found = season_for_date(seasons, date)
    if found is None:
        return None
    start_date, season = found
    anchor_date = season_anchor_date(start_date, season["startDayKey"])
    return day_key_for_date(date, anchor_date, season["startDayKey"]), start_date, season


def day_key_for_date_person_first(date, person_seasons, workbook_seasons):
    """The day key by the person's own seasons when one has started by `date`, else by the workbook seasons."""
    resolved = day_key_for_date_in_season(date, person_seasons) if person_seasons else None
    if resolved is None:
        resolved = day_key_for_date_in_season(date, workbook_seasons)
    return resolved[0]


def season_for_date_person_first(date, person_seasons, workbook_seasons):
    """The season `date` falls in by the person's own seasons when one has started by then, else by the
    workbook seasons (the season a generator proposal is made for); None when neither has one."""
    found = season_for_date(person_seasons, date) if person_seasons else None
    if found is None:
        found = season_for_date(workbook_seasons, date)
    return found[1] if found else None


def parse_iso_date(text):
    return datetime.date.fromisoformat(text)
