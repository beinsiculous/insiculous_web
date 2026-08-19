// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  // The custom domain; wrangler.toml routes it at the Worker. Canonical URLs and sitemaps
  // are built from this, so it must be the address visitors actually use.
  site: 'https://beinsiculous.com',
  integrations: [
    // The planner faces are on-device apps whose prerendered HTML is an empty no-JS shell —
    // keep them out of the sitemap so crawlers see only real content.
    sitemap({
      filter: (page) => !/\/(fortknight|forkknife|profile)\//.test(page),
    }),
  ],
});
