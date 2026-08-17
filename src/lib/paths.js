// URL helper that respects the configured deploy base path (ASTRO_BASE).
// import.meta.env.BASE_URL always ends with "/"; pass paths without a leading slash.
export function withBase(path) {
  return `${import.meta.env.BASE_URL}${path}`;
}
