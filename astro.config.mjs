// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  // The custom domain; wrangler.toml routes it at the Worker. Canonical URLs and sitemaps
  // are built from this, so it must be the address visitors actually use.
  site: 'https://beinsiculous.com',
});
