// Is this a My Fort seed this page can render?
//
// The file is exported by the Focus Key app and picked by the person who owns it. It is the only document this
// site reads that carries somebody's real schedule, so the rules here are about being useful rather than
// being strict: what a page can draw, it draws.
//
// TOLERANT WITHIN A MAJOR VERSION, on purpose. The two halves of this feature ship on different cadences —
// Focus Key at native-rebuild speed, this page at push speed — and the person holding the phone cannot redeploy
// the website. So an unknown field is ignored rather than refused, and `version` is refused only when it is
// higher than this page understands. Focus Key's side of that bargain is in src/lib/myfort-seed.js: the version
// bumps only for a breaking change.
//
// Reasons are written for a person standing at a television, not for a log.

/** The highest `meta.version` this page knows how to draw. */
export const READABLE_VERSION = 1;

/** A day needs a key and a name before it can be a panel; everything else on it degrades to nothing. */
function looksLikeDay(day) {
  return Boolean(day) && typeof day === "object"
    && typeof day.dayKey === "string" && day.dayKey.length > 0;
}

/** {ok: true, seed} or {ok: false, reason}. Never throws: the boot path calls this on whatever was left in
 *  localStorage, which may be half a document written by a browser that ran out of room. */
export function validateMyFortSeed(candidate) {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
    return { ok: false, reason: "That file is not a My Fort seed." };
  }
  const meta = candidate.meta;
  if (!meta || typeof meta !== "object" || meta.format !== "myfort") {
    // The likeliest wrong file by far is a whole keep_seed.json, which is the app's own data and far bigger.
    const hint = candidate.calendar && candidate.tasks
      ? " That looks like Focus Key's own seed — My Fort needs the smaller file the app exports for the web."
      : "";
    return { ok: false, reason: `That file is not a My Fort seed.${hint}` };
  }
  const version = meta.version;
  if (typeof version !== "number" || !Number.isFinite(version)) {
    return { ok: false, reason: "That seed does not say which format it is, so this page cannot read it." };
  }
  if (version > READABLE_VERSION) {
    return {
      ok: false,
      // Naming the remedy matters: the fix is on the website, which the person holding the phone cannot
      // deploy. Telling them to re-export would send them round a loop that cannot help.
      reason: `That seed is newer than this page understands (format ${version}; this page reads ${READABLE_VERSION}). The website needs updating — the file is fine.`,
    };
  }
  if (!Array.isArray(candidate.days) || !candidate.days.some(looksLikeDay)) {
    return { ok: false, reason: "That seed has no days in it, so there is no fortnight to show." };
  }
  return { ok: true, seed: candidate };
}

/** The days worth drawing, in the order the file gives them. A day without a key cannot be a panel; the
 *  rest of a sparse day is the page's problem and it renders what is there. */
export function readableDays(seed) {
  return (seed?.days ?? []).filter(looksLikeDay);
}

/** How stale the season and the wheel are. The fourteen days carry no dates and never go off; `season` and
 *  `year` are snapshots of the moment the file was exported, so this is the one thing the page says about
 *  age — and it says it in days, never by resolving a date, because nothing here evaluates a calendar. */
export function describeExportAge(seed, todayIsoDate) {
  const exportedAt = seed?.meta?.exportedAt;
  if (typeof exportedAt !== "string" || typeof todayIsoDate !== "string") return null;
  const exportedDay = exportedAt.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(exportedDay) || !/^\d{4}-\d{2}-\d{2}$/.test(todayIsoDate)) return null;
  if (exportedDay >= todayIsoDate) return { exportedDay, stale: false };
  // Only whether it is old, not how old: a day count is date arithmetic, and this page does none.
  return { exportedDay, stale: exportedDay < todayIsoDate };
}
