"""fk_core — shared, stdlib-only building blocks for FortKnight tooling.

Each module has one responsibility:
- timeconv.py         Excel fractions <-> "HH:MM" <-> minutes (twin: src/lib/shared/clock.js)
- keys.py             slugs, day-key order, meal-key normalization
- dates.py            season start rules and calendar date -> day key resolution
- astronomy.py        equinoxes, solstices and new moons (twin: src/lib/shared/astronomy.js)
- json_io.py          deterministic JSON read/write and repository paths
- validate.py         JSON-Schema-subset validator + referential integrity rules
- no_schedules.py     the privacy guard: this repository holds nobody's schedule
- import_document.py  a person's existing system, as their assistant read it
- meal_plan.py        the fortnight menu
- weights.py          questionnaire answers -> weights

The builder half — build.py's chain, generator.py, allocations.py, derive.py, xlsx.py and parse.py —
was removed on 2026-08-30 with the creation chain (docs/megaseed/display-only-face.md) and is preserved
at the tag `creation-chain-parked`. What remains is what validate.py and the privacy guard need.
"""
