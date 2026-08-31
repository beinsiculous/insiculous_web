# Reading a spreadsheet into an import document

> **Parked design — not implemented on this site.** This document is the design record of the
> creation chain, which was removed from `main` on 2026-08-30 by the display-only ruling
> (`docs/megaseed/display-only-face.md` in the working set) and is preserved at the annotated tag
> `creation-chain-parked`. **Nothing on beinsiculous.com runs any of it.** The face reads a keep the
> visitor loads and renders it; it builds nothing. The slab-upload builder that will return to
> `/fortknight/keep/` (`beinsiculous/insiculous_web#24`) is a new writer, not this chain coming back
> — its model is `docs/megaseed/name-drop.md`. Read what follows as history and as a contract, not as
> a description of running code.
>
> Code removed with it: `scripts/xlsx_to_json.py` and `scripts/fk_core/xlsx.py` (and `parse.py`), so
> the repository no longer has an `.xlsx` reader. The import-document contract it targets is
> `docs/importers.md`, also parked.

You (an assistant in the person's workspace) were handed a spreadsheet — an `.xlsx`, a Google
Sheets export, a `.csv` — that holds their existing schedule: a timetable, a chore rota, a list of
appointments, a bill calendar, a fortnight grid. Your job is to hand back **one import document**
(version 2) that the person pastes into the app's **Assistant page → Apply from assistant, step 2**. They will read that JSON before applying it, so it has to
be right *and* checkable: one readable line per commitment, the tasks, everything you left out with
the reason, and a short review with counts.

This page is enough on its own — the field grammar is in §3 and the shape in §8. If you also have
the FortKnight workspace files, `importers.md` is the full contract and `import.schema.json` the
schema.

## 0. Before you write
- **Do not ask a round of questions first.** Read everything, decide, and write the document with
  your assumptions listed under `review` (and `from` on the record). The person removes a wrong line
  in one tap; a questionnaire from you costs them more.
- Ask only when a whole sheet is unreadable to you (a photo of a sheet, a language you cannot
  read, colour-coded cells whose legend is missing).
- Never invent an entry the spreadsheet does not contain. Never silently drop one — that is what
  `skipped` is for.

## 1. Survey the workbook
List every sheet (hidden ones included), its size, and its header row. Classify each sheet:

| layout | what it looks like | what it becomes |
|---|---|---|
| **event list** | one row per thing: title, day/date, start, end or length, maybe a repeat/frequency column, notes | commitments (rows with a clock time), tasks (rows with a day but no time) |
| **weekly grid** | weekdays across the top (or down the side), time slots or periods the other way, entries in the cells | commitments — every non-empty cell is one, `repeats: "every week"`, weekday from the column, start from the row |
| **rota / checklist** | chores or duties with a frequency ("weekly", "Tue/Thu", "1st of month") and maybe a person | tasks (no time) or commitments (a time is given); a rota for several people: only this person's rows, the rest under `skipped` |
| **fortnight grid** (FortKnight-style) | day keys `sun-a … sat-b`, blocks `early / midday / late`, a focus per cell and a schedule sheet | the machine sections `blockFocusGrid`, `fixedActivities`, `appointmentBlocks` beside the readable lists — see §7 |
| **reference** | budgets, menus, shopping lists, notes, totals, a legend | not commitments: one `skipped` line per sheet naming why (a menu may ride along under `meals`) |

Note the sheet name and row numbers as you go — every record's `from` should let the person find
it again ("Sheet 'Rota', row 12").

## 2. What each row becomes
| the row has… | it becomes | note |
|---|---|---|
| a clock time (start, or start + end) and a day, weekday or repeat rule | **commitment** | work or school hours count — they are the biggest anchors |
| a day, weekday or frequency but no clock time | **task** — with a `when` word if the sheet hints at one (a "morning / evening" column, "after dinner", "AM/PM") | chores, errands, "call mum", "water plants" |
| a clock time but no day at all (a template of a day) | **task** with `repeats: "every week"` on every weekday and a `start` — and a review line saying you assumed daily | |
| a one-off in the past | **skipped** — "before today" | keep future one-offs (`once on YYYY-MM-DD`) |
| an all-day event, birthday, holiday, "reminder" with no time | **skipped** — "all-day, no time" | |
| a cancelled or struck-through entry, a "(old)" tab | **skipped** — say why | |
| a total, subtotal, header, legend, empty row | nothing — but count them in `review` ("6 rows were headers/totals") | |
| an entry you cannot read (merged cells with no meaning, a colour with no legend) | **skipped** — "could not read: …" | |

## 3. Field by field
- **`title`** — the person's own words for it, tidied: "Piano w/ Ms Ito (Tue)" → `Piano lesson`,
  keep the person's names ("Mum", "Dr Patel"). Never a cell code or an id.
- **`repeats`** — exactly one of five phrases: `every week` · `every other week from YYYY-MM-DD` ·
  `monthly on the 2nd tuesday` (1st–4th or last) · `monthly on day 15` · `once on YYYY-MM-DD`:
  | the sheet says | write |
  |---|---|
  | a weekday column in a grid; "weekly", "every Tuesday", "Tue/Thu", "wk" | `every week` + `weekdays` |
  | "biweekly", "every other week", "fortnightly", "alternate weeks", dates 14 days apart | `every other week from YYYY-MM-DD` — the date of one occurrence you saw — **and `weekdays` named explicitly** (`["wednesday"]`), even though the date implies it: the app rejects an every-other-week record without a weekday. If no occurrence is dated, use the first date in the sheet's range and say so in `review` ("biweekly" can also mean twice a week — if the sheet shows two weekdays, it is `every week` on both) |
  | "monthly", "1st Tue", "last Friday", "second Sunday" | `monthly on the 2nd tuesday` / `monthly on the last friday` |
  | "monthly", "on the 15th", "1st of month", a bill due-day column | `monthly on day 15` |
  | one dated row, "one-off", a due date | `once on YYYY-MM-DD` |
  | rows with dates: same weekday every 7 days → weekly; every 14 → every other week; same day-of-month → monthly on day N; same ordinal weekday → monthly on the Nth weekday; a single date → once. Say in `review` how many dated rows you collapsed into one line. |
- **`weekdays`** — full names or `Mon`; **required for `every week` and `every other week`** (for
  every-other-week the `from` date does not replace it — name the weekday too); not needed for the
  monthly / once forms (the phrase names the weekday for "monthly on the 2nd tuesday"). A grid
  column "M T W T F" → spell each out.
- **`start`** — `9:30 AM` or `09:30`. Excel stores times as day fractions (`0.5` = 12:00 PM,
  `0.375` = 9:00 AM) and dates as serials (`46086` = 2026-03-05): read the *displayed* value when you
  can, convert when you must. A bare "9" or "3" is ambiguous — assume 9 AM / 3 PM by context
  (school, work, dinner) and add a review line.
- **`lasts`** — end minus start (`1 h 30 min`); a "duration"/"hours" column; a grid slot's height.
  Nothing at all → `1 h` for commitments and say so in `review` (the app's default guess); tasks may
  leave it out.
- **`category`** — one of the seven, by key or label. Typical mappings:
  | words in the sheet | category |
  |---|---|
  | work, shift, office, client, meeting, standup, commute, class you teach | `working` |
  | school, class, lecture, course, lesson (music, language, art), study, church, meditation, journaling, therapy-as-growth | `spirituality-development` |
  | doctor, dentist, physio, therapy, gym, run, swim, medication, sleep routine | `health` |
  | dinner with, date, kids' pickup, playdate, call mum, family, birthday party, pet | `friends-family` |
  | groceries, cook, meal prep, lunch, dinner (the meal itself) | `meals` |
  | laundry, bins, clean, tidy, vacuum, dishes | `cleaning` |
  | bills, rent, bank, taxes, insurance, car service, repairs, admin, errands, shopping (non-food) | `operations` |
  A row that fits two ("dinner with Mum") takes the *reason* it exists (`friends-family`); when
  you cannot tell, `health` for appointments and `operations` for tasks, with a review line.
- **`when`** (tasks) — `morning`, `midday`, `afternoon`, `evening`, `night` from a slot column or the
  words ("before work", "after dinner" → morning / evening); nothing → `anytime`.
- **`from`** — sheet + row/cell and anything that helps the check: `"Sheet 'Rota' row 12; 'bins Tue' —
  time not given"`.

## 4. Spreadsheet traps
- **Merged cells** span days or hours: one entry per day it covers, or a longer `lasts`.
- **Hidden sheets and hidden rows** are still the person's data — read them, and say in `review`
  that you did.
- **Formulas**: use the shown value; if only the formula is visible, compute it and note it.
- **Colours and symbols** ("x", "✓", "●") in a grid mean "yes here" — an entry with the row/column
  meaning; a colour legend that is missing → skip those cells with "colour meaning unknown".
- **Repeated header rows**, frozen panes, a second table below the first: survey the whole sheet,
  not just the top.
- **Two people in one rota**: only this person's entries become commitments/tasks; the others go
  under `skipped` in one line ("11 rows are Sam's").
- **Dates without a year** (a printed calendar): assume the current or next occurrence and say so.

## 5. Completeness check (do this before you write)
For each sheet: rows read → entries produced (commitments + tasks) + skipped + headers/totals.
Those numbers must add up, and they go into `review`:
```
"Sheet 'Week' (grid, Mon–Fri × 7 slots): 23 filled cells → 23 commitments.",
"Sheet 'Rota': 14 rows → 9 tasks, 3 commitments, 2 skipped (Sam's).",
"Sheet 'Bills': 8 rows → 8 commitments (monthly on day N, 15 min each — durations assumed).",
"Skipped whole sheets: 'Menu' (a menu, no schedule), 'Notes'."
```
Then re-read your `commitments` list as the person would: is every line something they would
recognise from their own sheet? Is anything missing that was in the sheet?

## 6. Output
Answer with a short prose summary (what you read, what you assumed, what to check) and then
**exactly one** fenced JSON document — no other code blocks, no partial documents:
- `schemaVersion: 2`; `source: {"kind": "xlsx", "description": "<file name>: sheets <names>, <N> rows read, <date range if any>", "importedAt": "<today>"}`.
- `commitments`, `tasks`, `skipped`, `review` as above; `notes` only for things about the document
  itself.
- Every `repeats` is one of the five phrases; every `every week` / `every other week` record names
  its `weekdays`; every `start` is `H:MM AM/PM` or `HH:MM`; every `weekdays` entry is a weekday
  name; every `category` is one of the seven — the app rejects a
  record it cannot read and lists it under *Not applied*, so re-check the grammar before sending.
- Keep it valid JSON: straight quotes, no trailing commas, no comments.

## 7. A FortKnight-style workbook (day keys and blocks)
When the sheet *is* a fortnight grid — a Days sheet with `sun-a … sat-b` and an early / midday /
late focus per day, a Schedule sheet with day key, block, priority, times — you can also fill the
machine sections (`importers.md` → Machine sections): `blockFocusGrid` from the focus cells,
`fixedActivities` from the schedule rows (`id = slug(title)--dayKey--block`, `priority`,
`flexibility`, `timing`), `appointmentBlocks` if the sheet has them, `blocks` from a Blocks sheet.
`workbook-mapping.md` in the repository documents exactly that mapping for the original workbook
(`scripts/build.py --overlay examples/workbook` produces it as an import document). Still write the
readable `commitments` for the timed rows: that is what the person reads.

## 8. Worked example
Workbook `home.xlsx`, two sheets.

*Sheet "Week"* (grid; columns Mon–Fri, rows 07:00…20:00, one-hour slots):
```
        Mon        Tue         Wed        Thu        Fri
09:00   work       work        work       work       work
…       …          …           …          …          …
17:00   work       work        work       work       work
18:00              football                          
19:00                          band                  
```
*Sheet "Rota"* (list):
```
Task              How often        When      Who
Bins out          Tue              evening   me
Hoover            weekly Sat       —         me
Rent              1st of month     —         me
Call Mum          Sun              afternoon me
Dishwasher        daily            —         Sam
```
Reply:
```json
{
  "schemaVersion": 2,
  "source": {"kind": "xlsx", "description": "home.xlsx: sheets 'Week' (Mon–Fri grid, 07:00–20:00) and 'Rota' (5 rows)", "importedAt": "2026-08-16"},
  "commitments": [
    {"title": "Work", "repeats": "every week", "weekdays": ["monday", "tuesday", "wednesday", "thursday", "friday"], "start": "9:00 AM", "lasts": "8 h", "category": "working", "from": "'Week' 09:00–17:00 columns Mon–Fri (merged block per day)"},
    {"title": "Football", "repeats": "every week", "weekdays": ["tuesday"], "start": "6:00 PM", "lasts": "1 h", "category": "health", "from": "'Week' Tue 18:00 — one slot, 1 h assumed"},
    {"title": "Band", "repeats": "every week", "weekdays": ["wednesday"], "start": "7:00 PM", "lasts": "1 h", "category": "spirituality-development", "from": "'Week' Wed 19:00 — one slot, 1 h assumed"},
    {"title": "Rent", "repeats": "monthly on day 1", "start": "9:00 AM", "lasts": "15 min", "category": "operations", "from": "'Rota' row 4 — no time in the sheet; 9:00 AM and 15 min assumed"}
  ],
  "tasks": [
    {"title": "Bins out", "repeats": "every week", "weekdays": ["tuesday"], "when": "evening", "lasts": "10 min", "category": "cleaning", "from": "'Rota' row 2"},
    {"title": "Hoover", "repeats": "every week", "weekdays": ["saturday"], "when": "anytime", "lasts": "30 min", "category": "cleaning", "from": "'Rota' row 3 — 30 min assumed"},
    {"title": "Call Mum", "repeats": "every week", "weekdays": ["sunday"], "when": "afternoon", "category": "friends-family", "from": "'Rota' row 5"}
  ],
  "skipped": [
    {"title": "Dishwasher (daily)", "why": "'Rota' row 6 is Sam's, not yours"}
  ],
  "review": [
    "'Week': 43 filled cells → 3 commitments (the 09:00–17:00 work block collapsed to one line per weekday set; football and band one slot each, 1 h assumed).",
    "'Rota': 5 rows → 3 tasks, 1 commitment (Rent given a clock time so it anchors the day — remove it and re-add as a task if you prefer), 1 skipped.",
    "Guessed: durations for Football, Band, Hoover; Rent's time; categories from the words alone."
  ]
}
```
