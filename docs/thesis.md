# Thesis

What the studio is, how it speaks, and what each thing here argues — the games and the engine,
FortKnight, Fork Knife, and the company over all three, each with what it refuses to do.

This is a positioning document, not a contract. Nothing builds from it and no schema references it —
but the site copy does, and so should anyone deciding whether a proposed feature belongs. It is also
the **source of truth for the wording of the art policy** (below): if that policy is refined, it is
refined here first and mirrored outward.

> Not published into anyone's assistant workspace — it is not in `WORKSPACE_STATIC_DOCUMENTS`
> (`src/lib/shared/workspace-docs.js`) and must not be added to it.

## How the studio presents itself

**Be Insiculous is an Artificial Intelligence Development Studio.** That is the banner on `/`, spelled
out, and it is the frame the games and the planner both sit inside: the engine is co-developed with
coding agents and serves as a proving ground for them, and FortKnight and Fork Knife are tools an
agent drives. The tagline in the footer of every page says the whole of it in eleven words —
**"Built with AI, for AI, and the humans in the loop"** — and every clause of that is literal, not
rhetorical:

- **with AI** — the engine and this site are built with coding agents, under guardrails and review.
- **for AI** — the planner's whole assistant workspace is a document set whose only reader is an AI,
  and the engine is deliberately shaped so an agent can work in it (per-crate instruction files, live
  tech-debt ledgers, everything runnable headless from the CLI).
- **and the humans in the loop** — no leaderboard, no pass-rate, no credentials held on anyone's
  behalf, and a person adjudicating every finding.

### Two registers, and which page gets which

The studio layer is, in practice, the resume for everyone here: it exists partly to help the studio
become more professional *literally*, by looking legitimate to people who might hire or buy. So it
**dresses for the job** — plain, confident, professional. No self-deprecation, no in-jokes, no
manifesto voice.

The **four projects each keep their own bubble of quirk**, and the quirk should be specific to each
rather than one house style: FortKnight (`/fortknight/`), Fork Knife (its pages are folded into
FortKnight's for now — see its section below), the games
(`/games/`) and the devlog (`/devlog/`). Everything else — `/`, `/engine/`, `/404`, `/accessibility/`,
`/profile/`, and the shared header, footer and meta copy — is the studio speaking and takes the
professional register. When it is unclear which layer a page belongs to, ask that question first.

---

## The games and the engine

**Make the machine as well as the game, keep both small enough to hold in your head, and put a
second person on the couch.** The games are the studio's proving ground as much as its output: an
engine built to be worked in by agents is the clearest thing an AI development studio can show for
itself.

### The claims

- **Owning the engine is the point, not overhead.** Insiculous 2D has a hand-written ECS —
  per-type storage, generational entity ids, events, resources, systems — chosen for debuggability
  and testability over raw throughput. That is only a defensible trade if you are the one who has to
  debug it. A general-purpose engine makes the games it expects; this one makes the games we expect.
- **The classics are a control, not a shortcut.** The arcade remakes are a run at the 20 Games
  Challenge, and everyone already knows how Pong behaves — which is exactly what makes it a good
  instrument. The interesting variable is what happens when a known-good system is perturbed, and
  the *chaos modes* are that perturbation, escalating on purpose.
- **Every game is for two people in one room.** Versus rules for head-on collisions, two-cannon
  co-op, co-op variants, paddle-edge aiming against someone sitting next to you. Not matchmaking,
  not lobbies. That is a claim about what games are *for*, and it is why local play is never the
  fallback mode.
- **Testability is a design constraint, not hygiene.** The rule from day one is that everything must
  be exercisable from the CLI, headless, without a GPU. The payoff was unplanned and turned out to
  be the studio's edge: a codebase that can be verified without a human watching is a codebase an
  agent can safely work in.
- **The tools belong where the games run.** The games play in a browser tab, and the editor is
  headed to the same place: open it, build a scene, press play, and take the project away with
  you — building with the engine, not just playing what it built, with no toolchain installed.
  An engine whose front door is a URL is the version of "small enough to hold in your head" that
  a stranger can actually try.
- **The bar is survival, not a score.** No leaderboard, no pass-rate. Work is judged on whether it
  survives review, the test suite and actual play, adjudicated by the person who has to live with
  the codebase afterwards. A finding must name a concrete failure scenario; "this might have issues"
  is not a finding.

*(Engine specifics — crate layout, rendering, the test suite — live in the Insiculous 2D repository,
not here. This document keeps its engine claims directional on purpose: a line count or a test count
written down in this repo would rot without anything noticing.)*

### Two tracks, and the art policy

The studio ships along two tracks, and they are not the same product:

| | free games | games we sell |
|---|---|---|
| where | listed on this site, `/games/` | their own repository each; Steam and/or Android and iOS |
| what they are for | showcases for the engine, the 20 Games Challenge run | the commercial line |
| art | **AI art** | **no AI art** — made by our own artists |

**The policy, in the words the site uses:** *the games listed here are free and use AI art; the
games we sell carry none — those are made by our artists, and they ship on Steam and the app stores
rather than here.*

The commitment is worth making before there is anything to buy, because it is a promise to buyers
and it constrains what we build. It also has a maintenance condition: the blanket sentence on
`/games/` is true only while **every** game listed there uses AI art. The first game on this site
that does not makes it false, and per-game labelling has to ship in the same change.

### What it refuses

Engines rented from someone else. A metric standing in for judgment. Games that assume you are
alone. And selling anyone a game whose art a machine made.

---

## FortKnight

**A week is the wrong unit of life, and a calendar is the wrong shape for a plan. Decide the
proportions; let the schedule be derived.**

### The claims

- **Fourteen days, not seven.** The variant letter alternates every day, so week two is the mirror
  of week one (`docs/domain.md`). That is the smallest cycle that can hold both "every day" and
  "every other day" things without one of them lying — a weekly planner forces the alternating ones
  into a fiction.
- **Allocation precedes schedule.** The north star is `weights.*.json` (`docs/weights.md`): what
  fraction of the fortnight each of the seven categories should get. The block focus grid, the day
  pages and the proposed activities are all downstream of that number. A calendar can answer "what
  is at 3pm Thursday"; it cannot answer "am I spending my life the way I said I would."
- **The questionnaire *is* the settings.** There is no separate configuration screen, and weights
  are always re-derived from answers on device. So a plan can always be traced back to something the
  person actually said. A plan you cannot derive from your own answers is someone else's plan.
- **Open time is declared, not left over.** `flexibleShare` is explicitly the part of the waking
  window the seven categories did not claim — rest days, seasonal work, the not-yet-scheduled.
  Naming it is what stops it from being quietly eaten.
- **The year moves, so the rules move with it.** Season starts are *computed* — equinox, nth
  weekday, the Nth new moon, Easter — never typed in; only `manual` sections carry literal dates
  (`fk_core/dates.py`). A plan that cannot be recomputed for next year has an expiry date.
- **Your schedule is the most sensitive file you own.** No backend, no accounts, no server holding
  it. This repository is public and contains nobody's schedule: `data/` is person-neutral and the
  sample workbook lives behind an overlay flag.

### Where it is going

A fort weighs and measures **who is doing what** in a household, and a fortress does the same across
a community of households — the multi-person extension of exactly this vocabulary, where the missing
primitive is per-person attribution of the same category minutes. That direction brings a real login
with it, which is the first time this project would hold anyone's data on a server, and it is in open
tension with the claim directly above. The model, the five roles, the boards and that unresolved
tension are recorded in `docs/fortress.md`. None of it is built.

### What it refuses

Appointment-shaped thinking. A plan that cannot say why. Any architecture where a schedule leaves
the device without the person choosing to send it.

---

## Fork Knife

**Feeding yourself is a scheduling problem wearing a recipe problem's clothes. Plan the cooking, not
the eating.**

### The claims

- **Nobody's actual problem is inspiration.** Recipe apps solve discovery. The question at six in
  the evening is *what is already made, and what does tonight cost me*. That is the one Fork Knife
  answers.
- **Leftovers are the load-bearing structure.** About eight dishes cover fourteen days because six
  are eaten twice, and the spacing rules encode why it works: the second serving is never the next
  day and at most three days later, wrapping past the end of the fortnight (`docs/meal-plan.md`).
  That constraint *is* the design — it is what makes a fortnight of meals cost eight cooking
  sessions instead of fourteen.
- **Leftovers cross meals, one direction only.** Sunday's dinner is Tuesday's breakfast; a morning
  meal's leftovers never move to a later one. Food does not respect the slots we file it under.
- **A menu is a bill of work.** Choosing a dish is choosing prep minutes and cooking minutes on
  specific days. So the menu does not stay in the food app: its tasks land in the same profile
  FortKnight plans from, where `meals` is one of the seven categories and competes for the fortnight
  like everything else.
- **That is why it is not a product of its own.** A standalone meal-planning app would have to lie
  about what dinner costs the rest of your week. Two faces was the shape while both were being
  built; with the creation chain on the back burner, the `/forkknife/` routes came down
  (2026-08-28), and this section's argument moves with them: the by-dish and by-day menu views land
  where the keep already lives, on FortKnight's keep-fed pages, once the keep carries menu
  rows. Leftovers stay load-bearing there — eight dishes covering fourteen days is exactly what a
  real household's keep shows.

### Simple, and therefore difficult

The concept is small enough to say in a sentence, which is what makes the execution hard: the target
is a chain that starts from questions about where you live, what you eat, and how much time you
actually have, hands your own assistant enough context to **interview you back**, and ends with a
menu, recipe options, a prep schedule, a cooking schedule, a shopping schedule and a shopping list —
all of it landing in FortKnight's agenda. The stage-by-stage design, and what exists versus what is
missing at each stage, is in `docs/fork-knife-chain.md`.

### What it refuses

Being a recipe box. Pretending cooking is free. Living in a database that does not know what else
you have to do that day.

---

## Be Insiculous Studios

**AI is a collaborator held to a contract, never a service you hand your life to.**

### The claims

- **The same stance, pointed two ways.** On the game side, agents write engine code under hard
  guardrails — never claim a test passed without running it, never weaken a test to get green, stop
  after two failed attempts — with **adversarial cross-model review**: one model authors, a
  different vendor's model attacks, and every numbered finding gets an explicit accept or rebut
  (`.claude/skills/adversarial-review/SKILL.md`). On the planner side the same suspicion points
  outward: the app calls no LLM and holds no credentials. It hands *you* a file set for your own
  assistant and takes back only documents that validate against a published schema.
- **Bring your own model; keep your own data; verify the output.** Those three are one position, not
  three features. Any design that makes us the middleman between a person and a model — holding the
  key, holding the data, or holding the only model that works — fails it.
- **Verification is adversarial by default.** Plans and large diffs are attacked before they land,
  and findings must name a failure scenario. This is the same standard applied to our own work as to
  an agent's, which is the only version of it that means anything.
- **Small systems you own, tested until a machine can work in them.** The engine and the planner are
  the same practice at different scales: hand-built, legible, exercisable from a command line, and
  small enough that one person can still hold the whole thing.
- **The human adjudicates.** Every loop here ends at a person deciding — which finding was real,
  which plan survives, whether the game is fun, whether the fortnight is the life they meant to
  live. Nothing in the stack is allowed to quietly become the decider.

### What it refuses

Being a middleman between you and a model. Holding your credentials. Holding your schedule. Shipping
work no human judged. And any metric that would let us stop looking at the thing itself.
