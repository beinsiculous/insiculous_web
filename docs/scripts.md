# Scripts

All scripts are Python 3 standard library only, run from the repository root, exit non-zero on error, and support `--help`.

| script | purpose | typical use |
|---|---|---|
| `scripts/validate.py [data-dir] [--overlay DIR]` | schema-subset check + referential rules (day keys, blocks, categories, meal refs, menu completeness, monotonic times, appointment-block warnings), plus the no-schedules privacy sweep | after every data edit |
| `python3 -m unittest discover tests` | tests | always |

That is the whole list. There is no build step: `validate.py` checks `data/`, and nothing turns
`data/` into anything the site serves.

The `.mjs` gates are the other half of `npm run verify`, and they are Node, not Python:
`scripts/postbuild-check.mjs` (structure, static a11y and prose, over every built page),
`scripts/a11y-check.mjs` (axe-core, WCAG 2.2 AA, over every built page) and
`scripts/screenshot-pages.mjs` (every page answers 200 and none scrolls sideways, at four viewport
passes). All three walk `dist/`, so a new page is covered the moment it builds.

Shared logic is in `scripts/fk_core/` — one module per responsibility (see its `__init__.py`).
`scripts/importers/` holds only the interface for future calendar/spreadsheet/photo importers.

## The six CLIs that are gone

Removed on 2026-08-30 with the creation chain (`docs/megaseed/display-only-face.md` in the working
set), along with `npm run data`, and preserved at the annotated tag `creation-chain-parked`:

| script | what it did |
|---|---|
| `build.py` | validate → derive → `build/fortknight.bundle.json`, the bundle the site used to import |
| `analyze_allocations.py` | minutes and shares per category / day / block; produced the baseline weights |
| `questionnaire_to_weights.py` | questionnaire answers → a validated weights file |
| `generate_grid.py` | the generator: a weights file → a proposed block focus grid |
| `resolve_date.py` | calendar date → day key, cycle index, week, season, and that day's plan |
| `xlsx_to_json.py` | the workbook → the `examples/workbook/` shape |

Half of `fk_core` went with them — `generator.py`, `allocations.py`, `derive.py`, `xlsx.py`,
`parse.py` — because nothing else reached those modules. Recover any of them with
`git show creation-chain-parked:<path>`, but read `docs/app.md`'s recovery note first: the tag pins
the 2026-08-26 snapshot, which predates the 2026-08-28/29 naming settlements, so a file's state at
removal comes from `main` history instead.

If a doc, comment or habit tells you to run one of these, it is stale — say so rather than reviving
it.

## Data sets: `--overlay`
`data/` is the person-neutral canonical set. A sample set such as `examples/workbook/` is an
**overlay**: `fk_core.json_io.load_data_directory(data, overlay)` takes a same-named file from the
overlay when it exists (`activities.json`, `days.json`, `weights.baseline.json`, …) and adds its
`menus/*.json`; everything else comes from `data/`. `validate.py` is now the only script that takes
`--overlay`; `tests/helpers.py` loads the overlay the same way for the test suite.
