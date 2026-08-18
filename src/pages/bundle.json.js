// The built data bundle at /bundle.json, for the pages that fetch it on the client (the date
// resolver, the assistant pages, /profile/). It is the same module the static pages import at build
// time — serving it from here rather than a copy under public/ means there is one bundle in the
// repository and the served file can never drift from the rendered one.
import bundle from "../../build/fortknight.bundle.json";

export const GET = () =>
  new Response(JSON.stringify(bundle), { headers: { "content-type": "application/json" } });
