# The Fortress model — forts, roles, boards (design; not built)

How FortKnight is meant to grow from one person on one device into a **household** that can see who
is doing what, and a **community of households** that can share a calendar and a board.

> **Status: none of this exists.** No login, no server, no roles, no boards. This is a design record
> so the shape is written down before it is built, and so a decision made here can be argued with
> later. Nothing in `data/`, `src/` or `scripts/` implements any of it today.
>
> Not published into anyone's assistant workspace — it is not in `WORKSPACE_STATIC_DOCUMENTS`
> (`src/lib/shared/workspace-docs.js`) and must not be added to it.

The vocabulary here extends the one in `docs/domain.md` and the contract in `docs/weights.md`; the
positioning it serves is in `docs/thesis.md`. The ground truth for this document is the owner's own
description of the model, quoted in the appendix — the prose above it is written *from* that text.

## Fort and Fortress

- A **fort** is a household: the people who share a home, and increasingly a fortnight.
- A **fortress** is a community of forts.

Both are units of *measurement* before they are units of social software. A fort weighs and measures
who is doing what inside the household; a fortress does the same across the households in it.

## The four roles

| role | who they are | what the role is for |
|---|---|---|
| **Knight** | productive members — school-age children and working adults | the people whose time the fortnight actually allocates |
| **Royal** | dependants — small children, the elderly, the infirm | people the fort's work is done *for*, and whose care is itself allocated work |
| **Champion** | the fort's manager | runs one household: sees its measurements, curates its board |
| **Commander** | the fortress's manager, and the Champions' manager | runs the community: the only role that can post publicly |

Two things follow from the Knight/Royal split that are worth stating plainly. Care for a Royal is
**work someone else is doing** — it belongs in the fort's measurements as time spent, not as an
absence of activity. And a Royal is not a lesser user: the role describes who the fortnight is
carrying, not who matters.

## What a fort measures

Today `analyze_allocations.py` and `weights.*.json` answer *how much of the fortnight goes to each of
the seven categories* for one person. A fort asks the same question with a second axis: **who**.

The missing primitive is therefore **per-person attribution of category minutes** — the same
`{category: minutes}` shape the whole project already speaks, keyed by member. Everything a fort
would want to show (who is carrying the cleaning, whether one Knight's working share has crowded out
their health, what a Royal's care actually costs the household in hours) is a view over that one
addition. A fortress view is the same aggregate a level up, across forts.

Designing it this way is the point: forts and fortresses should be *readers* of the existing weights
contract, not a parallel data model. If a fort needs a number the weights file cannot express, that
is a signal to extend `docs/weights.md`, not to start a second system.

## Boards and calendars

Each fort has boards, the fortress has boards, and there are shared calendars alongside them. The
posting rules are deliberately narrow — this is a chain of curation, not a feed:

| who | may post to |
|---|---|
| **Royals, Knights and Champions** | their fort's **Champion's board** |
| **Champion** | reposts from the Champion's board onto the **Fort board**, or to the **Round Table board** |
| **Commander** | the **public-facing board**, their **own** board, the **Round Table**, and Champions' boards and calendars |

So nothing reaches a wider audience without a person choosing to carry it there: a Knight posts to
their Champion, the Champion decides whether the fort or the Round Table sees it, and only the
Commander can post where the public can read.

**The Fortress public board is the only real social-media surface in the whole project.** Everything
else is a household talking to itself or a small number of households coordinating. That boundary is
worth defending on purpose, because it is the only place where content leaves a fort — and it is the
one part of this project that would need moderation, reporting, and a policy for what happens when
someone posts something they should not.

## Accounts, and the tension this creates

FortKnight will eventually have a real login. That is the first time this project would hold anyone's
data on a server, and it contradicts a claim the thesis currently makes without qualification: no
backend, no accounts, nothing leaves the device (`docs/thesis.md`, FortKnight).

The honest position is that this is **unresolved**, and it should stay written down as unresolved
until someone decides. The options, so the decision is made with them in view:

1. **Login as identity only.** The server knows who you are and which fort you belong to; profiles,
   weights and schedules stay on the device, and the fort's measurements are computed locally from
   what members choose to publish to it. Smallest server, weakest features.
2. **Login plus a shared fort record.** The server holds the fort: membership, boards, the shared
   calendar, and whatever measurements members opt into sharing. Personal answers and weights stay
   on device. The likely middle.
3. **Login plus sync.** The server holds profiles so a person can move between devices. Most useful,
   most data held, and the furthest from the current thesis — it would need the thesis rewritten
   rather than footnoted.

Whichever is chosen, two properties should survive from the current design: **the person's answers
stay the source of their weights** (a fort must not be able to overwrite a member's questionnaire),
and **nothing is published from a fort without a person choosing to publish it**.

## Where this meets what exists today

- `data/questionnaire.json`, Startup Q1 is already `groupSize` — *"How many people are in your
  group?"* — carrying the note *"Groups stay on one device for now — one profile per person."* That
  note is precisely the seam a fort replaces.
- `settings.weightsProfiles` (`docs/app.md`) already holds several named profiles per device with
  one active, switched from the nav. One profile per person on one device is a fort with no server
  and no roles — the degenerate case that already works, and the thing a real fort must stay
  compatible with.
- The two faces already share one profile, so a fort's members each having a FortKnight and a
  Fork Knife view falls out of the existing structure rather than needing a third face.

## Open questions

- How do roles map onto profiles? Is a Champion a person with an extra permission, or a profile-level
  role? Can one person be a Knight in one fort and a Champion of another?
- Does a Royal have a device at all? If not, who answers their questionnaire, and whose weights are
  those?
- What exactly does a member publish to their fort — a whole weights file, or a reduced
  `{category: minutes}` summary? (The latter is the smaller, safer default.)
- Moderation of the public board: who acts, on what timescale, under what written policy. This needs
  answering *before* the board ships, not after.
- Does a fortress calendar write into a member's fortnight, or only sit beside it? A shared calendar
  that can allocate someone's time is a very different product from one that can only inform.
- What happens to a fort when its Champion leaves?

## Appendix — the map, as stated

The source for this document, lightly tidied (shorthand and typos cleaned; wording and meaning
otherwise untouched). This is the text the sections above are written from and should be checked
against:

> FortKnight will eventually have a real login. Each fort will be able to weigh and measure who is
> doing what in a household (fort) **and** in a community of households (fortress). It will have 4
> types of users: knights (productive members — school-age kids and working adults), royals
> (dependants — small children, elderly, infirm, etc.), Champions (fort managers), and Commander
> (fortress and champion manager).
>
> There will be different bulletin boards and shared calendars. Royals, knights and champions can
> post to the Champion of their fort's board. The champion can then repost them on the Fort's board
> or to the round-table board. The Commander can post to the public facing, their own, the round
> table, and Champions' boards and calendars. The Fortress public board is the only real social
> media part.
>
> I am hoping to find a way to get the app to download files to their phones like FortKnight's
> current AI flow. I know Claude already has Cowork, so I thought the flagship might have to be
> Cowork-centred.

The Cowork question is a delivery question shared with Fork Knife and is tracked in
`docs/fork-knife-chain.md`, where the same flow already exists to be improved.
