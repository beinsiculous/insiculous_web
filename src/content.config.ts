import { defineCollection, reference, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Slugs come from the entry `id`, which the glob loader derives from the
// filename (base + extension stripped): src/content/games/my-game.md -> "my-game".

const games = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/games' }),
  schema: z
    .object({
      title: z.string(),
      blurb: z.string(),
      // 'playable' = runs in the browser on this site (requires wasm).
      // 'alpha' = full gameplay loop on desktop, still getting polish.
      status: z.enum(['playable', 'alpha', 'in-development', 'prototype']),
      // Path to the wasm-bindgen JS glue under public/, e.g. "/games/my-game/v1/game.js".
      // Must be absolute (leading slash). Bump the version folder (v1 -> v2)
      // on every update instead of overwriting in place.
      wasm: z.string().startsWith('/').optional(),
      // Canvas pixel size for the playable embed — must match the game's
      // native window size. Omit for the 800x600 default.
      width: z.number().int().positive().optional(),
      height: z.number().int().positive().optional(),
      screenshots: z.array(z.string().startsWith('/')).default([]),
      order: z.number().default(0),
    })
    .refine((game) => game.status !== 'playable' || game.wasm !== undefined, {
      message: "status 'playable' requires a wasm path — a playable game must have a build to play",
      path: ['wasm'],
    }),
});

const devlog = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/devlog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    tags: z.array(z.string()).default([]),
    // Validated reference: the build fails if this doesn't match a games entry id.
    game: reference('games').optional(),
  }),
});

export const collections = { games, devlog };
