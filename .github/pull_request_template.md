## What changed

<!-- a sentence or two -->

## Checks

- [ ] `npm run verify` passes (type-check + build + postbuild + axe accessibility audit)

<!-- If you touched a layout, a component, styles, or anything interactive, also: -->
- [ ] Keyboard-only walkthrough of the changed pages (Tab / Shift-Tab / Enter / Escape; focus always visible)
- [ ] Screen-reader pass (VoiceOver or NVDA) on the changed pages: landmarks, headings, control names all announced
- [ ] 200% browser zoom at 320–390px wide: no sideways scroll, no clipped text (`LARGE_TEXT=1 node scripts/screenshot-pages.mjs` checks 125% site text automatically)
- [ ] New images have meaningful `alt` (or explicit `alt=""` if decorative); new form fields have labels
