# Importers — turning an existing system into FortKnight objects

People arrive with a system already: a hand-written planner, a spreadsheet, a Google Calendar,
an `.ics` export, a photo of the fridge whiteboard. FortKnight does not want them to retype it.
A future **Import** section of the app (and, for scripts/assistants, the same contract) turns
such a source into **usable objects** and hands them to the questionnaire and, later, to the
generator. This document is that contract; nothing here calls a server and the app calls no AI
(`docs/assistant-workspace.md`: the person's own assistant, in their own workspace, produces the
document; the source material never leaves the device except when the person uploads it there).

## The import document (`data/schema/import.schema.json`)
The document is **written for the person to read**: they will look at it and decide whether the
list of their commitments is right and complete before they Apply it. Version 2 (the current
shape) is one readable record per commitment, plus what the importer *left out* and a summary:
```json
{
  "schemaVersion": 2,
  "source": {"kind": "google-calendar", "description": "Jesse's Google Calendar, events 2026-08-01 → 2026-11-30, read 2026-08-16", "importedAt": "2026-08-16"},
  "commitments": [
    {"title": "Piano lesson", "repeats": "every week", "weekdays": ["friday"], "start": "2:00 PM", "lasts": "2 h 15 min", "category": "spirituality-development", "from": "'Piano w/ Ms. Ito' — 12 occurrences seen"},
    {"title": "Choir", "repeats": "every other week from 2026-09-02", "weekdays": ["wednesday"], "start": "6:30 PM", "lasts": "1 h 30 min", "category": "spirituality-development"},
    {"title": "Book club", "repeats": "monthly on the 2nd tuesday", "start": "7:00 PM", "lasts": "2 h", "category": "friends-family"},
    {"title": "Rent", "repeats": "monthly on day 1", "start": "9:00 AM", "lasts": "15 min", "category": "operations"},
    {"title": "Dentist", "repeats": "once on 2026-10-14", "start": "9:30 AM", "lasts": "1 h", "category": "health"}
  ],
  "tasks": [
    {"title": "Take out the bins", "repeats": "every week", "weekdays": ["tuesday"], "when": "evening", "lasts": "10 min", "category": "cleaning"}
  ],
  "skipped": [{"title": "Mom's birthday", "why": "all-day event, no time — a day note, not a commitment"}],
  "review": ["14 recurring events and 3 one-offs found; 5 imported as commitments, 1 as a task, 2 skipped (listed); durations guessed for 'Book club' (no end time) → 2 h"]
}
```
`tests/fixtures/import.v2.sample.json` is the complete example; `tests/fixtures/import.sample.json`
is a version-1 document (still valid). **`docs/import-from-spreadsheet.md` is the method** — how an
assistant reads an `.xlsx`, a Sheets export or a calendar dump into this document, with a worked
example; it is published into the workspace file set beside this page.

### Writing it (for importers and assistants)
- **`commitments`** — timed things: appointments, lessons, therapies, meetings, work or school
  hours, standing calls. One record each; they become the person's commitments (the standing
  appointments listed and edited on the Build page, `/fortknight/build/`) and anchor their day's blocks.
- **`tasks`** — recurring things to do that have a day but no fixed clock time (chores, errands,
  "call mum on Sundays"). They show on the day pages in the block their `when` falls in; they never
  anchor anything.
- **`skipped`** — every source entry you saw and did **not** bring in, with the reason (all-day
  event, cancelled series, a birthday, a duplicate, outside the date range you scanned). This is
  how the person judges *completeness* — write it even when it is long.
- **`review`** — your summary for the reader: what you scanned (source, date range), how many you
  found / imported / skipped, and every guess you made (a duration with no end time, a category you
  inferred, a series you collapsed into one line). Unknown durations default to 60 minutes and
  unknown categories to `health`, each with a `review` line (or a `from` on the record).
- **`from`** on a record — where it came from, so the person can match it against their calendar.
- Titles are the person's own words for the thing, not the calendar's internal names.

| field | how to write it |
|---|---|
| `repeats` | `every week` · `every other week from YYYY-MM-DD` (the date of one occurrence) · `monthly on the 2nd tuesday` (`1st`–`4th` or `last`; the phrase names the weekday) · `monthly on day 15` · `once on YYYY-MM-DD` |
| `weekdays` | `["monday", "thursday"]` — full names or `Mon`; **required for `every week` and `every other week`** (the every-other-week date does not stand in for it — name the weekday explicitly); not needed for the monthly and once forms |
| `start` | `2:00 PM`, `2 pm` or `14:00` (commitments always; tasks only when they have one) |
| `lasts` | `2 h 15 min`, `90 min`, `1 h`, or integer minutes (tasks may leave it out) |
| `when` | tasks without a `start`: `morning` (09:00) · `midday` (12:00) · `afternoon` (15:00) · `evening` (19:00) · `night` (21:00) · `anytime` — the clock time in brackets is what the day page places it by |
| `category` | a `categories.json` key (`friends-family`) or label (`Friends & Family`) |
| `source.kind` | `text` · `photo` · `xlsx` · `ics` · `google-calendar` · `other` |

The five `repeats` forms are the five canonical cadences (`weekly`, `every-other-week` +
`firstDate`, `monthly-nth-weekday` + `nth`, `monthly-date` + `dayOfMonth`, `one-off` + `date`).
`normalizeImportDocument()` in `src/lib/shared/import-document.js` (Python:
`fk_core/import_document.py`) turns the readable records into those canonical objects on read
— the app stores what was pasted, never the normalized copy — and reports anything it cannot read
("commitments #2 "Choir": cannot read "sometimes" — use …"); such a record is left out and listed
under *Not applied* in the review, the rest still applies.

### Machine sections (version 1; still valid in version 2)
Alongside the readable lists a document may carry the objects the app consumes directly — an
assistant-authored agenda (`docs/llm-guide.md` → *Building the person an agenda*), the workbook
example (`build.py --overlay examples/workbook`), a future deterministic `.ics`/`.xlsx` importer:
- `standingAppointments[*]` — **exactly** the standing-appointment shape the Build page writes
  (`docs/questionnaire.md` → Startup 2's answer keys): `title`, `weekdays[]`, `start` (`HH:MM`),
  `durationMinutes`, `category` (a `categories.json` key), and `cadence`:
  | `cadence.kind` | extra field | meaning |
  |---|---|---|
  | `weekly` | — | every listed weekday, every week |
  | `every-other-week` | `firstDate` (ISO) | every listed weekday, on the fortnight week `firstDate` falls in |
  | `monthly-nth-weekday` | `nth` 1–4 or -1 (last) | e.g. first Thursday |
  | `monthly-date` | `dayOfMonth` 1–31 | `weekdays` may be empty |
  | `one-off` | `date` (ISO) | a single occurrence |
- `fixedActivities[*]` follow `data/activities.json` (`id`, `title`, `dayKey`, `block`, `priority`,
  `categories`, `flexibility`, `timing`); the timed ones with `priority 1` or `flexibility "no"`
  become block-split anchors (`blockSplit.anchors[*].source: "import"`).
- `blocks` is the source system's day layout (same item shape as a weights file's `blocks`;
  informational — a person's blocks always come from their own answers).
- `blockFocusGrid` is `{dayKey: {focusBlockKey: focus}}` (focus = a category key or `flexible`);
  the questionnaire copies it into the weights for the block keys the profile has (the rest is
  dropped with a warning) — that grid is what FortKnight's Overview shows.
- `appointmentBlocks` is `{dayKey: blockKey}` — the block each day opens for appointments.
- `mealPlan` — the ForkKnife menu (`docs/meal-plan.md`): `{items[{meal, dish, days[1–2], notes?}]}`; the tasks document ForkKnife creates carries it next to its prep/cook `tasks`, and Apply merges it into the profile's meal plan.
- `meals` is **reserved** for the weights/generator: the shape follows `data/menus/*.json` meals
  (`slot`, `menu`, `days[]` or `dayKey`, `cookExtra`); the questionnaire ignores it, but the day
  pages (`/fortknight/days/<dayKey>/`) list the entries of a day as its menu line, so a person's menus can
  travel in their document.
- `notes[]` — free strings.

**The default paste is a short empty example.** `scripts/build.py` writes the data set as an import
document (`build/derived/defaultImport.json`, `bundle.derived.defaultImport`); on the neutral
canonical `data/` that is a version-2 document with empty lists and a `review` telling the person
what to do — a fresh device starts blank. **The workbook is an import document too**: the same
builder on the workbook example set (`--overlay examples/workbook`) yields the workbook itself
(`source.kind: "xlsx"`, all 64 fixed activities, the five blocks, the 14-day focus grid, appointment
blocks and its menu meals under `meals`); the owner's own copy is `source/import.my-activities.json`.
Nothing in the app reads a data set's grid or activities as a person's own: a schedule enters a
profile only through this document.

`fk_core.validate.check_import_document()` validates a document (schema, the readable fields
parsed, then the cadence rules on the result); `tests/test_import_document.py` runs the Python and
JavaScript normalizers on the same fixture and asserts identical output.

## Where it goes
- **Assistant page, Apply from assistant** — paste or upload the document and Apply
  (`applyImportDocument()` in `src/lib/shared/weights-rules.js`): its commitments / `standingAppointments`
  are appended to the person's commitments and its tasks to their tasks (the Build page's read-only
  lists, deduplicated on title + start/time of day + weekdays),
  the document itself is kept as `startup.import` (raw text under `startup.importJson`) and, on the
  next derivation, its fixed activities anchor the block split, its `blockFocusGrid`/`appointmentBlocks`
  land in the weights. A **review** appears under the box
  (`renderImportReview()` in `src/lib/shared/import-review.js`): the commitments and tasks as readable rows,
  what the assistant skipped and why, its review lines, and anything not applied — with a
  ready-made message (`retryMessage()`: the problems plus the offending records) to paste back into
  the chat the document came from, so the assistant fixes and resends the whole document.
- **Questionnaire, Startup 2** — a one-line note that a document was applied plus only the parts of the
  review the lists cannot show (what the assistant skipped, its review lines, parse problems —
  `renderImportReview(…, { listApplied: false })`), and a count of the commitments and tasks the profile
  now holds. A *Forget the applied import* link drops the document; the commitments and tasks it added
  stay in the profile until removed by hand.
- **Build page** (`/fortknight/build/`) — where the commitments and tasks themselves are listed, and
  where the person adds their own, one at a time, without any assistant.
- **An assistant-authored agenda** is this document too: when the person asks their assistant to
  draft the fortnight, it answers with `source.kind: "other"`, a `blockFocusGrid` over the person's
  own focus block keys, `fixedActivities` for the few timed anchors, and `notes` for its
  assumptions (`docs/llm-guide.md` → *Building the person an agenda*). Applying it replaces the
  previously applied document.
- **Overview `/fortknight/`** — renders the person's blocks with the imported focus per block, `•` on
  the appointment block / standing appointments, an "appointments" tag on their appointment
  weekdays; nothing imported → the blocks show `—`.
- The generator (`docs/generator.md`) proposes a grid from weights on `/fortknight/` (adopting it writes the person's own `answers.blockFocusGrid`, the import stays as it was); later: proposed activities, `meals`, exporters that push plans back out.

## The Import page (not built yet; on the back burner — `insiculous/docs/roadmap-fortnight-apps.md`)
Planned flow, all on-device:
1. The person pastes text or drops a file (photo, `.xlsx`, `.ics`); Google Calendar read-only OAuth later.
2. For free text and photos the person hands the material to the assistant in their workspace,
   whose README already carries this contract and the instruction to answer with **only** an import
   document — unknown durations default to 60 minutes, unknown categories to `health` for
   appointments, with a note explaining each guess.
3. The reply is validated (same rules as `check_import_document`), shown as a review table
   (done today, read-only: *Apply from assistant* on `/fortknight/assistant/` — built on the parked
   `fortknightdev` playground branch; ForkKnife's own assistant page went with the `/forkknife/`
   routes — and again under Startup 2 on `/fortknight/questionnaire/`; what landed is listed on `/fortknight/build/`),
   then applied to the saved answers; still open: editing rows in that table before applying.
`.ics` and `.xlsx` can be parsed without any assistant (deterministic importers under
`scripts/importers/` / `src/lib/shared/importers/`).
