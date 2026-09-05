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

// The two people who write here. An agent never adds, edits or comments on a devlog post.
const devlogAuthor = z.enum(['Jesse', 'M']);

const devlog = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/devlog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    // Required, and rendered as written: the byline is the value.
    author: devlogAuthor,
    tags: z.array(z.string()).default([]),
    // Held back from the site: no listing entry, no page of its own, no feed item — the rule lives
    // in src/lib/devlog-posts.js and every query goes through it. Releasing a held post is dropping
    // this line (the date stays the day it was written).
    draft: z.boolean().default(false),
    // Validated reference: the build fails if this doesn't match a games entry id.
    game: reference('games').optional(),
  })
  // Strict: a field the site no longer reads (the old `comments:`) or a misspelt one (`pubdate:`)
  // fails the build instead of being stripped and silently not rendered.
  .strict(),
});

export const collections = { games, devlog };
