// The allocation bars (one row per category, per view) as DOM — shared by the
// Astro /allocations/ page (whose prerendered AllocationBars.astro is only the no-JS fallback).
export const VIEW_LABELS = { byWeights: "Weights", byBlockFocus: "Focus grid", byProposal: "Proposed grid", byActivities: "Activities" };

function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/** Replace `container`'s children with the bars of `views` ({viewKey: {method, shareByCategory}}). */
export function renderAllocationBars(container, views, categoryLabel) {
  container.replaceChildren();
  for (const [viewKey, view] of Object.entries(views)) {
    container.appendChild(element("div", "allocation-legend", `${VIEW_LABELS[viewKey] || viewKey} — ${view.method}`));
    for (const [categoryKey, share] of Object.entries(view.shareByCategory)) {
      const row = element("div", `allocation-row${share === 0 ? " zero" : ""}`);
      row.appendChild(element("span", null, categoryLabel(categoryKey)));
      const bar = element("div", "allocation-bar");
      const fill = element("span", `fill${categoryKey === "flexible" ? " flexible" : ""}`);
      fill.style.width = `${Math.round(share * 100)}%`;
      if (categoryKey !== "flexible") fill.style.background = `var(--${categoryKey})`;
      bar.appendChild(fill);
      bar.appendChild(element("span", "allocation-value", `${(share * 100).toFixed(1)}%`));
      row.appendChild(bar);
      container.appendChild(row);
    }
  }
}
