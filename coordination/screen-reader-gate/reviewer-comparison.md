# Reviewer comparison — the announce gate and the deploy

One row per review. Wall time is the review file's mtime minus the dispatch timestamp recorded in
`review/screen-reader-gate/.dispatched-N`. The review files are transient, so the notable catch is
quoted here, not linked.

| subject | reviewer | findings | real | false | policy rebuts | notable catch (quoted) | wall time |
|---|---|---|---|---|---|---|---|
| plan v1 | kimi | 6 | 6 | 0 | 0 | F1: "A parser written to the plan's grammar, with 'a line it cannot read is an error,' errors on the first real page of the first real run — while the Python tests, written from the same imaginary format, pass" — the captures proved it: `/url` lines under every link | 5m04s, 04:30:55 → 04:35:59 |
| plan v1 | gemini | 6 | 5 | 1 (F1: an open modal does not strip landmarks — measured, all present) | 0 | F2: "`renderDayPanel(day)` in `src/lib/keep-view.js` hardcodes an `<h3>` … all 14 day pages … `/fortknight/keep/` … fail Rule 2" — fifteen skips the plan had not seen | 3m17s, 04:31:17 → 04:34:34 |
| plan v2 | kimi | 6 | 5 | 1 (F2: no route overflows at 320 CSS px — 41 measured, both fixtures) | 0 | F1: "the PR diff shows only the fix commit, merges cleanly, and deploys old-main-plus-one-commit — the other 20 commits' worth of content stays reverted while everyone reads the green deploy as fixed" | 6m05s, 04:45:41 → 04:51:46 |
| plan v2 | gemini | 6 | 5 | 1 (F4: the keep wheel fits at 320, measured) | 0 | F3: "Two adjacent headings with identical text, level 1 and level 2, are rendered for a single entity … 'Heading level 1, Sunday A. Heading level 2, Sunday A.'" — v2's own fix would have caused it | 4m02s, 04:45:41 → 04:49:43 |
| plan v3 | kimi | 6 | 6 | 0 | 0 | F1: "The day headings on the page whose stated hard requirement is 'readable across a room' get smaller (1.5rem → 1.1rem) … a visible restyle of three pages … reaches production with all boxes honestly ticked" — the re-leveling was not style-neutral | 9m44s, 04:57:55 → 05:07:39 |
| plan v3 | gemini | 6 | 6 | 0 | 0 | F1: "`<h1>Games</h1>` is followed immediately by … `<h3>{game.data.title}</h3>` … level 2 skipped" — a fifth skip the plan had declared clean | file at 22:02:52 local |
| plan v4 | kimi | 5 | 5 | 0 | 0 | F2: "`keep.astro:26-27` actually has the h1 inside `<section class="panel">` — no face page has a bare top-level h1 today" — the planner's own citation was false | 7m22s, 05:21:55 → 05:29:17 |
| plan v4 | gemini | 7 | 7 | 0 | 0 | F4: "`test_keep.py` does not define `DOM_STUB` … the `DOM_STUB` in `test_achievements.py` only implements `.append()`, whereas `element()` and `renderDayPanel()` call `.appendChild()`" | file at 22:28:16 local |
| batch 1 code | kimi | 4 | 4 | 0 | 1 (half of F3: a Python twin of the sentinel counts, when the gate itself is the pin) | F1: "`maybePromptForProfile()` fires at boot and `showModal()` puts the dialog + backdrop in the top layer before every screenshot … the `/games/` 125% shot no longer shows the card grid at all" — confirmed by looking at the PNG | 7m41s, 06:32:49 → 06:40:30 |
| batch 1 code | claude (planner) | 5 | 4 + 1 note | 0 | 0 | C3: the post-fix fixture read `heading "// Be Insiculous — 0 of 1 unlocked"` — CSS generated content is part of the accessible name, so every studio h2 announced "slash slash"; `content: '// ' / ''` measured silent. Also C1: the executor's report quoted gate outputs that no script prints | — |
