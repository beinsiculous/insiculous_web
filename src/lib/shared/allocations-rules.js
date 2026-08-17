// Time per category from a person's weights (the app's counterpart of scripts/fk_core/allocations.py, which
// measures a data set). Pure; canonical module (app/shared/), synced into the Astro app for /allocations/.
import { FLEXIBLE_FOCUS } from "./fortknight-rules.js";

/** Shares of a totals map, 4 decimals (0 everywhere when the total is 0) — mirror of fk_core.allocations._shares. */
export function shares(totals) {
  const grandTotal = Object.values(totals).reduce((sum, value) => sum + value, 0);
  return Object.fromEntries(Object.entries(totals).map(([key, value]) => [key, grandTotal ? Math.round((value / grandTotal) * 10000) / 10000 : 0]));
}

/** Each focus block gives its full duration to its focus (missing = flexible), per fortnight — mirror of
 *  fk_core.allocations.allocate_by_block_focus, generalised to a profile's own focus blocks. */
export function allocateByBlockFocus(blockFocusGrid, focusBlocks, categoryOrder, dayKeyOrder) {
  const byCategory = Object.fromEntries([...categoryOrder, FLEXIBLE_FOCUS].map((key) => [key, 0]));
  for (const dayKey of dayKeyOrder) {
    const dayGrid = blockFocusGrid?.[dayKey] || {};
    for (const block of focusBlocks) {
      const focus = dayGrid[block.key] ?? FLEXIBLE_FOCUS;
      if (!(focus in byCategory)) continue;
      byCategory[focus] += block.durationMinutes;
    }
  }
  return {
    method: "Each focus block of your day gives its full duration to the focus your grid gives it (your own or imported); blocks without one count as flexible.",
    byCategory,
    shareByCategory: shares(byCategory),
  };
}

/** The views /allocations/ shows for a profile: always "byWeights" (the shares the answers produced), plus
 *  "byBlockFocus" when the profile carries a block focus grid (its own or imported) and "byProposal" when it
 *  carries the generator's proposal (weights.proposal, docs/generator.md). */
export function allocationsFromWeights(weights, categoryOrder, dayKeyOrder) {
  const views = {};
  const weightsTotals = Object.fromEntries(categoryOrder.map((key) => [key, weights.categories?.[key]?.share ?? 0]));
  weightsTotals[FLEXIBLE_FOCUS] = weights.flexibleShare ?? 0;
  views.byWeights = {
    method: "Your weights: the share of the waking window each category should get, derived from your answers.",
    shareByCategory: shares(weightsTotals),
  };
  const grid = weights.blockFocusGrid || {};
  const hasGrid = Object.values(grid).some((dayGrid) => dayGrid && Object.keys(dayGrid).length);
  const focusBlocks = (weights.blocks || []).filter((block) => block.carriesFocus);
  if (hasGrid) {
    views.byBlockFocus = allocateByBlockFocus(grid, focusBlocks, categoryOrder, dayKeyOrder);
  }
  if (weights.proposal?.blockFocusGrid) {
    views.byProposal = {
      ...allocateByBlockFocus(weights.proposal.blockFocusGrid, focusBlocks, categoryOrder, dayKeyOrder),
      method: "The generator's proposed grid: each focus block gives its full duration to the focus proposed for it (Overview → Proposed grid).",
    };
  }
  return views;
}
