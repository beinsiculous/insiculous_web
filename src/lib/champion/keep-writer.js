// The keep: a fortnight of the fort, narrow enough to hand to a web page. All files are keeps; this
// is the one the person carries.
//
// The WRITER of the web keep, built from a Champion's keep — the fort's complete, private file that this
// repository never holds (scripts/fk_core/no_schedules.py). scripts/export_keep.py drives it over a keep
// outside the checkout; the slab-upload builder (beinsiculous/insiculous_web#24) will drive it in the
// browser. Moved here from the Fort Knight phone app's src/lib/keep.js on 2026-09-02 (Operation MVP,
// working set docs/megaseed/mvp.md), so the writer lives beside the format it writes — docs/keep-format.md
// and data/schema/keep.schema.json — and beinsiculous.com/fortknight/keep draws what it builds.
//
// EVERYTHING IS PRE-JOINED, and that is the whole design. The page that reads this does lookups by day key
// and renders; it never resolves a date, walks a calendar, or joins a menu row to a block. So the resolver
// does not have to exist twice — the joins happen here, where the parity suite already covers them, and
// the file is the contract between the two. (The website has its own FortKnight date evaluator, and it
// disagrees with this app: it resolves Ostara and Fimbulsumar on sun-b and has no transition weeks. Running it
// over this data would be wrong for half the year. It never has to: nothing here needs evaluating.)
//
// NARROWER THAN THE CHAMPION KEEP IT COMES FROM, on purpose. No tasks, no check-offs, no 1095-row calendar, no
// cleaning areas. The household's chores do not travel to the web; what is being eaten and what is booked
// do. That is a privacy property, and tests/test_keep_writer.py asserts it rather than trusting this
// comment. (Operation Chore Chart, 2026-08-31, widens what travels — beinsiculous/fortknight#15 is
// where that lands; until it does, this is the line.)
//
// Pure, like everything else in src/lib/: the championKeep and the date come in as arguments, and no Date object
// is ever constructed. `exportedAt` is passed in for the same reason — the export script is the one
// place that touches a clock.
import {
  appointmentsFor, dayLabel, mealForBlock, mealNameForBlock, mealsForDayKey, resolveMenu, resolveSeasons, resolveYear,
  rowsForSeason, timedBlocks,
} from "./resolve.js";

/** The format this builder writes. Bumped ONLY for a breaking change — a reader that tolerates unknown
 *  fields can take an additive one without being redeployed, and the person holding the phone cannot
 *  redeploy the website. Adding a field is not a bump. */
export const KEEP_FORMAT_VERSION = 1;

/** Every appointment a day key holds, flattened across the keep's blocks into the order the day happens in.
 *
 *  Block order IS the sort. `estimatedStart` is when to start moving, so it routinely precedes its own
 *  block — six of the championKeep's fifteen appointments sit outside their block's clock range — and `too-dark`
 *  runs 18:00 to 08:00, so a 00:30 appointment sorts first as a string and belongs last in the day. Walking
 *  `championKeep.blocks`, which is in clock order, is what makes the list chronological, and it comes out matching
 *  what resolveDay's blocks flatten to. */
/** The day's appointments, minus the ones FortKnightSlab's Appointments sheet marks. The filter is HERE and not in
 *  resolve.js on purpose: appointmentsFor is the shared path for the Today and Keep screens, so
 *  filtering there would hide the appointment on the phone too. The phone shows everything; the
 *  keep — which goes to a public page — shows what is not marked. `omitFromKeep` itself never
 *  travels: the row is dropped, not flagged. */
function appointmentsForDayKey(championKeep, dayKey) {
  return (championKeep.blocks ?? []).flatMap((block) => appointmentsFor(championKeep, dayKey, block.key)
    .filter((appointment) => appointment.omitFromKeep !== true)
    .map((appointment) => ({
      id: appointment.id,
      title: appointment.title,
      category: appointment.category,
      timing: { ...appointment.timing },
    })));
}

/** One day key, as the web page renders it: what the day is for, the shape of its blocks, what is
 *  booked, and what is eaten. Past the calendar (no season), the day keeps its shape and loses what
 *  depends on a season: `meals` is null, each block's `start`/`end` is null, and each block's meal keeps
 *  the slab's meal option name and drops the dish ({name, dish: null}). */
function keepDay(championKeep, day, season, blocks) {
  const seasonKey = season?.key ?? null;
  const meals = seasonKey ? mealsForDayKey(championKeep, day.dayKey, seasonKey) : null;
  return {
    dayKey: day.dayKey,
    label: dayLabel(championKeep, day.dayKey),
    week: day.index <= 7 ? 1 : 2,
    mainFocus: day.mainFocus,
    mainFocusLabel: day.mainFocusLabel,
    blocks: blocks.map((block) => {
      // Past the calendar there is no season to pick a Meals row from, so the block keeps the name it
      // gives its meal and loses the dish — the name is the block's, so no row is needed. A block whose
      // option has no Meals column (Breakfast, or none at all) is null on both sides of the edge.
      const mealName = mealNameForBlock(block);
      const meal = seasonKey === null
        ? (mealName ? { name: mealName, dish: null } : null)
        : mealForBlock(championKeep, day.dayKey, block, seasonKey);
      return {
        key: block.key,
        label: block.label,
        start: season ? (block.start ?? null) : null,
        end: season ? (block.end ?? null) : null,
        // The slab's display text ("Meal Prep"), not a category key — too-dark carries none.
        focus: day.blockFocus?.[block.key] ?? null,
        meal,
      };
    }),
    appointments: appointmentsForDayKey(championKeep, day.dayKey),
    // The three dishes only; the row's dayKey and sourceRow are the slab's business, not the page's.
    meals: meals
      ? { brunch: meals.brunch ?? null, snack: meals.snack ?? null, dinner: meals.dinner ?? null }
      : null,
  };
}

/** Which stones the keep is built of, which are foci, and which carry categories — copied verbatim
 *  from the Champion's keep (beinsiculous/fortknight#19, #36; the rule is fortknight's DOMAIN.md, "Composition"),
 *  additively: no version bump. A Champion's keep from before its schemaVersion 6 carries neither list, and then
 *  neither is written, because absent has to stay sayable: "this export predates composition" is a
 *  different sentence from "this fort added no optional stone" (stones: ["fort-knight"], foci: []).
 *  Each list is copied only when the source carries it — a source with stones and no foci yields
 *  stones and no foci, never an invented "no focus stones" (adversarial review, code round, F1).
 *  Nothing is copied without stones: the schema makes foci depend on them and carriers name them, so
 *  a source with foci and no stones yields a keep without composition rather than one the schema
 *  refuses. meta.carriers is copied when it is an object. */
function composition(championKeep) {
  const meta = championKeep.meta ?? {};
  if (!Array.isArray(meta.stones)) return {};
  const declared = { stones: [...meta.stones] };
  if (Array.isArray(meta.foci)) declared.foci = [...meta.foci];
  if (meta.carriers && typeof meta.carriers === "object" && !Array.isArray(meta.carriers)) {
    declared.carriers = { ...meta.carriers };
  }
  return declared;
}

/** The whole file. `isoDate` picks the season and the year — the fourteen days carry no dates and cannot
 *  go stale, but the season card and the wheel are snapshots of the moment this was exported, which is why
 *  `exportedAt` travels with them and the page can say how old they are.
 *
 *  A date the calendar cannot answer yields a null season AND a null year, and the two are tied together
 *  deliberately. They are one question — what is it right now — so answering half of it would be worse
 *  than answering none. Past the calendar, menu, menuAlternates, and menuProfile are null together with season.
 *  outsideSafety is copied without sourceRow, [] when empty, null when absent. All three new sections
 *  are always keys on the built keep. */
export function buildKeep(championKeep, isoDate, exportedAt = null) {
  const season = resolveSeasons(championKeep, isoDate).find((entry) => entry.isCurrent) ?? null;
  const wheel = resolveYear(championKeep, isoDate);
  const blocks = timedBlocks(championKeep, season?.key ?? null);

  let menu = null;
  let menuAlternates = null;
  let menuProfile = null;

  if (season) {
    // EMPTY HAS TO BE SAYABLE. resolveMenu always returns its three slots, so a household with no menu
    // for this season would otherwise export three empty slots and every reader would call that "a menu
    // with three things in it" (adversarial review, code round, F1). The rows are counted with the rule
    // resolveMenu writes with — rowsForSeason — or the two disagree on a file that mixes tagged and
    // untagged rows and the empty state becomes unreachable again.
    menu = rowsForSeason(championKeep.menu, season.key).length === 0 ? [] : resolveMenu(championKeep, season.key);

    if (championKeep.menuAlternates !== undefined) {
      menuAlternates = rowsForSeason(championKeep.menuAlternates, season.key).map((row) => {
        const { sourceRow, ...withoutRow } = row ?? {};
        return withoutRow;
      });
    }

    if (championKeep.menuProfiles !== undefined) {
      // The season's own profile first; a profile tagged with no season is the fallback, never the pick.
      const profiles = championKeep.menuProfiles ?? [];
      const profile = profiles.find((candidate) => candidate?.season === season.key)
        ?? profiles.find((candidate) => candidate?.season == null);
      menuProfile = Array.isArray(profile?.settings)
        ? profile.settings.map((entry) => ({ setting: entry.setting, value: entry.value }))
        : [];
    }
  }

  let outsideSafety = null;
  if (championKeep.outsideSafety !== undefined && championKeep.outsideSafety !== null) {
    outsideSafety = (championKeep.outsideSafety ?? []).map((row) => {
      const { sourceRow, ...withoutRow } = row ?? {};
      return withoutRow;
    });
  }

  return {
    meta: {
      format: "keep",
      version: KEEP_FORMAT_VERSION,
      exportedAt,
      ...composition(championKeep),
    },
    days: (championKeep.days ?? []).map((day) => keepDay(championKeep, day, season, blocks)),
    // The fortnight menu, by slot. resolveMenu is the Menu screen's own projection.
    menu,
    menuAlternates,
    menuProfile,
    outsideSafety,
    season,
    year: season && wheel.status === "year" ? wheel : null,
  };
}
