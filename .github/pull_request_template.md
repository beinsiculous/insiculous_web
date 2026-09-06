## What changed

<!-- a sentence or two -->

## Checks

- [ ] `npm run verify` passes (type-check + build + postbuild + axe accessibility audit + announce audit + the layout gate: every page answers 200, none scrolls sideways, 125% text and reflow included)

<!-- If you touched a layout, a component, styles, or anything interactive, also: -->
- [ ] Keyboard-only walkthrough of the changed pages (Tab / Shift-Tab / Enter / Escape; focus always visible)
- [ ] Screen-reader pass: `npm run verify`'s announce gate is green on every page (landmarks, one h1 with no skipped levels, every control and region named) — and, for a **new** interaction, one VoiceOver or NVDA listen of it, named here
- [ ] Reflow: `npm run verify`'s reflow pass is green (no sideways scroll at 320 CSS px, WCAG 1.4.10); a look at 200% text size on a phone for clipped text is still yours
- [ ] New images have meaningful `alt` (or explicit `alt=""` if decorative); new form fields have labels
