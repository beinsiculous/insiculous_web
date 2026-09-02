# The keep format: a fortnight you can write by hand

A **keep** is a small JSON file describing one fourteen-day fortnight — what is eaten, what is
booked, and what each block of each day is for. The planner app writes one; `/fortknight/keep/`
draws it. This document is the format's specification, written for a person making a keep by hand
in a text editor, and it is canonical: the machine schema beside it is
`data/schema/keep.schema.json`, and the reader that decides whether a page can draw your file is
`src/lib/keep.js`.

You do not need the app. A keep you write yourself is a first-class keep, and it is checked against
the same schema as one the app exports.

**Where this file sits in the chain** (Operation Name Drop, 2026-08-30 —
`docs/megaseed/name-drop.md` in the working set has the model). A fort's complete file is a
**Champion's keep**, and it is built of **stones**: one per domain — Fort Knight the agenda, Fork
Knife the meals, Fresh Keep the cleaning, Folk Knowledge friends and family, and four more. A stone
is chiselled from a **slab**, the human- and AI-readable `.xlsx` a person writes; a slab is quarried
from a **mountain**, whatever raw material they started with. The tool that cuts one slab is a
**chisel** — there are eight, one per slab — and the **mason** is what wields them and lays the
stones into a keep. Smaller files cut from the Champion's keep — a **Guest**, **Knight** or
**Royal keep** — are a single member's slice of it.

**Which slabs you must write** (extended 2026-09-01). `FortKnightSlab.xlsx` — the fourteen-day
agenda — is the **only required slab**; every keep has a Fort Knight stone. The other seven are
optional, and a fort writes only the ones it wants. **One caveat if you are using our exporter
rather than writing the JSON yourself:** it still requires all eight files to be present, empty
templates included, and exits without writing if one is missing. Making them genuinely optional is
planned, not done. Hand-making a keep has never had that restriction — this document is the whole
contract, and a keep is judged by what it contains, not by how many slabs produced it.

What this document specifies is the Champion's keep: the whole fourteen-day file. The vocabulary it
replaces, in anything you read from before 2026-08-30: *seed* meant the Champion's keep,
*companion* meant a stone, *kernel* meant a Guest/Knight/Royal keep, *silo* meant a Commander's
keep (2+ Champion keeps), and *workbook* meant the slab, back when there was one. The word itself is not
retired: the `.xlsx` format keeps it for its own container, and this repository's `examples/workbook/`
is named for the archived original.

## Two bars: readable and conforming

The format has two bars, and it matters which one you are aiming at.

- **Readable** — a page can draw something from it. This needs very little: `meta.format` is
  `"keep"`, `meta.version` is a number no higher than the page understands, and there is at least
  one day with a `dayKey`. A half-finished file is readable on purpose, so you can load a draft and
  see it.
- **Conforming** — the file is complete and well-formed: all fourteen days, every field the right
  shape. This is what `data/schema/keep.schema.json` certifies.

Every conforming keep is readable. A readable keep need not be conforming, and while you are
writing one by hand you will sit between the two. That is the intended experience, not a failure.

## The fourteen day keys

**A keep has exactly fourteen days, and their keys are fixed.** They are not your vocabulary to
choose — they are the skeleton of the format, in this order:

```
sun-a  mon-b  tue-a  wed-b  thu-a  fri-b  sat-a
sun-b  mon-a  tue-b  wed-a  thu-b  fri-a  sat-b
```

Each key appears exactly once, and `days` is in that order. The letter is which week of the
fortnight the weekday falls in; the alternation is what makes a fortnight a fortnight rather than
two copies of a week. This is a fourteen-day system — the fortnight is the product, so this is the
one part of the format that is never yours to change.

**The schema pins the count and the vocabulary, but not the order.** JSON Schema cannot say “each
of these exactly once, in this sequence”, so a file with `sun-a` fourteen times satisfies the
schema and still breaks this rule. The rule is the specification’s, and a test enforces it. If you
are generating keeps, do not rely on the schema to catch a shuffled or repeated day.

**The seven categories are the skeleton too.** `meals`, `cleaning`, `working`,
`spirituality-development`, `friends-family`, `health`, `operations` — in that order — are the only
values of `appointments[].category` and `season.focus[].key`, and a day’s `mainFocus` is one of
them or `flexible`, the pseudo-focus for a day left deliberately unassigned. A category is a stone,
and the stones were named when the format was; a fort chooses which stones it has, never what a
stone is (the working set’s `docs/megaseed/categories.md`, 2026-09-02). The same two bars apply
as for the day keys: **conforming** pins them, and the schema enumerates them; **readable**
tolerates them — a page that meets a key it does not know renders its label in the flexible colour
and does not refuse the file. Subjects, by contrast, are yours: the keep carries none, and a
fort’s slabs list whatever it likes under each category.

Everything else — block keys, season names, focus labels — is **your household’s vocabulary**.
One fort’s day runs `early`, `midday`, `late`, `too-dark`; another’s need not. The format does not
enumerate them and no reader should either.

## What travels, and what does not

**The keep is deliberately narrower than the planner data it comes from.** It carries what is eaten
and what is booked. It does not carry:

- **tasks and check-offs** — the household’s chores do not travel to the web,
- **the calendar** — a keep is keyed by day key and carries no dates at all,
- **cleaning areas**, and
- **row numbers and other workbook bookkeeping.**

This is a privacy property, not an oversight, and on the app’s side it is asserted by a test rather
than trusted to a comment. Keep it when you write one by hand: **put in what you want a website to
show, and leave out the rest.** The file lives on the device of whoever loads it, in that browser’s
storage, and is never uploaded — but the surest way for something not to travel is for it not to be
in the file.

Appointment titles do travel by default. If a booking is nobody’s business, leave it out.

## Dates: there are almost none, and that is the point

A keep is **pre-joined**. It is keyed by day key, so nothing reading it evaluates a calendar to
decide what today is; it looks the day up and draws it. That is why a keep never goes stale and why
the same file is correct in June and December.

The only dates in the format are `meta.exportedAt` and the year wheel’s `firstDate` / `lastDate`,
and they describe the file, not the fortnight.

## Season ordering: the wheel’s order is load-bearing

Season colours are drawn from a **positional palette** — the first slice in `year.slices` gets the
first colour, the second the second, and so on. Colours are never keyed to a season’s name or id.

Two consequences, both of which matter if you are writing or generating a keep:

1. **Keep `year.slices` in a stable order.** Re-ordering the array re-colours the wheel. Exporting
   the same year twice in different orders gives two differently-coloured wheels for one year.
2. **Your season names are free.** Because nothing is keyed to `ostara` or `winter`, a household
   with entirely different seasons gets a correctly-coloured, contrast-checked wheel with no change
   to any reader.

## The menu, and why it is grouped by slot

The `menu` is the fortnight's dishes: which one is cooked on which day, and which later day eats it
again as leftovers. About eight dishes cover fourteen days — most are eaten twice — and that is the
whole argument the menu is making, so the format keeps the pair rather than flattening it into
per-day text.

It is grouped by **slot** (`brunch`, `snack`, `dinner`), with a `label` beside it, because every day
has exactly one of each. Within a slot, `entries` are the dishes. The label is the slot's name for
display — today's writer emits `Brunch`, `Snack` and `Dinner`, and a household with its own words for
its meals may write its own. A reader prints the label it is given.

**It is additive, and it arrived after version 1 shipped.** A keep exported before 2026-08-29 has no
`menu` at all and is still perfectly conforming. That is the additive convention working, and the
reason the next section makes so much of absent-versus-empty.

**Days are already joined.** Each entry carries `cookDay` *and* `cookDayLabel`. A keep is pre-joined
so nothing reading it has to resolve anything — the label is the household's word for that day, and
a page prints it rather than working it out.

## Versioning, and why adding a field is not a version bump

`meta.version` is the format version. It is **1**.

**Adding a field never bumps it.** The app and the website ship on different cadences, and the
person holding the phone cannot redeploy the website — so a reader ignores fields it does not
recognise, and refuses a file only when the version is *higher* than it understands. A bump means a
breaking change and nothing else.

There are two constants, in two codebases, and they are two different ideas:

- `KEEP_FORMAT_VERSION`, in the app that writes keeps — the version it **writes**.
- `READABLE_VERSION`, in `src/lib/keep.js` — the highest version this website **reads**.

They are allowed to differ; the whole cadence argument is that they will, briefly, whenever one
half ships before the other. A file is refused only when the writer’s number exceeds the reader’s.

**Absent is not the same as empty**, and tooling that reports on a keep must say which it saw. The
menu is the worked example, and a real one: a keep exported before **2026-08-29** has no `menu`
section at all, which says the export predates menus; a keep with an empty menu says the household
has none. Those are different sentences, and a report that conflates them sends someone to
re-export a file that was never the problem.

`describeSection(keep, name)` in `src/lib/keep.js` is where that distinction lives — it answers
*absent*, *empty*, *present* or *wrong-shape*, with a sentence for each. Renderers still collapse
the two, deliberately: `validateKeep` ignores what it does not know and every panel degrades with
`?? []`, which is the right behaviour for something drawing a page. The requirement is on tools that
*report*.

**Room left deliberately:** a future per-member section — one person’s slice of a household’s
fortnight — is an additive section and would need no version bump, exactly as the menu did. Nothing
in version 1 forecloses it.

## The document

A complete keep, with one day shown in full. The other thirteen follow the same shape, in the order
given above.

```json
{
  "meta": {
    "format": "keep",
    "version": 1,
    "exportedAt": "2026-08-27T18:00:00+00:00"
  },
  "days": [
    {
      "dayKey": "sun-a",
      "label": "Sunday A",
      "week": 1,
      "mainFocus": "friends-family",
      "mainFocusLabel": "Friends & Family",
      "blocks": [
        {
          "key": "early",
          "label": "Early",
          "start": "08:00",
          "end": "12:00",
          "focus": "Slow Start",
          "meal": { "name": "Brunch", "dish": "Example eggs on toast" }
        },
        {
          "key": "too-dark",
          "label": "Too Dark",
          "start": "21:00",
          "end": "23:59",
          "focus": null,
          "meal": null
        }
      ],
      "meals": {
        "brunch": "Example eggs on toast",
        "snack": "Example oranges",
        "dinner": "Example garden soup"
      },
      "appointments": [
        {
          "id": "sun-a-example-swim",
          "title": "Example swimming lesson",
          "category": "health",
          "timing": {
            "estimatedStart": "14:00",
            "travelPrepComplete": "14:20",
            "timeStart": "14:30",
            "timeFinished": "15:30",
            "estimatedEnd": "15:50"
          }
        }
      ]
    }
  ],
  "menu": [
    {
      "slot": "brunch",
      "label": "Brunch",
      "entries": [
        {
          "mealKey": "Brunch1",
          "menu": "Example eggs on toast",
          "cookDay": "sun-a",
          "cookDayLabel": "Sunday A",
          "leftoversDay": "tue-a",
          "leftoversDayLabel": "Tuesday A",
          "cookExtra": false,
          "cookExtraNote": null
        }
      ]
    },
    {
      "slot": "dinner",
      "label": "Dinner",
      "entries": [
        {
          "mealKey": "Dinner1",
          "menu": "Example garden soup",
          "cookDay": "sun-a",
          "cookDayLabel": "Sunday A",
          "leftoversDay": "thu-a",
          "leftoversDayLabel": "Thursday A",
          "cookExtra": true,
          "cookExtraNote": "Example: the extra becomes Friday's pie filling"
        }
      ]
    }
  ],
  "season": {
    "key": "example-season",
    "name": "Example Season",
    "isCurrent": true,
    "gregorianRange": "August – October",
    "startDescription": "the second Sunday of August",
    "safeOutsidePercent": 62.5,
    "focus": [{ "key": "meals", "label": "Meals" }],
    "produce": [
      {
        "group": "vegetables",
        "label": "Vegetables",
        "items": [
          { "rank": "hero", "name": "Example squash" },
          { "rank": "secondary", "name": "Example kale" }
        ]
      }
    ],
    "mealIdeas": [{ "name": "Desserts", "text": "Example baked apples" }]
  },
  "year": {
    "status": "year",
    "year": "2026",
    "daysInYear": 365,
    "daysCovered": 365,
    "coversWholeYear": true,
    "firstDate": "2026-01-01",
    "lastDate": "2026-12-31",
    "slices": [
      {
        "key": "example-season",
        "name": "Example Season",
        "days": 84,
        "percent": 23,
        "startDegree": 0,
        "sweepDegree": 83,
        "isCurrent": true
      }
    ]
  }
}
```

### The fields

**`meta`** — required, with `format` and `version`.

- `format` — always the string `"keep"`. Before 2026-08-28 it was `"myfort"`; that name is dead and
  a file carrying it is refused.
- `version` — the integer `1`.
- `exportedAt` — when the file was written, or `null`. **Null is legitimate**, not a mistake: the
  writer takes this as an argument and defaults it to null, so a keep made without a clock has the
  key present and null rather than missing. Readers use it only to say how old the season snapshot
  is, and never to do date arithmetic.

**`days`** — required, exactly fourteen, keys as above. Only `dayKey` is required on a day;
everything else degrades to nothing if you leave it out, which is what makes a draft loadable.

- `label` — the day’s name as you write it. Rendered verbatim; nothing reformats it.
- `week` — `1` or `2`.
- `mainFocus` / `mainFocusLabel` — the day’s theme, as a key and as display text.
- `blocks[]` — the day’s parts, in the order they happen. `key` and `label` are yours.
  `start` and `end` are `"HH:MM"`, 24-hour, zero-padded — `"08:00"`, never `"8:00"`.
  `focus` is display text or `null`. **`meal` is an object `{ "name", "dish" }` or `null`** — a
  common mistake is to write the dish as a bare string here.
- `meals` — the day’s three dishes as plain strings, or `null`.
- `appointments[]` — the recurring **ideal** week: what is booked in principle. Not a device
  calendar feed. `timing`’s five fields are all `"HH:MM"` and run in the order given: the
  estimate, travel and preparation done, the real start, the real finish, and the estimated end.

**`menu`** — optional, and absent on any keep exported before 2026-08-29. A list of slots, each
`{slot, label, entries}`.

- `slot` — `brunch`, `snack` or `dinner`. `label` is its display name, rendered verbatim.
- `entries[].mealKey` — the household's own id for a dish within its slot. Not a fixed vocabulary.
- `entries[].menu` — the dish, in the household's words. The field really is called `menu`.
- `entries[].cookDay` / `cookDayLabel` — the day it is cooked, as a canonical day key **and** as the
  household's label. Both, because the page never resolves anything.
- `entries[].leftoversDay` / `leftoversDayLabel` — the day it is eaten again, or `null` for a dish
  eaten once.
- `entries[].cookExtra` — `true` when more is cooked than the servings need, because the surplus is
  an ingredient in a later dish. `cookExtraNote` says why, in the household's words, or is `null`.
  It is the only prose the menu sends to a page — write it knowing that.

**`season`** — the season current when the file was written, or `null`. `key` and `name` are yours.
`safeOutsidePercent` is a number, not necessarily whole. `focus`, `produce` and `mealIdeas` are the
season’s content and may be omitted entirely.

**`year`** — the year wheel, or `null`.

- `year` is a **string** — `"2026"`, not `2026`.
- `slices[]` draw the wheel. `percent`, `startDegree` and `sweepDegree` are numbers and need not be
  whole — they come from division, and a year whose seasons do not divide evenly will have
  fractions. `startDegree` and `sweepDegree` are degrees clockwise from the top.
- The order of `slices` sets the colours. See *Season ordering*, above.

## Checking your file

Validate against `data/schema/keep.schema.json` with any JSON Schema tool (it is draft 2020-12 and
uses no `$ref`), or simply load it at `/fortknight/keep/` and see what draws. Loading is
non-destructive: a file the page refuses is reported, and nothing already stored is lost.

**The schema is open on purpose.** No object in it forbids extra properties, because the format has
to tolerate a field one half of the system knows and the other does not. That means the schema will
not tell you about a typo in a field name — it will simply ignore `mealz` as a field it does not
know. Read the field list above when something you wrote does not appear on screen.
