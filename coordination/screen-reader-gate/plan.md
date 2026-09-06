# Deploy `dev` to `main` — after the manual checklist becomes gates

**v5 — revised 2026-09-06 after review round 4** (kimi five, gemini seven, all twelve accepted;
`rebuttal-4.md`: specification precision — the parser's quoted keys and continuation lines, the
stub check on standalone files, the keep view's test scaffolding, sentinel scoping and shape, the
timeout set from a measurement, and one false citation of mine corrected).
**v4 — revised 2026-09-06 after review round 3** (kimi six, gemini six, all twelve accepted;
`rebuttal-3.md`: the re-leveling is made style-explicit, `/games/` joins the heading fixes, the
grammar is one shape, the sentinels move out of the pure function, the fixtures are captured
after the fixes).
**v3 — revised 2026-09-06 after review round 2** (kimi six, gemini six; `rebuttal-2.md` — the two
overflow claims were measured false on all 41 routes, the two heading claims true).
**v2 — revised 2026-09-06 after review round 1** (kimi six findings, gemini six; adjudicated with
M, `review/screen-reader-gate/rebuttal-1.md`, every claim measured on the built site first).
Decisions recorded in place; the rebuttal explains them.

Run through the **handoff loop** (`.claude/skills/handoff-loop/SKILL.md`) for the one code batch:
this session plans and commits, kimi and gemini review the plan, gemini executes the batch from a
handoff prompt, kimi and the planner review it before it lands. The deploy itself is the planner's,
with M's go at the merge.

## Context

`insiculous_web`'s `dev` is 20 commits ahead of `main` (Focus in the Bar's sprint and the
game-achievements effort; 41 files, +2415/−206). Production deploys only by a `dev → main` pull
request (`.github/workflows/deploy.yml`: push to `main` → the production Worker; push to `dev` →
staging). Staging already serves this exact tree: the `dev` deploy run of 2026-09-06 04:16 UTC
succeeded and `https://dev.beinsiculous.com/achievements/` carries the new board.

The PR template (`.github/pull_request_template.md`) has four checks beyond `npm run verify` for
layout or interactive changes: a keyboard walkthrough, a screen-reader pass ("landmarks, headings,
control names all announced"), 200% zoom at 320–390px, and alt/labels on new images and fields.
Both efforts on `dev` changed layouts and one added an interaction (the Peripheral disclosure). No
screen reader runs on Danny (Linux; VoiceOver and NVDA are macOS and Windows), so that box cannot
be ticked by hand here. **M's ruling (2026-09-06): fix it so the box is ticked honestly** — make
the pass a gate that measures what a screen reader announces, from the accessibility tree the
browser builds, and let the template say so. The 200% zoom line is the same kind of thing and is
one viewport entry away from being mechanical, so it comes along; the keyboard walkthrough stays
manual (focus visibility is a thing you see) — **a human's, never a scratch script's** (M,
2026-09-06, kimi F2): M walks the changed pages on staging and ticks the box, or it stays
unticked and the PR says so. M has already looked at 200% text size on a 320×480 viewport and
found it good; that is the human look beside the reflow gate below.

Not in scope: the engine and game repositories — nothing deploys from them, and their `main`
lines are Jesse's cleanup reconciliation, not this. A keyboard-order gate. Real screen-reader
runs (still asked for when a new interaction lands; the template says so).

## Where things live

- **This plan, tracked:** `insiculous_web/coordination/screen-reader-gate/plan.md` (the code is
  the site's; the same layout Focus in the Bar used). **Scoreboard:**
  `insiculous_web/coordination/screen-reader-gate/reviewer-comparison.md`.
- **Transients:** `insiculous_web/review/screen-reader-gate/` — `plan.md`, `review-N*.md`,
  `rebuttal-N.md`, `handoff-1.md`, `draft-1*.diff`.
- **Branch:** `m` in `insiculous_web`, merged into `dev` after the commit (the `.idea` stash dance
  around the merge, verified after the pop); `main` by the PR in § *The deploy*.
- **Fetched first:** `git -C insiculous_web fetch origin` before every branch comparison
  (the effort before this one learned that the hard way).

## Ground rules for the batch

As the game-achievements plan's, for `insiculous_web`: branch `m`; touch only the named files
plus what a build forces; stage everything, commit nothing; INCOMPLETE rather than silence; no
new dependencies (Playwright and the dist server are already there — no YAML library: the tree's
text form is parsed by a small documented reader); `src/lib` untyped and node-tested, pages
type-checked; curly apostrophes and inline tags on their word's line; comments carry reasons;
human-readable names, no abbreviations, closure parameters included; never stage, unstage or
delete M's `.idea` files; `git -C <abs path>` for every git call. Gate: `npm run verify`, which
after this batch includes the new gate and the new pass. Report shape as before, ending with the
porcelain over the touched paths and the cached stat tail.

## Batch 1 — the announce gate, the zoom pass, and the template that names them

**Files:** new `scripts/announce-check.mjs`; new `scripts/lib/announce-tree.mjs`; new
`scripts/lib/a11y-scenarios.mjs` (extracted from `scripts/a11y-check.mjs`, which then imports it);
new fixtures `tests/fixtures/aria/achievements.snapshot.yaml` and
`tests/fixtures/aria/fixknitt-peripheral-open.snapshot.yaml` (real captures, see below);
`scripts/screenshot-pages.mjs`; `package.json`;
`.github/workflows/deploy.yml`; `.github/pull_request_template.md`; `README.md` (§ Accessibility,
the gate list at `:173-183` and the command table at `:48`); `CLAUDE.md` (`:71` the verify chain,
`:120-127` the three gates and the manual pass, the *Where to look* row at `:270`);
`src/lib/achievements.js` and `src/pages/achievements.astro` for the heading skip described
below; `src/lib/keep-view.js`, `src/components/KeepStyles.astro`, `src/pages/fortknight/keep.astro` and
`src/pages/fortknight/days/[dayKey].astro` for the second; `src/pages/fortknight/index.astro`
for the third; `src/components/GameCard.astro` and `src/styles/global.css` for the fourth;
`tests/test_achievements.py` and `tests/test_keep.py` for those; new
`tests/test_announce_check.py`. The deploy workflow's Layout-gate step comment
(`deploy.yml:80-82`) is in scope with the step it describes.

**Target shape — the scenarios module.** `scripts/lib/a11y-scenarios.mjs` exports what
`a11y-check.mjs` today keeps inline: the seeds (`SEEDED_PROFILE`, the sample and other-household
keeps, `pongAchievements`, `siteAchievements`, `everyStoneKeepSeed`), the four-store init script
the main sweep plants (`a11y-check.mjs:222`), `SEED_FED_ROUTES` (`:251`, the keep-fed routes the
other-household pass re-audits) and `OPENED_ELEMENT_ROUTES` (`:73`, the opened-disclosure
scenarios — `{ route, seed, label, viewport?, waitFor, open }`), so both gates audit the same
populated states and the same opened disclosures, and the list is the one place that says
which states a gate must see. The other-household pass itself stays in `a11y-check.mjs`: it
exists for colour contrast, which the announce gate does not hear. `a11y-check.mjs` loses the
definitions and gains the import; its behaviour is unchanged, and the report proves it with
its **analysed-page count** before and after the extraction (kimi F3), not only its exit
status.

**Target shape — the gate.** `scripts/announce-check.mjs` (`npm run announce`; header says what
it measures and why it is the honest form of the template's screen-reader line, and what it
cannot hear — pronunciation, verbosity, live-region timing — which is why a new interaction
still gets a real listen):
- serves `dist/` with `serveDist`, walks `distRoutes` **minus the redirect stubs** — a route whose
  own file — `dist/<route>/index.html` for a directory route, `dist/<route>` for a route ending in
  `.html` such as `/404.html` (kimi round 4 F5, gemini F3) — **read from disk before any
  navigation** (kimi round 3 F3: the zero-second refresh has fired by the time the live DOM could
  be read) carries
  `<meta http-equiv="refresh"` is a stub with no layout and is skipped, the skip reported with
  its route (detection is by the file, never a list; today's four are
  `/fortknight/allocations/`, `/fortknight/fortnight/`, `/fortknight/myfort/`,
  `/fortknight/settings/` — gemini F4, F5) — plus every `OPENED_ELEMENT_ROUTES` entry, each in a
  fresh context seeded with **its own `seed` records only**, exactly as `a11y-check.mjs:276-281`
  does (gemini F6: two scenarios depend on an empty store) — navigate, run the entry's `open`,
  wait for its `waitFor` selector exactly as `a11y-check.mjs:284-289` does (gemini round 3 F4),
  **then** take `await page.locator("body").ariaSnapshot()`. The main sweep plants the
  scenarios module's one init script.
- **The format, from real captures** (`review/screen-reader-gate/probe.mjs` and `probe2.mjs`
  captured `/achievements/`, a devlog post, the seeded keep, the open dialog, the seeded
  overview and a day page): one node per line, nested by two-space indent, and **one shape**
  (gemini round 3 F2 — an enumeration of forms let a heading line fall through): a name part —
  `role`, `role "name"`, or `'role "name"'` (a name that needed YAML quoting comes out as a
  single-quoted key) — then zero or more `[attr]` / `[attr=value]`, then optionally `:` (a
  container with children) or `: text` (a node whose content is text, `- group: Peripheral`).
  So `- banner:`, `- heading "Keep" [level=1]`, `- group`, `- link "Games":` and `- 'link "…"':`
  are all the one shape; a single-quoted key encloses its attributes too
  (`- 'link "x" [expanded]':`), so the parser strips the enclosing quotes first and then reads
  the shape (gemini round 4 F1). Under a link, `- /url: <href>` lines; `- text: …` lines for static text;
  possibly continuation lines that do not start with `- ` (none appeared, but wrapped text can
  produce them). Names may carry `\"` and `\\` escapes, which the parser unescapes. `ariaSnapshot` exists since Playwright 1.49; 1.62.1 is
  installed. Two captures are committed as fixtures — `/achievements/` plain, and
  `/fortknight/fixknitt/` with the Peripheral strip open (the `[expanded]` case) — **captured
  from `dist/` after the five heading fixes below have landed** (kimi round 3 F2: a pre-fix
  capture is the skip the gate exists to catch, so it cannot also be the "clean" fixture), and
  the parser test's heading and level expectations are read off those captures at that point,
  never a hand-written idealisation.
- `scripts/lib/announce-tree.mjs` (pure, node-tested): `parseAriaSnapshot(text)` → a list of
  `{ depth, role, name, attributes }` nodes: `/url` and `text` lines are ignored by name, a
  continuation line takes the previous line's disposition — ignored after an ignored line,
  folded into the name only when the previous line opened a node (gemini round 4 F2) — a bare
  role parses to an empty
  name, attributes are read generically (`level` is the one the rules use), and a line that fits
  none of these forms is an error naming the line and saying both things it can mean — that
  Playwright changed its format, or that a page's text has a shape the captures never showed
  (kimi F4). `announceFindings(nodes)` →
  the failures for one page:
  1. **landmarks:** exactly one `main`; at least one `navigation`; a `banner` and a
     `contentinfo`. (The layouts render `<header>`, `<nav>`, `<main>`, `<footer>` — the gate
     proves it on every route, `404.html` included.)
  2. **headings:** exactly one level-1 heading, **it comes first**, and going down the page no
     level is skipped (a level-3 heading whose nearest preceding heading is level 1 is a skip).
     This is what heading navigation in a screen reader walks.
  3. **control names:** every `link`, `button`, `textbox`, `combobox`, `checkbox`, `radio`,
     `slider`, `switch`, `tab`, `menuitem` node has a non-empty name (an unnamed control appears
     in the tree as its bare role).
  4. **named regions and dialogs:** every `region` and every `dialog` node has a name. `group`
     nodes are exempt on purpose: the header's `<details>` elements are groups with no name by
     browser design (`- group` on every captured page), and the board's scroll boxes are
     `role="group"` with `aria-labelledby`, which the captures show named — a rule on groups
     would fail every page for the browser's convention, not for a defect. The open naming
     dialog keeps every landmark in the tree (measured: banner, two navigations, main,
     contentinfo and the dialog all present), so the dialog scenarios need no special scoping
     (gemini F1, rebutted).
  5. **seeded sentinels** (kimi F3, extended by kimi round 3 F4, homed by gemini round 3 F3):
     rules 1–4 are universal and live in `announceFindings(nodes)`; the sentinels are a
     `SENTINELS` map in `announce-check.mjs` — route → the heading texts (`string[]`) the seeded
     sweep must find (gemini round 4 F5) — checked **on the main sweep only, never on a
     scenario pass** (kimi round 4 F4: the `/profile/` dialog scenario is seeded with settings
     alone by design), through a pure, tested `missingSentinels(route, nodes, sentinels)` in
     `announce-tree.mjs` that returns the strings not found, one entry per seeded surface: `/profile/` the pong group heading (the games
     save) and the two site group headings (the site store); `/games/` the pong group heading;
     `/fortknight/keep/` a day heading and `/fortknight/days/sun-a/` its h1 with the keep's day
     label (the keep); seeded `/fortknight/` "Your fortnight". A seed dropped in the extraction,
     or a boot that draws nothing, is a named failure, not a quietly emptier tree.
  The gate's header also names what the landmark rule leans on for face pages on desktop: the
  `<nav>` landmarks live inside a closed `<details class="menu">` made visible by
  `.site-nav .menu::details-content { content-visibility: visible }` (`faces.css:118`,
  Chromium's pseudo-element), so a red on every face page after a Playwright bump reads as that
  (kimi F5).
  The rules cover every page `dist/` holds, devlog posts included: a post that opens with `###`
  under the page's `h1` fails the deploy gate by design (kimi F4) — the script's header and
  README say so, so an author reads the first such failure as the rule.
- prints one line per failing route and scenario with the finding and the offending node's
  text, exits 1 on any; `ANNOUNCE_ONLY=<substring>` filters routes for iterating, as
  `A11Y_ONLY` does.

**The five findings the gate will make, fixed in the same batch — style-explicitly** (kimi round
3 F1: the site's heading styles key on tag names, so a re-leveled heading changes size or gains
the studio's `// ` decoration unless the selector says otherwise; every fix below names its
style rule, and M's visual look on staging is sequenced after the batch, not before).
- `/achievements/` renders `h1` then the board's group headings as `h3` — a skipped level
  (`/games/` and `/profile/` have an `h2` above theirs, so they do not). `renderAchievementsBoard`
  gains `headingLevel = 3` in its options; `achievements.astro` passes `2`; the renderer's header
  comment says why the level is the page's to choose. As `h2`s the group headings take the
  studio's section style (`global.css:101-109`, the `// ` prefix) **on purpose** — the same look
  `/games/`'s "Game achievements" heading has; M's look on staging decides whether it reads
  right. `test_achievements.py` gains one case (the tag is `h2` when asked, `h3` by default).
- `/fortknight/keep/` (`keep.astro:27` `<h1>Keep</h1>`) and the fourteen `/fortknight/days/<dayKey>/`
  pages (`<h1>A day of the fortnight</h1>`) are followed by `renderDayPanel`'s `h3` panels
  (`src/lib/keep-view.js`) with no `h2` between — the same skip fifteen times (gemini F2,
  verified on the seeded capture: `heading "Keep" [level=1]` then `heading "Sunday A" [level=3]`).
  `renderDayPanel(day, { headingLevel = 3 } = {})`, where **`headingLevel: null` renders no
  heading** — `days/[dayKey].astro:79` already appends its own `h1` with the day label, so the
  panel's heading there would only repeat it (gemini F3, verified: `heading "Sunday A" [level=1]`
  then `heading "Sunday A" [level=3]`); the day pages pass `null`, `keep.astro` passes `2`, and
  the keep page's later season and year headings are already `h2`, so it reads h1 → h2s. `KeepStyles.astro:21`'s `.keep-day h3 { margin: 0; font-size: 1.5rem }`
  becomes `.keep-day :is(h2, h3)` so the day headings keep the size the page's "readable across
  a room" requirement is about (`faces.css:35` would otherwise give an `h2` 1.1rem).
  `tests/test_keep.py` has no rendering class today (its classes validate, export age, slice
  colours, menu grouping, style scoping, keep-fed pages and boot): it gains `RenderDayPanelTests`,
  driven through node with a small stub implementing `createElement`, `appendChild`,
  `textContent` and `className` (`keep-view.js`'s `element()` helper uses those; the
  `test_achievements.py` stub only implements `append`), with two cases — level 2 when asked, no
  heading on null (gemini round 4 F4).
- Seeded `/fortknight/` announces `Your fortnight` (h2, the keep grid at `index.astro:28`) before
  the page's `<h1>FortKnight</h1>` (`:30`, inside the thesis panel) — the first heading a listener
  meets is not the title (gemini F2, verified). The fix: `#keepGrid` moves **inside** the
  thesis panel, directly after `<h1>FortKnight</h1>` (kimi round 4 F2 corrected the earlier
  citation — no face page carries a bare top-level h1; `keep.astro:26-27` keeps its h1 inside a
  panel too). The no-keep look is then byte-identical (the grid is hidden), and with a keep the
  grid sits under the title inside the panel, above the lede — the with-keep state is on M's
  staging look. The page's comment at `:97` ("the prerendered h1 below is the document's one
  h1") is corrected to say above.
- `/games/` renders `<h1>Games</h1>` (`games/index.astro:18`) then every game card's title as `h3`
  (`GameCard.astro:14`), before the `h2` at `:38` — a skip on the first card (gemini round 3 F1,
  verified). Card titles become `h2` with a class (`card-title`) whose rule ports the
  component's existing scoped `h3` block wholesale — `GameCard.astro:52`'s `margin: 0` and its
  size (kimi round 4 F3: `global.css:103` would otherwise give each title `margin-top: 2.2em`) —
  and sets `::before { content: none }`, so the grid does not sprout `// ` on every title; `/games/` then reads h1 → h2 cards → h2 "Game achievements" → h3 groups.
Any other failure the gate finds on an untouched page is **reported per route in the handoff
report**, fixed in the batch only when it is a one-line semantic fix (a missing accessible name,
a missing landmark element), and otherwise left for M to decide — the same rule as a red
baseline on untouched code. **Which wins when they conflict** (kimi F2): a red the executor may
not fix is reported INCOMPLETE with the route and the finding; the batch is not green, the
deploy waits, and M rules. There is no "green with a red inside".

**Target shape — the reflow pass.** `screenshot-pages.mjs` gains a `reflow` entry beside
`largetext`, opt-in under the same `LARGE_TEXT=1` switch — **the switch keeps its name** (kimi
F6), its comment says it now runs both extra passes, and the filter at `:95` names both opt-in
labels (gemini round 3 F5). The harness's own init script (`:120-123`, settings and keep only)
is replaced by the scenarios module's init script, so the shots gate measures the populated
boards too — one seeding for all three gates: viewport `{ width: 320, height: 480 }`,
`deviceScaleFactor: 2`, touch and mobile, no shots, overflow only. **320 CSS px is the width**
(M, 2026-09-06, gemini F3): it is WCAG 1.4.10's reflow requirement — 200% zoom on a 640px window
— and the built site is clean there on **all 41 non-stub routes, measured with each keep
fixture seeded and the boards populated** (kimi F2, gemini F4: the `.keep-wheel` fits). At 160
CSS px (200% zoom on a 320px phone, the template's literal reading) every studio page overflows
by 108px because the header's wordmark, Aa control and menu need 268px; that is a header
redesign, **filed with the numbers** at close-out, not this batch. The summary line counts the pass. A route that scrolls
sideways at 320px is reported the same way as any other overflow; the executor fixes it when
the cause is in the achievements board's own styles and reports it otherwise — with one fix
ruled in advance (M, 2026-09-06): **if a header's FortKnight link is what overflows** (`src/layouts/BaseLayout.astro:32`, the
`STUDIO_NAV` entry `{ href: '/fortknight/', label: 'FortKnight' }`), it becomes its emoji button
— `FACES.fortknight.logo`, `🏰🛡️` from `src/lib/faces.js:12` — in the icon-only pattern the face
header already uses for the studio button (`FaceLayout.astro:82-84`: the emoji as the link text,
`aria-label` carrying the name, `title` carrying the name and blurb), so the announce gate still
hears "FortKnight" and the postbuild prose gate sees no glued word. The same rule applies to a
face page's header if its own text entries are the overflow: the emoji with the name as the
accessible label, never a wrapping fix.

**Target shape — wiring.** `package.json`: `"announce": "node scripts/announce-check.mjs"`, and
`verify` runs it after `a11y` and before the shots. `deploy.yml`: an `Announce audit` step
between `Accessibility audit` and `Layout gate`, same shape, and the Layout gate's comment
(`:80-82`) names both extra passes (kimi round 3 F6). The batch **times `npm run verify` end to
end locally** (the identical chain), quotes the wall time in the report, and sets the job's
`timeout-minutes` (`:40`) in the same diff to twice that, never below the current 30 (kimi round
4 F1: the first CI run of the enlarged chain is the staging run the deploy gates on, so the
budget cannot be set reactively). The template's two lines become:
- `[ ] Screen-reader pass: `npm run verify`'s announce gate is green on every page (landmarks,
  one h1 with no skipped levels, every control and region named) — and, for a **new**
  interaction, one VoiceOver or NVDA listen of it, named here`
- `[ ] Reflow: `npm run verify`'s reflow pass is green (no sideways scroll at 320 CSS px, WCAG
  1.4.10); a look at 200% text size on a phone for clipped text is still yours`
README § Accessibility lists four gates and says what the announce gate hears and does not;
`CLAUDE.md` says "four gates" where it says three and names the pass; the *Where to look* row
gains the script.

**Tests.** `tests/test_announce_check.py` drives `announce-tree.mjs` through node (the
`helpers.run_node` pattern): the parser reads the two committed real captures into nodes (the
achievements capture yields nine headings — one `h1` and eight `h2`s — with their levels, the
four landmarks, every
link named, the `/url` and `text` lines ignored; the fixknitt capture yields the `[expanded]`
attribute on the summary and the `- group: Peripheral` form) and errors on a line in none of the
documented forms; the findings function reports each of the four rules from small hand-edited
variants of those captures — a second `main`, no `contentinfo`, two `h1`s, an `h2` before the
`h1`, a skipped level, a bare `button`, a nameless `region` — and reports nothing for the clean
captures; the parser reads the container form, a heading with attributes and no colon, the
single-quoted-key form and an escaped quote inside a name; and `missingSentinels` reports a
missing heading text for a route in the map and nothing for a route outside it.

**Gates:** `npm run verify` (now validate → tests → check → build → axe → **announce** → shots
with the two extra passes). The report quotes every gate's summary line, the axe gate's
analysed-page count before and after the extraction, the announce gate's per-route output when
it found anything, and the shots line (`N route(s) × 5 viewport pass(es)`).

**Leaves out:** a keyboard-order gate; touching FortKnight's pages beyond one-line fixes the
gate names; any change to what the pages say.

Over the hook's threshold — code-mode review before it commits.

## The deploy (planner, after batch 1 is on `dev` and its staging run is green)

1. `git -C insiculous_web fetch origin`; confirm `origin/main..origin/dev` is the expected set and
   `origin/dev..origin/main` is empty; confirm the latest `Deploy dev` run for `origin/dev`'s
   head is `success` (`gh run list -R beinsiculous/insiculous_web`), and that
   `https://dev.beinsiculous.com/achievements/` serves the board.
2. The manual lines are M's, on staging: the keyboard walkthrough of `/achievements/`,
   `/games/`, `/profile/` and `/fortknight/fixknitt/` (Tab reaches every link and control, focus
   visible each step, Escape closes the Peripheral strip and returns focus to its summary) —
   ticked only if M did it and says so; and the visual look at 200% text size on a phone —
   **redone by M on staging after the batch lands** (kimi round 3 F1: the batch re-levels
   headings on four pages and moves one; M's earlier look was of the pre-batch tree). The
   planner measures nothing for those boxes (kimi F2).
3. `gh pr create -R beinsiculous/insiculous_web --base main --head dev` with the template
   filled — **hand-built on the new lines**, because GitHub fills a PR body from the base
   branch's template and the new template lands with this merge (kimi round 3 F5); the body says
   so, and the old VoiceOver/NVDA line is superseded by the quoted gate output: *What changed* names both efforts and their commits; `npm run verify` ticked (CI run
   id on `dev`'s head); the screen-reader and reflow lines ticked by the gates, with the announce
   gate's per-page count quoted and the new interaction (Peripheral) named as **listened to by:
   nobody yet** unless M has done it — the template asks for a listen on a new interaction and
   the PR says truthfully whether one happened; the keyboard line ticked only by M; images and
   labels: none new.
4. **M's go**, then `gh pr merge dev --merge -R beinsiculous/insiculous_web` (the PR named, since
   this session sits on `m` — gemini round 3 F6; main receives merges, never squashes), then watch the
   `Deploy` run on `main` — `gh run list -R beinsiculous/insiculous_web --branch main --limit 1
   --json databaseId`, then `gh run watch <id> -R beinsiculous/insiculous_web` (gemini round 4
   F7) — then `https://beinsiculous.com/achievements/`
   carries `data-catalogs` and the six game headings, and `/games/` and `/profile/` answer 200.
   **Rollback** (kimi F5): if production shows what staging did not, revert the merge commit on
   `main` (`git revert -m 1`, pushed through a PR like any change to `main`) and the deploy run
   restores the previous build; the planner does it on M's word. **Fixing forward after that**
   (kimi round 2 F1): the reverted commits are already `main`'s ancestors, so re-merging `dev`
   reapplies nothing — the path is to revert the revert on a branch, merge the fix into it, and
   PR that; and the content check in this step runs on that re-deploy too.
5. Close-out: `git -C insiculous_web fetch`; local `main` is not checked out by this session and
   stays untouched; the effort's follow-ups filed (`file-issue`), the plan marked, memory if the
   deploy taught anything.

## Verification, end to end

- `npm run announce` on a tree with a deliberate skipped heading fails naming the route and the
  heading; on `dev` after the batch it is green on every route and scenario.
- `LARGE_TEXT=1 npm run shots` reports five passes and no sideways scroll at 320 CSS px.
- The PR's checklist has every ticked box backed by a gate line or a quoted measurement, and
  the one it cannot back is unticked and says why.
- After the merge, the production run is green and the three pages serve the new board.

## Follow-ups to file (not this effort's work)

- A keyboard-order gate (Tab reaches every control in DOM order, focus visible) — the last
  manual line, measurable the same way step 2 measures it by hand.
- The studio header at 200% zoom on a 320px phone (160 CSS px): every studio page overflows by
  108px because the wordmark, the Aa control and the menu need 268px (measured 2026-09-06 on
  `/`, `/achievements/`, `/games/`; the face pages fit). A header redesign — wrap, or the
  wordmark as its icon at that width — filed with the numbers.
- If the reflow pass finds overflow on untouched pages at 320px: one issue per page with the
  numbers.

**Clearing:** safe now and at any point after this plan is written — nothing runs in the
background, and the state lives in the tracked plans, the scoreboard, the board and memory.
