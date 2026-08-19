// The devlog as an RSS feed at /rss.xml. Plain endpoint in the style of bundle.json.js —
// the studio site has no UI framework, and this needs none either.
import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const posts = (await getCollection('devlog')).sort(
    (a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf()
  );
  return rss({
    title: 'Be Insiculous devlog',
    description: 'Development notes on games and the Insiculous 2D engine.',
    site: context.site,
    xmlns: { atom: 'http://www.w3.org/2005/Atom' },
    customData:
      '<language>en</language>' +
      `<atom:link href="${new URL('/rss.xml', context.site)}" rel="self" type="application/rss+xml"/>`,
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.pubDate,
      link: `/devlog/${post.id}/`,
    })),
  });
}
