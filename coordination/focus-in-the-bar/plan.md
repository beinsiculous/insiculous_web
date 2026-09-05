# Focus in the Bar — the handoff plan

**v3 — settled 2026-09-05 after two review rounds** (round 1: kimi seven findings, gemini five; round 2:
gemini six, kimi four; adjudicated with M, `review/focus-in-the-bar/rebuttal-1.md` and `rebuttal-2.md`).
Decisions are recorded in place below; the rebuttals explain them.

Sprint *Focus in the Bar* (`beinsiculous/insiculous_web`, milestone of the same name): the face nav
says what the loaded keep focuses on. Picked by M on 2026-09-05 over three alternatives; run through
the **handoff loop** (`insiculous_web/.claude/skills/handoff-loop/SKILL.md`): this session plans and
commits, kimi and gemini review the plan, gemini executes one batch at a time from a handoff prompt,
kimi and the planner review each batch before it lands.

## Context

The face nav under `/fortknight/` is ten static pills (`src/lib/faces.js` `faceNav()`, rendered by
`src/layouts/FaceLayout.astro:79-85`). The keep already carries the season's focus categories
(`season.focus[]` = `{key, label}`, keyed to the closed seven), but nothing on the site knows which
stone is which category, so the bar looks the same for every fort. Four issues, one sprint, decided
with M on 2026-09-01 and amended by the categories ruling on 2026-09-02:

| issue | what | size |
|---|---|---|
| #25 | `faces.css` folds the nav with a `min-width`/`max-width` pair on one value; at exactly 640px both match and the header becomes a 495px wall | Small |
| #30 | the rule and the mapping: `category` on each stone entry of `faceNav()`, `focusCategoryKeys(keep)` in `keep.js`; nothing visible changes | Small |
| #31 | `FaceNav.astro`: the focus stones as category pills in focus order, the other stones behind one **Peripheral** disclosure; no keep → all seven peripheral | Medium |
| #32 | six places still say the nav is ten pills | Small |

Decided (M, 2026-09-01): pill text is the **category only** (stone name in `title` and `aria-label`);
with no keep or no focus every stone sits in the disclosure; the disclosure is called **Peripheral**;
the mapping lives on `faceNav()`; the pills read `season.focus`, **never `meta.foci`** (a different
axis — `fortknight/DOMAIN.md`, *Composition*). Fret Knot's label is **Working**, not Work
(`docs/megaseed/categories.md` (f); the #30 body's table predates it).

Not in scope: named keep slots per profile (the nav reads the stored keep through `loadKeep()` and follows when they
land); `.nav-links` wrapping the header to 170–206px across ~700–1152px (noted on #25, out of scope
there too); a general link crawler; opening `<details>` inside the axe gate (see *Follow-ups*).

## Where things live

- **This plan, tracked:** `insiculous_web/coordination/focus-in-the-bar/plan.md` — the repo that owns
  the code, per the skill (`review/` is gitignored and does not survive a clone). The devlog effort
  used the same layout in the working set (`coordination/devlog/plan.md`, now closed).
- **Scoreboard:** `insiculous_web/coordination/focus-in-the-bar/reviewer-comparison.md`.
- **Transients:** `insiculous_web/review/focus-in-the-bar/` — `plan.md` (a copy, because
  `scripts/request-review.sh` requires its artifact under `review/<subject>/`), `review-N.md`
  (kimi), `review-N-gemini.md`, `rebuttal-N.md`, `handoff-<batch>.md`, `draft-<batch>.diff`,
  `draft-<batch>-fixed.diff`, `review-N-claude.md`.
- **Branch:** `m` in every repo on Danny (M's machine), merged to the shared `dev` after each commit;
  `main` only by PR. Both the working set and `insiculous_web` were on `main` when this plan was
  drafted — switch before the first commit: `git checkout m` (working set) and
  `git -C insiculous_web checkout m` (the web repo's staged `.idea` files are untracked on `m` and
  carry over; `m` and `dev` have identical trees there).

## Ground rules for every batch

Written for the executor (gemini, driven by M in another window) and carried verbatim into each
handoff prompt, adapted from `prompts/handoff-batch.md` — whose gate block is the Rust engine's and
must be replaced with this repo's:

1. Branch `m`, checkout `insiculous_web/`. Touch only the files the batch names plus what a build
   forces. **Stage everything you touched, new files included; do not commit.** If you must stop,
   stage what you have and report **INCOMPLETE**.
2. Read first: this plan § *Ground rules* and the batch section; `CLAUDE.md` § *Coding conventions*
   and § *Invariants*; the issue body the batch names (quoted into the handoff, not fetched).
3. Conventions: human-readable names, no abbreviations (loop variables included); no new
   dependencies, no UI framework, no build step for `src/lib`; `src/lib` is untyped and node-tested,
   `src/components` IS type-checked by `astro check` so DOM lookups there are guarded
   (`StoneEmptyState.astro` is the model); prose uses curly apostrophes (`’`) and an inline tag
   stays on its word's line (`scripts/lib/prose-check.mjs` gates both); no `order` in CSS — source
   order is tab order is paint order (WCAG 2.4.3, `faces.css:96-105`); every selector for a
   `<details>` in the bar is scoped to its own class, never bare `summary` (the Aa control and the ☰
   are `<details>` in the same bar).
4. Doc lines the batch names land in the same change; a guide describing a thing the batch removed
   is a defect.
5. **Gates, all clean before you report:**
   ```
   npm run verify        # validate → python3 -m unittest discover tests → astro check → build (+ postbuild-check) → axe over every page → LARGE_TEXT=1 shots
   ```
   `python3 -m unittest discover tests` alone is the fast loop while working; the report quotes the
   verify run's summary lines, including the shots line (`N route(s) × 4 viewport pass(es)`).
6. **Report shape:** each gate's summary lines; every batch item as done / done differently because …
   / not done because …; the one non-obvious decision, if any; any hunk outside the batch's files,
   by file and line; then verbatim `git status --porcelain -- <the paths you touched>` (only
   `A`/`M`/`D` in column one — nothing `??`, nothing modified-but-unstaged) and the tail of
   `git diff --cached --stat`.

Standing rules the planner holds: one batch out at a time; while a batch is out the planner neither
edits nor runs `npm` in that checkout; the planner never writes skip trailers; a diff over the
commit hook's 100-line threshold is committed only after code-mode review, with `ADV_REVIEWED=1`
asserting the review happened.

## Batch 1 — #25: the fold boundary in `faces.css`

> **DONE 2026-09-05 — `dc64670` on `m`, closing #25.** Executor gemini (`review/focus-in-the-bar/report-1.md`);
> reviewed by kimi (three findings) and the planner (two), all accepted (`rebuttal-3.md`): the pin now
> covers BaseLayout's 66rem fold too and strips comments first, the fold comment carries both halves of
> the pair's failure and cites the fallback issue **beinsiculous/insiculous_web#45** (filed, P3).
> Measured on the built site: 639px ☰ only in a 63px header; 640px and 641px the flat bar with no ☰.
> Line numbers below are as of the plan's writing; batch 1 grew faces.css's fold comment by four lines.

**Files:** `src/styles/faces.css`; new `tests/test_face_nav.py`; `src/layouts/BaseLayout.astro` (one
comment clause).

**Target shape.**
- `faces.css:106` `@media (min-width: 40rem)` → `@media (width >= 40rem)`.
- `faces.css:114` `@media (max-width: 40rem)` → `@media (width < 40rem)`.
- `faces.css:234` `@media (max-width: 40rem)` (the phone geometry block) → `@media (width < 40rem)`,
  so exactly 640px lands on one side for every rule in the file. *Judgment call, open to review:* it
  is not in #25's text, but leaving it makes 640px the flat bar with phone padding.
- The comment at `:96-105` loses "Overlapping at exactly 40rem is harmless: the phone block is later"
  (false — the two blocks set disjoint properties, so both survive) and states the real rule: range
  syntax is the one form with no overlap and no gap at any width, fractional included; the studio
  twin is `BaseLayout.astro` (`width >= 66rem` / `width < 66rem`, its comment at `:312`). The ☰
  comment at `:85-86` ("same 40rem breakpoint") stays true.
- **The same comment states the accepted regression (M, 2026-09-05, kimi F1):** an engine without
  Media Queries 4 range syntax — Safari before 16.4, Chrome before 104, Firefox before 63 — drops both
  queries, and because this file's base state is the hidden ☰ with the panel folded, those engines get
  no face nav at all. That is the trade the studio layout already made when `BaseLayout.astro` adopted
  range syntax, and #25 chose it knowingly; the fallback for both layouts is a filed follow-up (below),
  not this batch's work.
- `BaseLayout.astro:312-319`: its range-syntax comment says faces.css uses the min/max pair; one
  clause makes it read "the pair faces.css used until #25" so the two twins do not cite each other
  as documenting contradictory rules (kimi F5).
- `tests/test_face_nav.py`, class `FoldBoundaryTests` (source-level, like `PageStyleScopingTests` in
  `tests/test_keep.py`): `faces.css` contains `(width >= 40rem)` and `(width < 40rem)` and contains
  neither `(min-width: 40rem)` nor `(max-width: 40rem)`. Module docstring says what the file pins and
  why no gate sees it (the shots run at 390, 641 and 1440, never 640).

**Leaves out:** the `.nav-links` wrap height (noted on #25); any rule change in `BaseLayout.astro`
(the comment clause above is its only edit).

**Take-back verification (planner):** `npm run verify`; then a scratch Playwright script (not
committed) over `dist/` at 639/640/641px on `/fortknight/`: exactly one of {☰ summary visible, flat
bar visible} and the header one row tall on each side. Record the three measurements in the review.

## Batch 2 — #30: the mapping and the reader

> **DONE 2026-09-05 — `41f8808` on `m`, closing #30.** Executor gemini (`review/focus-in-the-bar/report-2.md`);
> reviewed by kimi (two findings) and the planner (two), all accepted (`rebuttal-4.md`): the mapping is
> pinned path by path, not as a set; FaceLayout's header sentence and the test docstring were made
> consistent; the faces.js header's "(built by #31)" is batch 3's to drop. `npm run verify` green, 307 tests.

**Files:** `src/lib/faces.js`, `src/lib/keep.js`, `src/layouts/FaceLayout.astro` (one line),
`src/styles/faces.css` (one rule and one comment), `scripts/postbuild-check.mjs` (wording),
`tests/test_face_nav.py`.

**Target shape.**
- `faces.js` `faceNav()`: the seven stone entries gain `category: { key, label }`; Overview, Keep
  and Achievements carry none — that absence marks a non-stone. Keys and labels are
  `data/categories.json`'s, copied (nothing under `src/` reads `data/`, `CLAUDE.md` says so on
  purpose) and **pinned by a test** (below):

  | path | key | label |
  |---|---|---|
  | `forkknife/` | `meals` | Meals |
  | `freshkeep/` | `cleaning` | Cleaning |
  | `folkknowledge/` | `friends-family` | Friends & Family |
  | `fixknitt/` | `operations` | Operations |
  | `foekiss/` | `spirituality-development` | Spirituality & Development |
  | `funknee/` | `health` | Health |
  | `fretknot/` | `working` | **Working** |

  `shortLabel` goes from all ten entries. The header comment (`:15-28`) is rewritten: the menu is
  Overview, Keep, the seven stones each carrying its category, Achievements; the bar shows the
  stored keep's focus stones by category and the rest sit behind Peripheral, all seven with no keep
  (#31 builds it); the "every entry has a page, check 7 gates it" warning stays; the `shortLabel`
  paragraph goes. Paths unchanged, so postbuild check 7 keeps gating every entry.
- `keep.js`, beside `describeSection`:
  ```js
  /** The current season's focus category keys, in focus order: strings only, deduped, [] when the
   *  keep has no season or the season carries no focus. Labels are the site's own (faceNav()), matched
   *  by key — the keep's focus[].label is not read. */
  export function focusCategoryKeys(keep)
  ```
  Defensive like `describeSection`: `season` null or absent, `focus` absent or not an array, an entry
  without a string `key`, all handled without throwing. No `partitionStones` helper (#31 partitions
  in the DOM by `data-category`).
- `FaceLayout.astro:82`: `<span class="nav-full">{item.label}</span>{item.shortLabel && …}` becomes
  `{item.label}` — the two spans go now that nothing feeds them, so the tree never carries a property
  the data no longer has. `faces.css:80-82` (`.nav-short`) and the comment at `:243-246` (was `:236-239` before batch 1) go with
  them. *(#31's text says these go with #31; they move here because a removed field must not be
  referenced in between — correction carried into the batch that acts on it.)*
- `scripts/postbuild-check.mjs`: check 7's wording at `:24-26`, `:158-166` and the message at
  `:181-184` — "pill" → "entry" ("take the entry out of `faceNav()`"); no logic change.
  `tests/test_postbuild_check.py` does not assert these strings (checked).
- `tests/test_face_nav.py` gains two node-driven classes (`helpers.run_node`, `STDIN_PRELUDE`, the
  `test_keep.py` pattern):
  - `FocusCategoryKeysTests`: `tests/fixtures/keep.sample.json` → `["meals","cleaning","working","health"]`;
    `keep.other-household.json` → `["meals","working"]`; `season: null`; no `focus`; `focus` not an
    array; entries without `key`; non-string keys; duplicates deduped keeping first position.
  - `FaceNavMappingTests` (imports `faces.js` from node the way `postbuild-check.mjs` does — `withBase`
    is only called by `facePath`, never by `faceNav()`): every stone entry has a `category` whose key
    is unique and drawn from the seven; Overview, Keep and Achievements have none; the ten paths in
    order are unchanged; **the set of `{key, label}` pairs equals `data/categories.json`'s `order`
    and `categories[*].label`** — the pin that holds this copy to its source (the categories ruling's
    rule: every hardcode of the list is dispositioned with the check that holds it).

**Leaves out:** anything a visitor sees. `npm run verify` green; the rendered text and geometry of
every face page are identical, and every face page's DOM loses the two label spans — that is the diff
to expect in `dist/`, and the only one (kimi F4).

## Batch 3 — #31 + #32: `FaceNav.astro`, the Peripheral disclosure, and the six guides

One reviewed diff, **two commits by pathspec**: the code and its tests close #31; `CLAUDE.md`,
`README.md` and `docs/app.md` close #32 (adjacent commits, one push — the guides never describe a
nav that is not on the branch).

**Files:** new `src/components/FaceNav.astro`; `src/layouts/FaceLayout.astro`;
`src/styles/faces.css`; `src/lib/keep-store.js`; `src/pages/fortknight/keep.astro`;
`scripts/a11y-check.mjs`; `tests/test_face_nav.py`; `tests/test_keep.py` (one class); `CLAUDE.md`
(`AGENTS.md` is a symlink to it — edit once); `README.md`; `docs/app.md`.

**Target shape — the component.** `FaceNav.astro` owns the `<nav class="nav-links">` FaceLayout
renders today, including `isActive` (moved, unchanged: Overview is exact plus `days/`, others are
prefix matches). Props: `face`. Server-rendered, no-keep state, in this order:

```html
<nav class="nav-links">
  <a class="nav-link" href=…>Overview</a>
  <a class="nav-link" href=…>Keep</a>
  <details class="nav-peripheral">
    <summary class="nav-link{ active when the current page is a stone }">Peripheral<span class="nav-caret" aria-hidden="true">▾</span><span class="visually-hidden nav-current-section"{ hidden unless the current page is a stone }>, current section</span></summary>
    <div class="nav-peripheral-panel">
      <a class="nav-link" data-category="meals" href="…/forkknife/" title="Fork Knife" aria-label="Meals, Fork Knife">Meals</a>
      … six more, faceNav() order, the current one also carrying class="active" and aria-current="page" …
    </div>
  </details>
  <a class="nav-link" href=…>Achievements</a>
</nav>
```
- Every active link carries `aria-current="page"` (BaseLayout already does; FaceLayout only set
  `class="active"`).
- **Never server-render `open`**: the sticky `.site-nav` is the panel's containing block, so an
  open-on-load panel would cover the `h1` on every peripheral stone page at desktop width.
- `aria-label` begins with the visible text (WCAG 2.5.3); `title` carries the stone name; the caret
  is an `aria-hidden` span on the same source line as "Peripheral" (the prose gate skips aria-hidden
  spans), never CSS `content:`.
- **The summary says when the current page is inside it (gemini F3).** A closed `<details>` prunes
  its content from the accessibility tree, so the `aria-current` link inside is unreachable and the
  summary's `.active` colour is the only cue. The visually-hidden span above gives the summary the
  accessible name "Peripheral, current section" exactly when a link inside the panel is active;
  `[hidden]` hides it otherwise (`faces.css:168` after batches 1–2 — `[hidden] { display: none !important }`
  makes `hidden` win over any display rule). The
  same code toggles `.active` and the span, server-side and in the script.
- Header comment records the accepted side effects and boundaries: the bar first paints
  all-peripheral and grows when the module script runs (as the profile dropdown does; an inline script
  would bypass `validateKeep`); **the nav reads storage non-destructively** — `loadKeep()` plus
  `validateKeep()`, never `readStoredKeep()` — so it deletes nothing and a keep-fed page's own boot
  keeps its "cleared"/"kept" verdict and reason (round 2, both reviewers' F1; round 1's kimi F7
  behaviour change is thereby withdrawn — no face page clears anything it did not clear before);
  **the bar mirrors storage, not the page's in-memory keep** — when storage refuses `storeKeep` the
  page draws the fortnight and says it was not stored while the bar stays all-peripheral (kimi F4,
  round 2); **an unknown `season.focus` key drops silently** — the keep schema enumerates the seven, so
  only a hand-made non-conforming keep can hit it, and the nav is not the keep's validator (kimi F3,
  round 2); and `applyFocus` is idempotent by contract, because a keep-fed page's boot-time clear of
  unreadable storage dispatches the change event and runs it a second, sequential time.

**The store notifies, the nav follows (gemini F1).** `keep.astro` adopts a picked file and forgets one
in place, with no reload, so a nav that reads storage once at boot desyncs on this sprint's own
acceptance test. So:

- `src/lib/keep-store.js` gains `export const KEEP_CHANGED_EVENT = "beinsiculous:keep-changed";` and
  `export function storeKeep(text)` (the `localStorage.setItem(KEEP_STORE_KEY, text)` that `keep.astro`
  does inline today, moved here, still throwing to the caller when storage refuses). `storeKeep` and
  `clearKeep` end by dispatching `new Event(KEEP_CHANGED_EVENT)` on `document` when
  `typeof document !== "undefined"` (the node tests import this module with no DOM). The header says
  why the store notifies: two components on one page read it, and neither may know about the other.
- `src/pages/fortknight/keep.astro` calls `storeKeep(text)` where it wrote storage itself; its Forget
  handler already calls `clearKeep()`. Nothing else in it changes. (`/profile/`'s Forget is a
  BaseLayout page with no face nav; its `clearKeep()` dispatching to nobody is fine.)
- `FaceNav.astro`'s script owns one idempotent function and calls it at boot and on the event:

```js
import { KEEP_CHANGED_EVENT, loadKeep } from "../lib/keep-store.js";
import { focusCategoryKeys, validateKeep } from "../lib/keep.js";
// Type-checked, so every DOM read is narrowed: querySelectorAll("a[…]") is NodeListOf<Element>, and
// Element has no dataset (gemini F4, round 2).
const details = document.querySelector("details.nav-peripheral");
const panel = details?.querySelector(".nav-peripheral-panel");
const summary = details?.querySelector("summary");
const currentSection = summary?.querySelector(".nav-current-section");
// The seven stone links in faceNav() order, captured once: folding back is "append these, in this order".
const stoneLinks = panel ? [...panel.querySelectorAll<HTMLAnchorElement>("a[data-category]")] : [];

/** The stored keep's focus keys, read without touching storage: loadKeep() returns null for an
 *  unparseable value and never clears it — that verdict, and its reason, belong to the page's own boot. */
function storedFocusKeys() {
  const parsed = loadKeep();
  if (parsed === null) return [];
  const check = validateKeep(parsed);
  return check.ok ? focusCategoryKeys(check.keep) : [];
}

function applyFocus() {
  if (!(details instanceof HTMLDetailsElement) || !panel || !summary) return;
  details.open = false;                              // a keep change never leaves the strip open (gemini F3, round 2)
  panel.append(...stoneLinks);                       // fold everything back, in faceNav() order — idempotent
  const byCategory = new Map(stoneLinks.map((link) => [link.dataset.category, link]));
  const promoted = storedFocusKeys().map((key) => byCategory.get(key)).filter((link) => link !== undefined);
  details.before(...promoted);                       // one move: focus order = DOM order = tab order = paint order
  details.hidden = panel.querySelector("a") === null;               // every stone is a focus
  const currentInside = panel.querySelector("a.active") !== null;
  summary.classList.toggle("active", currentInside);
  if (currentSection) currentSection.hidden = !currentInside;
}
applyFocus();
document.addEventListener(KEEP_CHANGED_EVENT, applyFocus);
```
Dedupe is `focusCategoryKeys`'s; an unknown key is a Map miss. A stored value that will not parse or
will not validate leaves the nav all-peripheral, and the page's own boot reports why — the nav says
nothing and deletes nothing.

Closers, all scoped to `details.nav-peripheral` (gemini F2 — the Aa control's pair plus one it lacks):
- `focusout` on the details: when `event.relatedTarget` is an element outside it, `details.open = false`
  (a null `relatedTarget` — focus to the body — is left to the click-outside closer, so a click on the
  panel's own padding does not close it).
- `keydown` Escape on the document: if `details.open`, close it, and call `summary.focus()` **only when
  `details.contains(document.activeElement)`** — never steal focus from `main`.
- `click` on the document: if `details.open` and the target is outside it, close it.

**FaceLayout.astro:** imports `FaceNav`, renders `<FaceNav face={face} />` where the `<nav>` was,
drops `faceNav`/`navItems`/`isActive` from its frontmatter (keeps `facePath`, `PROFILE_PATH`,
`STUDIO`, `studioPath`). Comments updated: `:10-13` (batch 2 already rewrote the menu sentence; the
rest stands), `:53` ("six pills"), `:60-68` — the order argument extended: an open Peripheral
panel is painted below the bar but tabbed before Achievements, the same compromise the Aa panel makes.

**faces.css:** a new block after the ☰ rules (`:81-108` after batches 1–2), every selector scoped to
`.nav-peripheral`; the summary
is `class="nav-link"` so it inherits the pill look, `themes.css:71-73`'s fort-knight nav colour
(without it the summary is `--muted` on the plank and fails contrast), the coarse-pointer 44px rule,
and the `.menu-panel .nav-link` full-width row inside the ☰ panel. The wide/narrow rules go inside
the range-syntax blocks batch 1 made:
```css
.nav-peripheral { min-width: 0; }
.nav-peripheral > summary { list-style: none; }
.nav-peripheral > summary::-webkit-details-marker { display: none; }
.nav-caret { display: inline-block; margin-left: 0.3rem; }
.nav-peripheral[open] > summary .nav-caret { transform: rotate(180deg); }
@media (width >= 40rem) {
  /* A full-width strip under the bar, positioned against the sticky .site-nav like .menu-panel — never
     anchored to the summary, so it cannot run past the viewport at 641px with four focus pills ahead
     of it. No white-space: nowrap, for the same reason (the Aa panel has it and must not be copied). */
  .nav-peripheral-panel {
    position: absolute; left: 0; right: 0; top: 100%;
    display: flex; flex-wrap: wrap; gap: 0.25rem; padding: 0.5rem 1.25rem;
    background: var(--background); border-bottom: 1px solid var(--line); box-shadow: var(--shadow);
    z-index: 20;   /* above main, below .a11y-panel's 30 */
  }
}
@media (width < 40rem) {
  /* Inside the ☰ panel: a static, indented column of the 44px rows .menu-panel .nav-link already gives. */
  .menu-panel .nav-peripheral-panel {
    display: flex; flex-direction: column; gap: 0.25rem;
    margin-left: 0.75rem; padding-left: 0.5rem; border-left: 2px solid var(--line);
  }
}
```
The existing `.site-nav .menu::details-content { display: contents }` targets `.menu` only. The
screenshot gate measures the closed state, so the open geometry is overflow-proof by construction
(full-width strip, wrapping), not by measurement.

**Gates that cover it.** `a11y-check.mjs` seeds `beinsiculous.keep` with the sample keep on every
route, so axe audits the promoted bar (four pills) on every face page, and the other-household pass
(two pills) on the keep-fed routes; postbuild check 7 still resolves every `faceNav()` entry; the
shots at 390/641/1440 and 125% text measure the closed bar.

**The gate learns to open the strip, and to count (gemini F4, kimi F2).** `a11y-check.mjs`'s
`DIALOG_ROUTES` loop becomes a general "open something, then audit" loop: each entry is
`{ route, seed, label, open, waitFor }`; `open` returns `true` or a string saying what it found. A
string is pushed to `failures` as `${route} [${label}] ${string}` and the entry `continue`s at once —
no `waitForSelector`, no axe (gemini F5, round 2); only `true` proceeds to wait for `waitFor` and run
axe. The two dialog entries keep their behaviour (`waitFor: "dialog.name-dialog[open]"`). Two entries
join, both on `/fortknight/fixknitt/` (a peripheral stone in both keeps, so the summary is active):
- seeded with `tests/fixtures/keep.sample.json`: `open` counts `a[data-category]` that are direct
  children of `.nav-links` (must be 4, in the order meals · cleaning · working · health) and inside
  `.nav-peripheral-panel` (must be 3), then sets `details.open = true`;
- seeded with nothing: 0 promoted and 7 inside, then opens.
Either count wrong returns the counts as the failure string, so `npm run verify` fails with the
partition it saw — the durable check that promotion happens — and axe audits the open strip in both
states (link contrast against `--background`, focus outlines, the visually-hidden current-section span).

**What no gate sees** (planner's manual pass at take-back): the `<40rem` nested column (axe runs at
desktop width); keyboard: Tab reaches the summary, Enter/Space opens, Escape closes and returns focus
only when focus was inside, Tab out of the strip closes it, Tab walks the strip then Achievements;
one screen-reader run (summary announces "Peripheral, collapsed" on a focus page and "Peripheral,
current section, collapsed" on a peripheral stone page; a pill reads "Meals, Fork Knife, link, current
page"); 200% zoom at 320px; one look in Firefox or Safari; and a scratch sideways-scroll measurement of
the open strip at 641px with the sample keep loaded.

**The wrap is measured before the commit, not after (kimi F3).** With the sample keep seeded the
641px pass renders eight items plus the brand, Aa, the profile select and the site links, and
`.site-nav` wraps rather than scrolls, so the gate stays green while the sticky header grows. At
take-back the planner measures the header's height at 641, 700 and 1152px with the sample keep
seeded (a scratch Playwright script over `dist/`), presents the three numbers with the rebuttal, and
M decides — ship as is, mitigate in this batch, or file with the numbers — before the batch commits.

**Tests.** `tests/test_face_nav.py`, class `FaceNavComponentTests` (source-level): `FaceNav.astro`
imports `loadKeep`, `validateKeep`, `focusCategoryKeys` and `KEEP_CHANGED_EVENT`, **does not import
`readStoredKeep` or call `clearKeep`** (the non-destructive read is a contract), adds a listener for
the event, renders
`data-category` for each of the seven, its `<details class="nav-peripheral"` carries no `open`, its
summary text is Peripheral with the `nav-current-section` span; `FaceLayout.astro` renders `FaceNav`
exactly once and no longer maps `faceNav()` itself; `keep.astro` imports `storeKeep` and no longer
calls `localStorage.setItem` itself. `tests/test_keep.py`, class `KeepStoreEventTests` (node-driven,
the `READ_STORED` stub pattern plus a stub `document` recording `dispatchEvent` calls): `storeKeep`
writes the key and dispatches once; `clearKeep` removes it and dispatches once; both run without a
`document` in scope (the node case) and dispatch nothing. Also extend
`StoredKeepBootTests.test_every_keep_fed_page_reports_the_kept_case`? **No** — the nav does nothing
on "kept"/"cleared" (the page's status line already reports them), and that is the right behaviour:
the nav stays all-peripheral.

**The six guides (#32).** The rule, written once in each file's own words: *the bar shows the stored
keep's focus stones, labelled by category; the rest sit behind Peripheral; with no keep every stone
is peripheral; the mapping is `faceNav()`'s `category`; every entry still has a page and
`postbuild-check.mjs` check 7 fails the build if one does not.*
- `CLAUDE.md:84` — the invariant bullet ("Its nav is ten pills … Every pill has a page").
- `CLAUDE.md:197` — "sits in the face nav (six pills: Overview · Keep · Achievements · Build ·
  Questionnaire · Assistant)" — stale since The Chain Comes Out; fixed in passing.
- `docs/app.md:22-25` ("The face's nav is ten pills") and `:32-34` ("Every pill has a page" → entry).
- `README.md:214-216` ("The face's nav is ten pills").
- `src/lib/faces.js` header and `scripts/postbuild-check.mjs` — done in batch 2; the sweep confirms, and
  **drops the header's "(built by #31)" parenthetical** so the Peripheral sentence reads as fact now that
  it is (planner's C2, batch 2 review).
- Stays as dated history: `docs/roadmap.md:23`, `:102` and `docs/app.md:131` ("six pills", inside the
  parked chain's record).
Done when `git grep -n -i -E "ten pills|six pills|every pill" -- CLAUDE.md README.md docs scripts src`
returns only those three history lines.

**What "done" looks like for the sprint.** No keep: `/fortknight/` shows Overview · Keep · Peripheral ▾
· Achievements and the strip lists all seven stones by category. Load `tests/fixtures/keep.sample.json`
on `/fortknight/keep/`: the bar becomes Overview · Keep · Meals · Cleaning · Working · Health ·
Peripheral ▾ (Friends & Family · Operations · Spirituality & Development) · Achievements. On
`/fortknight/fixknitt/` the summary is active with Operations current inside. Forget the keep and the
stones fold back. The other-household fixture gives two focus pills. `npm run verify` green.

## The loop, step by step

1. **On approval** (the ExitPlanMode hook will ask about review — the answer is this section):
   switch both repos to `m`; write this plan to `insiculous_web/coordination/focus-in-the-bar/plan.md`;
   `mkdir insiculous_web/review/focus-in-the-bar` and copy the plan there.
2. **Plan review, both reviewers on the same snapshot**, from inside `insiculous_web/` (the read
   scope — running from the working set would hand the reviewer every sibling repo):
   ```
   cd insiculous_web && nohup scripts/request-review.sh plan review/focus-in-the-bar/plan.md --reviewer=kimi   > review/focus-in-the-bar/request-kimi.log 2>&1 &
   cd insiculous_web && nohup scripts/request-review.sh plan review/focus-in-the-bar/plan.md --reviewer=gemini --out=review/focus-in-the-bar/review-1-gemini.md > review/focus-in-the-bar/request-gemini.log 2>&1 &
   ```
   Record dispatch timestamps and PIDs; wait on the PIDs (kimi six to eight minutes, gemini about
   four); a log with `INCOMPLETE`/error lines or a review without a Verdict is no review. Present
   every finding with my own assessment, adjudicate each with M (kimi is often skipped to save tokens
   and M signs — ask, never assume, never write trailers), write `rebuttal-N.md` covering both,
   revise the tracked plan, and **for every further round write the revised tracked plan to
   `review/focus-in-the-bar/plan-vN.md` immediately before dispatch and hand the reviewers that
   file** — the tracked file is the source of truth and the review copy never drifts from it (kimi
   F6). Repeat until M calls it settled. Commit the settled plan on `m` with its
   own pathspec (`ADV_REVIEWED=1`, honest — it was reviewed), then merge `m` → `dev`.
3. **Batch 1 handoff:** re-verify the section against the tree (grep every `file:line`), write
   `review/focus-in-the-bar/handoff-1.md` from `prompts/handoff-batch.md` with this repo's gates
   substituted, hand M the path. Hands off the checkout until the report arrives.
4. **Take batch 1 back:** reconcile the report's `--stat` with `git diff --cached --stat` and
   `git status --porcelain -- <scope>`; run `npm run verify` myself; the 639/640/641 measurement;
   `git diff --cached > review/focus-in-the-bar/draft-1.diff`; kimi code review detached (this diff is
   under the hook's threshold, so the review is the loop's, not the hook's — M may waive it); my own
   review to `review-N-claude.md`; adjudicate, `rebuttal-N.md`, apply accepted fixes myself, re-run
   the gates, snapshot `draft-1-fixed.diff` and diff it against the reviewed bytes; commit with `-F`
   and `--pathspec-from-file` (`fixes beinsiculous/insiculous_web#25`), mark the batch done in the
   plan with its own pathspec commit, merge `m` → `dev`, close #25 by hand (the `fixes` trailer only
   fires on `main`), update `reviewer-comparison.md`.
5. **Batches 2 and 3** the same way; batch 3 is over the threshold, so code-mode review is required,
   and its two commits (#31 code, #32 docs) each take their own pathspec file.
   *Settled 2026-09-05 after round 2 (M): no Critical, both reviewers converged on one design point,
   the rest were one-line decisions.*
6. **Close out:** every follow-up filed (`file-issue`); `scripts/check-skill-parity.sh` in the
   working set (no skill files change here, so it should stay green); the sprint's milestone
   description amended if its shape changed (it should not); memory note if anything about the loop
   itself was learned.

## Follow-ups to file (not this effort's work)

- `prompts/handoff-batch.md` in `insiculous_web` (and the working set's copy) carries the Rust
  engine's gate block (`cargo test`, `../games`, `check_wasm.sh`); a repo-neutral template with a
  per-repo gate slot, or a web twin, so the next effort does not rewrite it by hand. File on
  `beinsiculous/insiculous` (the canonical copy lives there).
- The axe gate now opens the Peripheral strip (batch 3) but still never opens the Aa control's
  panel, in either layout — the same gap, one entry each in the generalised loop.
- **Both layouts' fallback for an engine without range syntax is "no nav"** (kimi F1, accepted as a
  regression on 2026-09-05): `faces.css` and `BaseLayout.astro` both make the folded, hidden-☰ state
  the base and reach the flat bar only through a media query. Making the flat bar the base state and
  folding with one narrow query would give such an engine a wrapping flat bar and remove the
  boundary pair altogether; evaluate it for both files at once.
- The `.nav-links` wrap height at ~641–1152px with a loaded keep — measured in batch 3's take-back
  (kimi F3); filed with the numbers if M ships it as is.
