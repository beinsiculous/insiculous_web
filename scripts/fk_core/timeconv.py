"""Conversions between Excel day fractions, "HH:MM" strings, and integer minutes."""
import math
import re

MINUTES_PER_DAY = 24 * 60
# Every minutes answer lands on a five-minute mark: a person's unrounded input rounds *up* to the next
# one (a 12-minute walk is booked as 15). Mirror of src/lib/shared/clock.js — keep both in sync.
MINUTE_GRID_MINUTES = 5
TIME_PATTERN = re.compile(r"^(\d{2}):(\d{2})$")


def fraction_to_minutes(fraction):
    return int(round(float(fraction) * MINUTES_PER_DAY))


def minutes_to_time_string(minutes):
    """0 -> "00:00", 1440 -> "24:00" (used only for a block ending at midnight)."""
    hours, remainder = divmod(int(minutes), 60)
    return f"{hours:02d}:{remainder:02d}"


def time_string_to_minutes(time_string):
    match = TIME_PATTERN.match(time_string)
    if not match:
        raise ValueError(f"not an HH:MM time: {time_string!r}")
    return int(match.group(1)) * 60 + int(match.group(2))


def fraction_to_time_string(fraction):
    return minutes_to_time_string(fraction_to_minutes(fraction))


def duration_minutes(start_time_string, end_time_string):
    return time_string_to_minutes(end_time_string) - time_string_to_minutes(start_time_string)


def round_up_to_grid(minutes, grid=MINUTE_GRID_MINUTES):
    """The next five-minute mark at or above `minutes` (see MINUTE_GRID_MINUTES)."""
    return int(math.ceil(float(minutes) / grid) * grid)
