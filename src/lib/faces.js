// The site's two faces (docs/app.md): FortKnight (the fortnight schedule) and ForkKnife (the meal plan), each with
// its own Overview / building page / Questionnaire / Assistant pages under its own path; they share the profile
// (/profile/) and the on-device settings. `face` is null on the profile page, which falls back to DEFAULT_THEME.
// Each face carries its own `theme` (the skin in app/shared/themes.css) so the two read as different sites; the
// studio pages of beinsiculous.com are the third and use their own layout entirely.
import { withBase } from "./paths.js";

export const SITE_NAME = "beinsiculous";
// `build` is the face's own page for adding things by hand — ForkKnife's Spoon Feed (the fortnight menu) and
// FortKnight's Build (the menu plus the commitments and tasks); the label differs, the place in the menu does not.
export const FACES = {
  fortknight: { id: "fortknight", label: "FortKnight", logo: "🏰🛡️", favicon: "🗡️", theme: "fort-knight", home: "fortknight/", blurb: "the repeating 14-day schedule: your fortnight grid, day pages and time by category", build: { path: "build/", label: "Build", shortLabel: "Build" } },
  forkknife: { id: "forkknife", label: "ForkKnife", logo: "🍴", favicon: "🍴", theme: "fork-knife", home: "forkknife/", blurb: "the fortnight menu: your meals, the dishes for each day, and the prep and cooking tasks", build: { path: "spoon-feed/", label: "Spoon Feed", shortLabel: "Spoon" } },
};
export const FACE_IDS = Object.keys(FACES);
/** The face's menu: Overview, its own building page, Questionnaire, Assistant. `shortLabel` is what the phone bar
 *  shows instead of the full label, where four pills have to fit one no-wrap row. */
export function faceNav(faceId) {
  return [
    { path: "", label: "Overview", shortLabel: "Menu", exact: true },
    { ...FACES[faceId].build, exact: false },
    { path: "questionnaire/", label: "Questionnaire", shortLabel: "Quiz", exact: false },
    { path: "assistant/", label: "Assistant", shortLabel: "AI", exact: false },
  ];
}
/** URL of a page inside a face (path without a leading slash, with a trailing slash for pages). */
export function facePath(faceId, path = "") {
  return withBase(`${FACES[faceId].home}${path}`);
}
export const PROFILE_PATH = "profile/";
/** The skin and tab icon for pages with no face (the shared Profile page). */
export const DEFAULT_THEME = FACES.fortknight.theme;
export const DEFAULT_FAVICON = FACES.fortknight.favicon;
/** The studio site (beinsiculous.com itself) that the two faces sit inside: its label and its logo (an emoji, like the faces'). */
export const STUDIO = { label: "Be Insiculous", logo: "💧" };
/** URL of the studio home. */
export function studioPath() {
  return withBase("");
}
