# The keep format: a fortnight you can write by hand

A **keep** is a small JSON file describing one fourteen-day fortnight — what is eaten, what is
booked, and what each block of each day is for. The planner app writes one; `/fortknight/keep/`
draws it. This document is the format's specification, written for a person making a keep by hand
in a text editor, and it is canonical: the machine schema beside it is
`data/schema/keep.schema.json`, and the reader that decides whether a page can draw your file is
`src/lib/keep.js`.

You do not need the app. A keep you write yourself is a first-class keep, and it is checked against
the same schema as one the app exports.

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

Everything else — block keys, season names, focus labels, categories — is **your household’s
vocabulary**. One fort’s day runs `early`, `midday`, `late`, `too-dark`; another’s need not. The
format does not enumerate them and no reader should either.

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

**Absent is not the same as empty**, and tooling that reports on a keep must say which it saw. A
keep with no `menu` section at all was written before menus existed; a keep with an empty one says
the household has no menu. Those are different sentences, and a report that conflates them sends
someone looking for a bug that is not there. *No reader implements this today* — `validateKeep`
silently ignores what it does not know, which is the right behaviour for a renderer. The
requirement is on validators and reports, and it is written here because the tools that will need
it are not built yet.

**Room left deliberately:** a future per-member section — one person’s slice of a household’s
fortnight — is an additive section and would need no version bump. Nothing in version 1 forecloses
it.

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
