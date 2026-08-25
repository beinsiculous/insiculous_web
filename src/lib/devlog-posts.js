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
 * Generic in the entry so the collection's own type survives the filter — the post route passes
 * what comes back straight into the page's props, and a narrowed type breaks `astro check`.
 *
 * @template {{data: {pubDate: Date, draft?: boolean}}} Entry
 * @param {Entry[]} entries  collection entries as Astro loads them
 * @returns {Entry[]}
 */
export function publishedPosts(entries) {
  return entries
    .filter((entry) => !entry.data.draft)
    .sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
}
