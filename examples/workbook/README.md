# The workbook example set

The original FortKnight workbook (`source/FortKnight.xlsx`, `docs/workbook-mapping.md`) as **sample data**:
`activities.json` (64 activities), `days.json` (the 14-day block focus grid), `menus/spooky-season.json`,
`weights.baseline.json` (the historical baseline weights). It is an **overlay** on the person-neutral
`data/`: files here replace the same-named canonical files, its menus are added, everything else
(categories, blocks, seasons, questionnaire, schemas) comes from `data/`.

```
python3 scripts/validate.py --overlay examples/workbook
python3 scripts/build.py --overlay examples/workbook --out build/examples/workbook   # gitignored demo bundle
python3 scripts/analyze_allocations.py --overlay examples/workbook
```
Tests load it as `WORKBOOK_DATA` (`tests/helpers.py`). Its import document (`build/examples/workbook/derived/defaultImport.json`)
is what a person would apply on the Assistant page (*Apply from assistant*) to make this schedule theirs; the owner's own
copy with full detail and menus is `source/import.my-activities.json`.
