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
/** The face’s menu: Overview, Keep, the seven stones each carrying its category, Achievements.
 *  The bar shows the stored keep’s focus stones by category and the rest sit behind Peripheral, all
 *  seven with no keep.
 *
 *  Every entry has a page — postbuild check 7 gates it, added after three entries 404ed when the nav
 *  ran ahead of its routes. If you add an entry here before its route exists, check 7 will fail the
 *  build.
 *
 *  Fort Knight itself has no entry. It is the agenda stone, and the agenda is what the Overview, Keep
 *  and the day pages already are — an entry for it would point at the page you are on. */
export function faceNav() {
  return [
    { path: "", label: "Overview", exact: true },
    { path: "keep/", label: "Keep", exact: false },
    { path: "forkknife/", label: "Fork Knife", category: { key: "meals", label: "Meals" }, exact: false },
    { path: "freshkeep/", label: "Fresh Keep", category: { key: "cleaning", label: "Cleaning" }, exact: false },
    { path: "folkknowledge/", label: "Folk Knowledge", category: { key: "friends-family", label: "Friends & Family" }, exact: false },
    { path: "fixknitt/", label: "Fix Knitt", category: { key: "operations", label: "Operations" }, exact: false },
    { path: "foekiss/", label: "Foe Kiss", category: { key: "spirituality-development", label: "Spirituality & Development" }, exact: false },
    { path: "funknee/", label: "Fun Knee", category: { key: "health", label: "Health" }, exact: false },
    { path: "fretknot/", label: "Fret Knot", category: { key: "working", label: "Working" }, exact: false },
    { path: "achievements/", label: "Achievements", exact: false },
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
