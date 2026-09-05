# Reviewer comparison — Focus in the Bar

One row per review. Wall time is the review file's mtime minus the dispatch timestamp recorded
in `review/focus-in-the-bar/.dispatched-*`. The review files themselves are transient (`review/` is
gitignored), so the notable catch is quoted here, not linked.

| subject | reviewer | findings | real | false | policy rebuts | notable catch (quoted) | wall time |
|---|---|---|---|---|---|---|---|
| plan v1 | kimi | 7 | 6 | 0 | 1 (F1 accepted as a written decision rather than a code change) | F1: "faces.css's base state is the hidden ☰ … Safari < 16.4 … the entire header is reduced to the brand and the Aa control" — the fallback state of a fold is a decision nobody had written down | 6m28s (11:13:52 → 11:20:20) |
| plan v1 | gemini | 5 | 4 | 1 (F5: absolute positioning resolves against the padding box; measured) | 0 | F1: "keep.astro … calls adopt(parsed) to render the keep in <main> without a full page reload … the nav bar remains unchanged" — the sprint's own acceptance test would have failed on the page it names | 4m21s (11:13:52 → 11:18:13) |
| plan v2 | gemini | 6 | 5 | 0 | 1 (F6 cross-tab sync — not a property any face page has) | F1: "FaceNav.astro boots before the page content script … storage is already empty … The host page then executes showLoadPrompt(\"\"), wiping the status line" — the same finding as kimi's F1, independently | 5m18s (11:37:00 → 11:42:18) |
| plan v2 | kimi | 4 | 4 | 0 | 0 | F1: "Round 1's kimi F7 accepted *which pages* clear; it did not consider that the *reason text* is consumed by a reader that ignores it" — a reviewer auditing its own earlier acceptance | 5m56s (11:37:00 → 11:42:56) |
| batch 1 code | kimi | 3 | 3 | 0 | 1 (F1's base-state flip — the plan's round-1 decision, now #45's question) | F1: "The comment says the fallback is 'a filed follow-up'; I could not verify from the repository that the issue actually exists" — a comment claiming a record that was not there yet; filed as #45 before the commit | 1m52s (12:38:47 → 12:40:39) |
| batch 1 code | claude (planner) | 2 | 2 | 0 | 0 | C1: faces.css dropped the fractional-gap paragraph that BaseLayout:316 says "faces.css already documents" — the twin pointed at a record the batch had just deleted | — |
| batch 2 code | kimi | 2 | 2 | 0 | 0 | F1: "it never asserts *which path* carries *which key* … Operations focus pulls up Fun Knee — with all gates green" — the plan called the table pinned and the test pinned only the set | 2m12s (14:05:08 → 14:07:20) |
| batch 2 code | claude (planner) | 2 | 2 | 0 | 0 | C2: faces.js's header describes the Peripheral bar in the present tense one commit before it exists — the plan's own wording, caught only because #32 names that exact failure | — |
