"""fk_core — shared, stdlib-only building blocks for FortKnight tooling.

Each module has one responsibility:
- xlsx.py         read cells (and formula text) out of an .xlsx without openpyxl
- timeconv.py     Excel fractions <-> "HH:MM" <-> minutes
- keys.py         slugs, day-key order, meal-key normalization
- parse.py        parse the free-text "Link/Tasks" column into structured detail
- dates.py        season start rules and calendar date -> day key resolution
- json_io.py      deterministic JSON read/write and repository paths
- validate.py     JSON-Schema-subset validator + referential integrity rules
- derive.py       derived views (menu by day, plan by day) built from canonical data
- allocations.py  time groupings per category (the weights baseline)
- weights.py      questionnaire answers -> weights (mirrored by src/lib/shared/weights-rules.js)
"""
