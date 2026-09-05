/**
 * Which devlog posts the site shows, and in what order.
 *
 * Four places ask for the devlog — the listing, the post route, the RSS feed and a game's related
 * posts — and a post held back has to disappear from all four at once. A partial hide is worse
 * than none: the listing would still link a page that was never built, and nothing here
 * link-checks the build, so it would ship as a silent 404. Hence one function, four callers.
 *
 * Framework-free plain ES module (see CLAUDE.md), in the style of devlog-status.js: no imports,
 * no build step, driven directly by tests/test_devlog_posts.py through node.
 */

/**
 * The posts the site shows, newest first. A post with `draft: true` is held back: no listing
 * entry, no page of its own, no feed item. The file stays in src/content/devlog/ with its author
 * and comments intact, so releasing it is one line of frontmatter.
 *
 * A publication date or comment date in the future relative to `now` throws — a typo'd date must
 * fail the build rather than pinning a badge into the future. A comment dated before the post’s
 * pubDate also throws: a comment cannot predate what it comments on. Drafts are exempt: a draft
 * builds nothing, so a future date on one is harmless.
 *
 * Generic in the entry so the collection's own type survives the filter — the post route passes
 * what comes back straight into the page's props, and a narrowed type breaks `astro check`.
 *
 * @template {{id: string, data: {pubDate: Date|string, draft?: boolean, comments?: Array<{author?: string, date: Date|string}>}}} Entry
 * @param {Entry[]} entries  collection entries as Astro loads them
 * @param {Date|string} now  the clock to check against
 * @returns {Entry[]}
 */
export function publishedPosts(entries, now) {
  if (now === undefined || now === null) {
    throw new Error('publishedPosts requires a clock (now)');
  }
  const nowDate = now instanceof Date ? now : new Date(now);
  if (Number.isNaN(nowDate.valueOf())) {
    throw new Error(`not a date: ${String(now)}`);
  }

  const published = entries.filter((entry) => !entry.data.draft);

  for (const entry of published) {
    const pubDate = entry.data.pubDate instanceof Date ? entry.data.pubDate : new Date(entry.data.pubDate);
    if (pubDate.valueOf() > nowDate.valueOf()) {
      throw new Error(
        `devlog post '${entry.id}' pubDate (${pubDate.toISOString().slice(0, 10)}) is in the future relative to ${nowDate.toISOString().slice(0, 10)}`
      );
    }
    const comments = entry.data.comments ?? [];
    for (const comment of comments) {
      const commentDate = comment.date instanceof Date ? comment.date : new Date(comment.date);
      if (commentDate.valueOf() > nowDate.valueOf()) {
        throw new Error(
          `devlog post '${entry.id}' comment date (${commentDate.toISOString().slice(0, 10)}) is in the future relative to ${nowDate.toISOString().slice(0, 10)}`
        );
      }
      if (commentDate.valueOf() < pubDate.valueOf()) {
        throw new Error(
          `devlog post '${entry.id}' comment date (${commentDate.toISOString().slice(0, 10)}) is before the post’s pubDate (${pubDate.toISOString().slice(0, 10)})`
        );
      }
    }
  }

  return published.sort((a, b) => new Date(b.data.pubDate).valueOf() - new Date(a.data.pubDate).valueOf());
}
