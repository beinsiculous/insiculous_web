/**
 * Devlog comment status — the NEW / OLD badge rules for src/pages/devlog/.
 *
 * Every devlog post is written by one of five authors: the three coding agents (Claude, Kimi,
 * Gemini) and the two developers (Jesse, M). A post is not finished when it is published — it
 * is finished when one comment lands from anyone on the roster other than its author. The author’s
 * own comment never counts. The badge is the nag, and it clears itself:
 *
 *   still waiting, within 7 days of the anchor date  -> "NEW", in the author's colour
 *   still waiting, more than 7 days                  -> "OLD", in the author's colour
 *   commented on, within 7 days                      -> "NEW" as bare green text, no tag
 *   commented on, more than 7 days                   -> no badge at all
 *
 * The anchor date is the publication date until the post is commented on, and then the date of
 * the earliest comment from someone else — so landing a qualifying comment restarts the 7-day
 * countdown. A later comment from a different person does not restart it.
 *
 * Framework-free plain ES module (see CLAUDE.md): no imports, no build step, driven directly by
 * tests/test_devlog_status.py through node and imported by the .astro pages at build time.
 */

/** How long a post counts as fresh, in days, measured from its anchor date. */
export const FRESH_DAYS = 7;

export const DEVELOPERS = ['jesse', 'm'];
export const AGENTS = ['claude', 'kimi', 'gemini'];
export const AUTHORS = [...AGENTS, ...DEVELOPERS];

export const AUTHOR_LABELS = { claude: 'Claude', kimi: 'Kimi', gemini: 'Gemini', jesse: 'Jesse', m: 'M' };

const MILLISECONDS_PER_DAY = 86400000;

/** Whole days since the epoch, so ages come out as calendar days rather than elapsed hours. */
function dayNumber(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.valueOf())) throw new Error(`not a date: ${String(value)}`);
  return Math.floor(date.valueOf() / MILLISECONDS_PER_DAY);
}

/**
 * The badge for one post.
 *
 * @param {{author: string, pubDate: Date|string, comments?: Array<{author: string, date: Date|string}>}} post
 * @param {Date|string} now  the day the badge is being rendered on (build time in the site)
 * @returns {{label: 'NEW'|'OLD'|null, tone: string|null, author: string, complete: boolean,
 *            ageDays: number, description: string}}
 */
export function statusFor(post, now) {
  const author = post.author;
  if (!AUTHORS.includes(author)) throw new Error(`unknown devlog author: ${String(author)}`);

  const comments = post.comments ?? [];
  const qualifying = comments.filter((comment) => comment.author !== author && AUTHORS.includes(comment.author));

  let completingComment = null;
  if (qualifying.length > 0) {
    completingComment = qualifying.reduce((earliest, comment) => {
      if (!earliest) return comment;
      return dayNumber(comment.date) < dayNumber(earliest.date) ? comment : earliest;
    }, null);
  }
  const complete = completingComment !== null;

  const publishedDay = dayNumber(post.pubDate);
  // A comment can only ever push the countdown forward, never behind the publication date.
  const anchorDay = complete ? Math.max(publishedDay, dayNumber(completingComment.date)) : publishedDay;
  const ageDays = dayNumber(now) - anchorDay;
  const fresh = ageDays <= FRESH_DAYS;

  if (complete) {
    return {
      label: fresh ? 'NEW' : null,
      tone: fresh ? 'complete' : null,
      author,
      complete: true,
      ageDays,
      description: fresh ? `commented on by ${AUTHOR_LABELS[completingComment.author]}` : '',
    };
  }

  return {
    label: fresh ? 'NEW' : 'OLD',
    tone: DEVELOPERS.includes(author) ? 'developer' : author,
    author,
    complete: false,
    ageDays,
    description: `${AUTHOR_LABELS[author]}’s post, still waiting on its first comment from someone else`,
  };
}

/**
 * The posts whose badge still reads NEW on `now` — a devlog that has not gone quiet yet.
 *
 * Publishing on top of these is what src/pages/devlog/index.astro warns about: two NEW posts at
 * once means the older one loses its turn on the listing before anyone has commented on it.
 * Holding the newcomer with `draft: true` until this comes back with one entry is the way out.
 *
 * Generic in the post so the caller keeps its own type — the listing reads `title` off what comes
 * back to name the crowded posts, and a narrowed type breaks `astro check`.
 *
 * @template {{author: string, pubDate: Date|string, comments?: Array<object>}} Post
 * @param {Post[]} posts
 * @param {Date|string} now  the day the badges are being rendered on
 * @returns {Post[]}
 */
export function postsStillNew(posts, now) {
  return posts.filter((post) => statusFor(post, now).label === 'NEW');
}
