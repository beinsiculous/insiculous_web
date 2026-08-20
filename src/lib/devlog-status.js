/**
 * Devlog comment status — the NEW / OLD badge rules for src/pages/devlog/.
 *
 * Every devlog post is written by one of four authors: the two coding agents (Claude, Kimi) and
 * the two developers (Jesse, M). A post is not finished when it is published — it is finished when
 * the people who owe it a comment have left one. The badge is the nag, and it clears itself:
 *
 *   agent-written post   -> needs a comment from BOTH developers
 *   developer-written post -> needs a comment from the OTHER developer (agent comments are welcome
 *                             extras and never gate the badge)
 *
 *   still waiting, within 14 days of the anchor date  -> "NEW", in the author's colour
 *   still waiting, more than 14 days                  -> "OLD", in the author's colour
 *   every needed comment in, within 14 days           -> "NEW" as bare green text, no tag
 *   every needed comment in, more than 14 days        -> no badge at all
 *
 * The anchor date is the publication date until the post is fully commented, and then the date of
 * the comment that completed it — so landing the last needed comment restarts the 14-day countdown.
 *
 * Framework-free plain ES module (see CLAUDE.md): no imports, no build step, driven directly by
 * tests/test_devlog_status.py through node and imported by the .astro pages at build time.
 */

/** How long a post counts as fresh, in days, measured from its anchor date. */
export const FRESH_DAYS = 14;

export const DEVELOPERS = ['jesse', 'm'];
export const AGENTS = ['claude', 'kimi'];
export const AUTHORS = [...AGENTS, ...DEVELOPERS];

export const AUTHOR_LABELS = { claude: 'Claude', kimi: 'Kimi', jesse: 'Jesse', m: 'M' };

const MILLISECONDS_PER_DAY = 86400000;

/**
 * Who owes this post a comment before it can go green.
 * An agent post needs both developers; a developer post needs the other developer.
 */
export function requiredCommenters(author) {
  if (DEVELOPERS.includes(author)) return DEVELOPERS.filter((developer) => developer !== author);
  return [...DEVELOPERS];
}

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
 * @returns {{label: 'NEW'|'OLD'|null, tone: string|null, author: string, awaiting: string[],
 *            awaitingNames: string, complete: boolean, ageDays: number, description: string}}
 */
export function statusFor(post, now) {
  const author = post.author;
  if (!AUTHORS.includes(author)) throw new Error(`unknown devlog author: ${String(author)}`);

  const comments = post.comments ?? [];
  const required = requiredCommenters(author);

  // The first comment from each person who owes one; the last of those completes the post.
  const firstCommentDays = required.map((commenter) => {
    const theirs = comments.filter((comment) => comment.author === commenter).map((comment) => dayNumber(comment.date));
    return theirs.length ? Math.min(...theirs) : null;
  });
  const complete = firstCommentDays.every((day) => day !== null);
  const awaiting = required.filter((_, index) => firstCommentDays[index] === null);

  const publishedDay = dayNumber(post.pubDate);
  // A comment can only ever push the countdown forward, never behind the publication date.
  const anchorDay = complete ? Math.max(publishedDay, Math.max(...firstCommentDays)) : publishedDay;
  const ageDays = dayNumber(now) - anchorDay;
  const fresh = ageDays <= FRESH_DAYS;

  const names = (people) => people.map((person) => AUTHOR_LABELS[person]).join(' and ');

  if (complete) {
    return {
      label: fresh ? 'NEW' : null,
      tone: fresh ? 'complete' : null,
      author,
      awaiting: [],
      awaitingNames: '',
      complete: true,
      ageDays,
      description: fresh ? `commented on by ${names(required)}` : '',
    };
  }

  return {
    label: fresh ? 'NEW' : 'OLD',
    tone: DEVELOPERS.includes(author) ? 'developer' : author,
    author,
    awaiting,
    // Pre-joined for the pages, so no caller has to reach back into AUTHOR_LABELS to say it.
    awaitingNames: names(awaiting),
    complete: false,
    ageDays,
    description: `${AUTHOR_LABELS[author]}’s post, still waiting on a comment from ${names(awaiting)}`,
  };
}
