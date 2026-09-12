// Prose rules over built HTML, used by scripts/postbuild-check.mjs (rules 5 and 6) on every page.
// tests/test_postbuild_check.py drives this module directly, so the rules and their exclusions stay
// pinned rather than being loosened the first time one cries wolf.
//
// findGluedBoundaries — a word run into an inline tag: "it is a <a>proving ground</a>" shipping as
// "it is a<a>proving ground</a>". Astro drops the newline + indentation between a word and an inline
// tag that sit on different lines of the .astro source, so a paragraph that reads correctly in the
// editor can lose a space in dist/. Whitespace on the *same* line always survives: the fix is to
// keep the tag on the same line as the word beside it.
//
// findStraightApostrophes — a straight ' where the site's prose uses curly ’. Markdown content gets
// curly quotes from Astro's smartypants, so without this the .astro pages drift the other way and
// the two sit side by side on the same page looking different. Limitation: this sees rendered HTML
// only, so a straight apostrophe inside a client-rendered JS string is beyond it.

const INLINE_TAGS = 'a|strong|em|code|b|i|abbr|kbd|small|span';

// A word character right after a closing inline tag. Deliberately narrow: punctuation after a link
// is normal typography ("</a>," "</em>."), a letter is not.
const AFTER_CLOSE = new RegExp(`</(?:${INLINE_TAGS})>(?=[A-Za-z0-9(])`, 'g');

// A word or sentence-punctuation character right before an opening inline tag. `!` and `?` are in
// the class because "really!<em>wow</em>" is the same bug; `;` is here for "word;<a>" but costs an
// entity guard below, since every HTML entity also ends in `;`.
const BEFORE_OPEN = new RegExp(`[A-Za-z0-9,.:;!?)](?=<(?:${INLINE_TAGS})[ >])`, 'g');

const TRAILING_ENTITY = /&[a-zA-Z#][a-zA-Z0-9]*;$/;

/** Remove script/style bodies and HTML comments — their contents are not prose. */
function stripNonProse(html) {
  return html
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/g, '')
    .replace(/<!--[\s\S]*?-->/g, '');
}

/**
 * Markup that is glued on purpose, not by a lost line break:
 * the aria-hidden wordmark cursor, visually-hidden screen-reader text, and empty elements.
 */
function isDeliberate(openingTag, content) {
  if (/\baria-hidden="true"/.test(openingTag)) return true;
  const classNames = openingTag.match(/\bclass="([^"]*)"/);
  if (classNames && classNames[1].includes('visually-hidden')) return true;
  return content.trim() === '';
}

/** The opening tag and content of the element starting at `index`. */
function elementAt(text, index) {
  const tagName = text.slice(index).match(/^<([a-zA-Z]+)/)?.[1];
  if (!tagName) return null;
  const end = text.indexOf('>', index);
  if (end === -1) return null;
  const openingTag = text.slice(index, end + 1);
  const closeIndex = text.indexOf(`</${tagName}>`, end);
  const content = closeIndex === -1 ? '' : text.slice(end + 1, closeIndex);
  return { openingTag, content };
}

/** The opening tag and content of the element whose closing tag sits at `index`. */
function elementEndingAt(text, index) {
  const tagName = text.slice(index).match(/^<\/([a-zA-Z]+)>/)?.[1];
  if (!tagName) return null;
  const openIndex = text.lastIndexOf(`<${tagName}`, index);
  if (openIndex === -1) return null;
  const end = text.indexOf('>', openIndex);
  if (end === -1 || end > index) return null;
  return { openingTag: text.slice(openIndex, end + 1), content: text.slice(end + 1, index) };
}

/**
 * Every place a word runs into an inline tag. Returns [{ kind, snippet }]; empty means clean.
 * `kind` is "after-close" or "before-open".
 */
export function findGluedBoundaries(html) {
  const text = stripNonProse(html);
  const boundaries = [];

  for (const match of text.matchAll(AFTER_CLOSE)) {
    const element = elementEndingAt(text, match.index);
    if (element && isDeliberate(element.openingTag, element.content)) continue;
    boundaries.push({ kind: 'after-close', snippet: snippetAround(text, match.index, match[0].length) });
  }

  for (const match of text.matchAll(BEFORE_OPEN)) {
    // "&hellip;<a>" is an entity, not a word glued to a tag — the `;` in the class would catch it.
    if (TRAILING_ENTITY.test(text.slice(Math.max(0, match.index - 12), match.index + 1))) continue;
    const element = elementAt(text, match.index + 1);
    if (element && isDeliberate(element.openingTag, element.content)) continue;
    boundaries.push({ kind: 'before-open', snippet: snippetAround(text, match.index, 1) });
  }

  return boundaries;
}

function snippetAround(text, index, length) {
  return text.slice(Math.max(0, index - 45), index + length + 45).replace(/\s+/g, ' ');
}

/** Straight apostrophes in rendered prose (tags and their attributes removed).
 *
 *  `&#39;` counts. Prose that reaches the page through an Astro prop or expression is HTML-escaped on
 *  the way out, so `The fortnight's meals` ships as `The fortnight&#39;s meals` — a straight apostrophe
 *  to every reader, and invisible to a check that only looks for the character itself. That is how five
 *  stone pages passed this gate on 2026-08-31 while showing exactly what it exists to forbid. */
export function findStraightApostrophes(html) {
  const text = stripNonProse(html).replace(/<[^>]+>/g, ' ').replace(/&#0*39;|&#x0*27;|&apos;/gi, "'");
  return [...text.matchAll(/\w'\w/g)].map((match) => ({
    snippet: snippetAround(text, match.index, match[0].length),
  }));
}
