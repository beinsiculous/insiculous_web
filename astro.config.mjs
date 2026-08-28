// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  // The custom domain; wrangler.toml routes it at the Worker. Canonical URLs and sitemaps
  // are built from this, so it must be the address visitors actually use.
  site: 'https://beinsiculous.com',
  integrations: [
    // The planner face is an on-device app whose prerendered HTML is an empty no-JS shell —
    // keep it out of the sitemap so crawlers see only real content.
    sitemap({
      filter: (page) => !/\/(fortknight|profile)\//.test(page),
    }),
  ],
});
