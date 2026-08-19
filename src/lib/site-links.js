// Where the site's "buy me a coffee" links point. One constant, three consumers across the two
// layouts: src/components/SupportLink.astro (the devlog's end-of-post block),
// src/pages/devlog/index.astro (the ☕ beside the listing's h1) and src/layouts/FaceLayout.astro
// (the ☕ in the face switcher). Change the handle here and every entry point follows.
//
// Ko-fi rather than Buy Me a Coffee: the same one-off "coffee" gesture, givers need no account,
// and it takes 0% of a donation against BMC's 5%. A plain link, never their <script> widget —
// the site ships no third-party runtime resources, and their markup would sit outside the axe
// gate that blocks the deploy (scripts/a11y-check.mjs).
export const KOFI_URL = "https://ko-fi.com/beinsiculous";

// Every entry point opens in a new tab, so a reader mid-post keeps their place. `noopener` is
// load-bearing here (a new browsing context would otherwise hand Ko-fi a window.opener handle);
// on a same-tab link it would have been decorative. These are the only target/rel in src/, so
// each link also announces the new tab rather than springing it silently.
export const KOFI_LABEL = "Buy me a coffee (opens in a new tab)";
export const KOFI_TITLE = "Buy me a coffee — support Be Insiculous";
