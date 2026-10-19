// The redirect rules of the build gate, used by scripts/postbuild-check.mjs (check 9) over
// dist/_redirects. tests/test_postbuild_check.py drives this module directly, so a missing rename
// line or a dead destination stays a failure here rather than surfacing as a visitor's 404.
//
// The file is Cloudflare's static-assets grammar: one rule per line, `[source] [destination]
// [code]`, blank lines and `#` comment lines ignored. A renamed game (an entry whose frontmatter
// carries `formerSlug`) owes exact lines — its former page path, and its former playground path when
// it has an editor bundle, each with and without the trailing slash — and never a splat under the
// former slug, which would also redirect the editor bundle the new playground page still loads from
// under the former slug.

/**
 * The rules a renamed game owes, each sending a former path to the page under the new slug: two per
 * section it has a page in (`games` always; `playground` only when its entry carries `editor`,
 * because that is what builds the playground page).
 */
export function expectedRenameRules(slug, formerSlug, sections) {
  return sections.flatMap((section) => [
    { source: `/${section}/${formerSlug}/`, destination: `/${section}/${slug}/` },
    { source: `/${section}/${formerSlug}`, destination: `/${section}/${slug}/` },
  ]);
}

/**
 * _redirects text → { rules: [{lineNumber, source, destination, code}], malformed: [{lineNumber,
 * line}] }. `code` is the third field as written, or null when the line leaves it out.
 */
export function parseRedirects(text) {
  const rules = [];
  const malformed = [];
  text.split('\n').forEach((rawLine, index) => {
    const line = rawLine.trim();
    if (line === '' || line.startsWith('#')) return;
    const fields = line.split(/\s+/);
    if (fields.length < 2 || fields.length > 3) {
      malformed.push({ lineNumber: index + 1, line });
      return;
    }
    const [source, destination, code = null] = fields;
    rules.push({ lineNumber: index + 1, source, destination, code });
  });
  return { rules, malformed };
}

/**
 * The dist/-relative file a destination must resolve to: a page written in its trailing-slash form
 * resolves to its index.html, anything else to a file at that path. Null for a destination that
 * is not a site path (an external URL cannot be checked against dist/).
 */
export function destinationFile(destination) {
  if (!destination.startsWith('/') || destination.startsWith('//')) return null;
  const relative = destination.replace(/^\//, '');
  return destination.endsWith('/') ? `${relative}index.html` : relative;
}

/**
 * Every problem with a _redirects file, as messages: a malformed line, a source listed twice (the
 * first match wins at the edge, so the second is dead), a destination that does not resolve
 * (`isFile` answers for a dist/-relative path), and for each renamed game a missing line, a line
 * pointing elsewhere, a line with any code but `expectedCode`, or a splat or placeholder source
 * under its former slug — the edge would then redirect the editor bundle and the old version
 * directories that still live under that slug.
 */
export function findRedirectProblems({ text, renamedGames, expectedCode, isFile }) {
  const problems = [];
  const { rules, malformed } = parseRedirects(text);
  for (const { lineNumber, line } of malformed) {
    problems.push(`line ${lineNumber} is not "[source] [destination] [code]": ${line}`);
  }

  const rulesBySource = new Map();
  for (const rule of rules) {
    const earlier = rulesBySource.get(rule.source);
    if (earlier) {
      problems.push(`line ${rule.lineNumber} repeats the source ${rule.source} of line ${earlier.lineNumber}`);
      continue;
    }
    rulesBySource.set(rule.source, rule);
    const target = destinationFile(rule.destination);
    if (target === null || !isFile(target)) {
      problems.push(`line ${rule.lineNumber}: ${rule.source} redirects to ${rule.destination}, which has no page or file in dist/`);
    }
  }

  for (const { entry, slug, formerSlug, sections } of renamedGames) {
    for (const rule of rules) {
      // Under the former slug: the path itself, a path below it, or the slug followed straight by
      // a wildcard or placeholder (`/games/old*` covers the slug's whole subtree at the edge too).
      const underFormerSlug = ['games', 'playground'].some((section) => {
        const prefix = `/${section}/${formerSlug}`;
        return rule.source.startsWith(prefix) && /^(|[/*:].*)$/.test(rule.source.slice(prefix.length));
      });
      if (underFormerSlug && /[*:]/.test(rule.source)) {
        problems.push(`${entry}: line ${rule.lineNumber} is a splat under the former slug '${formerSlug}', which would redirect its editor bundle and old version directories`);
      }
    }
    for (const expected of expectedRenameRules(slug, formerSlug, sections)) {
      const rule = rulesBySource.get(expected.source);
      const wanted = `${expected.source} ${expected.destination} ${expectedCode}`;
      if (!rule) {
        problems.push(`${entry}: formerSlug '${formerSlug}' needs the line "${wanted}"`);
      } else if (rule.destination !== expected.destination || rule.code !== String(expectedCode)) {
        problems.push(`${entry}: line ${rule.lineNumber} should read "${wanted}"`);
      }
    }
  }
  return problems;
}
