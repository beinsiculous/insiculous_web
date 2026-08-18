"""Import adapters (future): bring existing calendars into FortKnight's shape.

Nothing here talks to a network yet. The only contract is `ExternalEvent` and the `Importer`
protocol below, so Google Calendar / spreadsheet / photo importers can be added one file each.
"""
from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class ExternalEvent:
    source: str                     # "google-calendar" | "spreadsheet" | "image" | ...
    id: str                         # stable id within the source
    title: str
    start: str                      # ISO 8601 date-time (or date when allDay)
    end: str
    allDay: bool = False
    raw: dict = field(default_factory=dict)   # untouched source payload
    suggestedCategories: list = field(default_factory=list)  # category keys, filled by a classifier later
    notes: Optional[str] = None


class Importer(Protocol):
    source: str

    def load(self) -> list:
        """Return a list of ExternalEvent. Must not mutate anything under data/."""
