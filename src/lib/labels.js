// Category labels shared by every page (build-time and client-side).
import bundle from "../../build/fortknight.bundle.json";

export function categoryLabel(categoryKey) {
  if (categoryKey === "flexible") return "Flexible";
  return bundle.categories.categories[categoryKey]?.label ?? categoryKey;
}
