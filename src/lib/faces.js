// The site's planner face (docs/app.md): FortKnight (the fortnight schedule and its menu), with its own
// Overview / building page / Questionnaire / Assistant pages under /fortknight/; it shares the profile
// (/profile/) and the on-device settings with the studio site. The face carries its own `theme` (the skin in
// public/app/shared/themes.css). The studio pages of beinsiculous.com — including /profile/ — use their own
// layout entirely (src/layouts/BaseLayout.astro).
import { withBase } from "./paths.js";

// `build` is the face's own page for adding things by hand — FortKnight's Build (the menu plus the commitments
// and tasks).
export const FACES = {
  fortknight: { id: "fortknight", label: "FortKnight", logo: "🏰🛡️", favicon: "🗡️", theme: "fort-knight", home: "fortknight/", blurb: "the repeating 14-day schedule: your fortnight grid, day pages, and time by category", build: { path: "build/", label: "Build", shortLabel: "Build" } },
};
export const FACE_IDS = Object.keys(FACES);
/** The face's menu: Overview, My Fort, Achievements, its own building page, Questionnaire,
 *  Assistant. `shortLabel` is kept per entry but currently shown nowhere: the phone-width swap to
 *  the short label is dead CSS on this branch — at that width the pills live inside the ☰ panel,
 *  which is full width and has room for the full label (faces.css's mobile block explains). */
export function faceNav(faceId) {
  return [
    { path: "", label: "Overview", shortLabel: "Menu", exact: true },
    { path: "myfort/", label: "My Fort", shortLabel: "Fort", exact: false },
    { path: "achievements/", label: "Achievements", shortLabel: "Won", exact: false },
    { ...FACES[faceId].build, exact: false },
    { path: "questionnaire/", label: "Questionnaire", shortLabel: "Quiz", exact: false },
    { path: "assistant/", label: "Assistant", shortLabel: "AI", exact: false },
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
