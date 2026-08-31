// The site's planner face (docs/app.md): FortKnight (the fortnight schedule and its menu), a display-only
// face that renders the keep a visitor loads under /fortknight/; it shares the profile (/profile/) and the
// on-device settings with the studio site. The face carries its own `theme` (the skin in
// public/app/shared/themes.css). The studio pages of beinsiculous.com — including /profile/ — use their own
// layout entirely (src/layouts/BaseLayout.astro).
//
// The creation chain (Build / Questionnaire / Assistant) was removed from main on 2026-08-30 by the
// display-only ruling and is preserved at the tag `creation-chain-parked`. Nothing here builds a keep.
import { withBase } from "./paths.js";

export const FACES = {
  fortknight: { id: "fortknight", label: "FortKnight", logo: "🏰🛡️", favicon: "🗡️", theme: "fort-knight", home: "fortknight/", blurb: "the repeating 14-day schedule: your fortnight grid, day pages, and time by category" },
};
export const FACE_IDS = Object.keys(FACES);
/** The face's menu: Overview, Keep, three of Name Drop's stones, Achievements.
 *
 *  WARNING — three of these pills 404 today. Fork Knife, Fresh Keep and Folk Knowledge have no page
 *  until beinsiculous/insiculous_web#18, #19 and #20 land (the *Eight Stones, Eight Pages* sprint).
 *  Nothing catches it: postbuild-check.mjs has no link checker, and a11y-check.mjs and
 *  screenshot-pages.mjs both walk dist/, where a route that does not exist simply is not. So
 *  **dev → main is held until those three pages exist** — shipping this nav to production would put
 *  dead links in FortKnight's primary navigation on every face page.
 *
 *  Six is itself interim: Name Drop's eight stones mean Fix Knitt, Foe Kiss, Fun Knee and Fret Knot
 *  join later (#23), making ten pills.
 *
 *  `shortLabel` is kept per entry but currently shown nowhere: the phone-width swap to the short
 *  label is dead CSS on this branch — at that width the pills live inside the ☰ panel, which is full
 *  width and has room for the full label (faces.css's mobile block explains). */
export function faceNav() {
  return [
    { path: "", label: "Overview", shortLabel: "Menu", exact: true },
    { path: "keep/", label: "Keep", shortLabel: "Keep", exact: false },
    { path: "forkknife/", label: "Fork Knife", shortLabel: "Meals", exact: false },
    { path: "freshkeep/", label: "Fresh Keep", shortLabel: "Clean", exact: false },
    { path: "folkknowledge/", label: "Folk Knowledge", shortLabel: "Folk", exact: false },
    { path: "achievements/", label: "Achievements", shortLabel: "Won", exact: false },
  ];
}
/** URL of a page inside a face (path without a leading slash, with a trailing slash for pages). */
export function facePath(faceId, path = "") {
  return withBase(`${FACES[faceId].home}${path}`);
}
/** The shared Profile page. It belongs to the studio, not to the face, so it is a BaseLayout page like the rest
 *  of beinsiculous.com; the face only links to it. */
export const PROFILE_PATH = "profile/";
/** The studio site (beinsiculous.com itself) that the face sits inside: its label and its logo (an emoji, like
 *  the face's), worn by the face-switcher's way back out. */
export const STUDIO = { label: "Be Insiculous", logo: "💧" };
/** URL of the studio home. */
export function studioPath() {
  return withBase("");
}
