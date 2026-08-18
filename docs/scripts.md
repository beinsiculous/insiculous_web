# Scripts

All scripts are Python 3 standard library only, run from the repository root, exit non-zero on error, and support `--help`.

| script | purpose | typical use |
|---|---|---|
| `scripts/validate.py [data-dir] [--overlay DIR]` | schema-subset check + referential rules (day keys, blocks, categories, meal refs, menu completeness, monotonic times, appointment-block warnings) | after every data edit |
| `scripts/build.py [--data] [--overlay DIR] [--out]` | validate → derive (`menuByDay`, `planByDay`, `allocations`, `defaultImport` — the data set as an import document, validated) → `build/fortknight.bundle.json`; `--overlay examples/workbook --out build/examples/workbook` builds the sample's demo bundle (gitignored) | before committing / running the app |
| `scripts/analyze_allocations.py [--overlay DIR] [--json] [--weights-out PATH]` | minutes and shares per category / day / block, two views (block focus vs actual activities); optionally emit baseline weights | understanding a data set; producing `examples/workbook/weights.baseline.json` (the neutral data allocates everything to flexible) |
| `scripts/questionnaire_to_weights.py ANSWERS --id ID [--out PATH] [--answered-at DATE] [--date DATE]` / `--defaults` | questionnaire answers (`docs/questionnaire.md`) → validated weights file, `proposal` included (`--date`: the season it is made for, default today) | producing `data/weights.<id>.json` outside the app |
| `scripts/generate_grid.py WEIGHTS [--date DATE] [--answers ANSWERS] [--overlay DIR] [--table]` | the generator (`docs/generator.md`): a weights file → proposed block focus grid, reasons, warnings, diff against the file's grid, and the activities proposed inside the cells; the season by the file's own answers (or `--answers`) first, FortKnight's otherwise | trying the generator on a weights file (`--table` for a readable grid) |
| `scripts/resolve_date.py DATE [--json] [--plan] [--answers ANSWERS] [--overlay DIR]` | calendar date → day key, cycle index, week, season (season-anchored; with `--answers` by that person's own seasons — their year split + week start — falling back to FortKnight's seasons, `seasonSource` says which) and optionally that day's plan (of the data set — empty on the neutral data) | "what is today?" |
| `scripts/xlsx_to_json.py [--xlsx] [--out] [--dry-run]` | workbook → the `examples/workbook/` shape (deterministic output; refuses `--out data/`) | reference / re-convert only when explicitly wanted |
| `python3 -m unittest discover tests` | tests | always |

Shared logic is in `scripts/fk_core/` — one module per responsibility (see its `__init__.py`).
`scripts/importers/` holds only the interface for future calendar/spreadsheet/photo importers.

## Data sets: `--overlay`
`data/` is the person-neutral canonical set. A sample set such as `examples/workbook/` is an
**overlay**: `fk_core.json_io.load_data_directory(data, overlay)` takes a same-named file from the
overlay when it exists (`activities.json`, `days.json`, `weights.baseline.json`, …) and adds its
`menus/*.json`; everything else comes from `data/`. Every script above takes `--overlay DIR`.
