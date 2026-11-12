/**
 * One Playground project open in one page at a time.
 *
 * Every editor boot — the page, its window, a reload — takes a Web Lock named for the
 * project it is about to open, in this script, before the engine starts: nothing has
 * been read from the store yet, so whatever the engine reads is read under the lock. The
 * lock is held until the document goes, whatever the path, because the callback's
 * promise never settles; the browser releases it on navigation or close.
 *
 * No page ever waits in the lock's queue. A request is always `ifAvailable`: a queued
 * one outlives the intent that made it and is granted ahead of whatever the visitor
 * asks for next. A boot sent here by a hand-off (`move=1`) may find its source still
 * unloading, so it asks again a bounded number of times, then shows the owner card like
 * any boot. Pages never talk to each other; the lock is the only shared thing.
 *
 * Where the browser has no Web Locks, or refuses them, the page boots as it always did:
 * the one-page guarantee holds among pages that have the API.
 */

/** The part of `navigator.locks` this file reaches, so a test can hand in a fake. */
export interface ProjectLockManager {
  request(
    name: string,
    options: { ifAvailable: true },
    callback: (lock: unknown) => unknown
  ): Promise<unknown>;
}

export const LOCK_NAME_PREFIX = 'beinsiculous.playground:';
/** How long the bundle's project list may take before the page stops on its card. */
export const PROJECT_LIST_TIMEOUT_MS = 10_000;
/** A hand-off's destination asks every 100 ms for at most 5 s. */
export const MOVE_RETRY_INTERVAL_MS = 100;
export const MOVE_RETRY_ATTEMPTS = 50;

export type LockOutcome = 'granted' | 'held' | 'unsupported';

export function lockName(slug: string): string {
  return `${LOCK_NAME_PREFIX}${slug}`;
}

/** Whether the page's query marks a boot sent here by a hand-off. */
export function isMoveBoot(search: string): boolean {
  return new URLSearchParams(search).get('move') === '1';
}

/** `href` as a same-document path with `project` set to `slug`, every other parameter kept. */
export function withProject(href: string, slug: string): string {
  const url = new URL(href);
  url.searchParams.set('project', slug);
  return url.pathname + url.search + url.hash;
}

/** `href` as a same-document path without `move`, so a reload is an ordinary boot. */
export function withoutMove(href: string): string {
  const url = new URL(href);
  url.searchParams.delete('move');
  return url.pathname + url.search + url.hash;
}

/**
 * The project this boot opens: `?project=`, or else the first slug of the bundle's own
 * project list — the list the engine reads — so the lock is named for the project the
 * engine will open. `null` when the list fails, is slow, is empty or will not parse: a
 * guessed name would lock one project while the engine opened another.
 */
export async function resolveProjectSlug(options: {
  search: string;
  listUrl: string;
  fetchList: (url: string, init: { signal: AbortSignal }) => Promise<Response>;
  timeoutMs: number;
}): Promise<string | null> {
  const requested = new URLSearchParams(options.search).get('project');
  if (requested) return requested;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs);
  try {
    const response = await options.fetchList(options.listUrl, { signal: controller.signal });
    if (!response.ok) return null;
    const list: unknown = await response.json();
    const first = Array.isArray(list) ? (list[0] as { slug?: unknown } | undefined) : undefined;
    return typeof first?.slug === 'string' && first.slug !== '' ? first.slug : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** One `ifAvailable` request: `true` when granted, and the grant is then held for good. */
export function requestOnce(locks: ProjectLockManager, name: string): Promise<boolean> {
  return new Promise((resolve, reject) => {
    locks
      .request(name, { ifAvailable: true }, (lock) => {
        if (!lock) {
          resolve(false);
          return undefined;
        }
        resolve(true);
        return new Promise(() => {});
      })
      .catch(reject);
  });
}

/**
 * Ask for the project's lock `attempts` times, `intervalMs` apart, never queued.
 * `onRetrying` runs once, before the first wait. A lock API that throws is `unsupported`.
 */
export async function acquireProjectLock(options: {
  locks: ProjectLockManager | null;
  slug: string;
  attempts: number;
  intervalMs: number;
  wait: (milliseconds: number) => Promise<void>;
  onRetrying?: () => void;
}): Promise<LockOutcome> {
  const { locks, slug, attempts, intervalMs, wait, onRetrying } = options;
  if (!locks) return 'unsupported';
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      if (await requestOnce(locks, lockName(slug))) return 'granted';
    } catch {
      return 'unsupported';
    }
    if (attempt < attempts) {
      if (attempt === 1) onRetrying?.();
      await wait(intervalMs);
    }
  }
  return 'held';
}

/**
 * Import an archive under the lock of the project it names. The open project's own lock
 * is this page's already; any other is taken `ifAvailable` and held through the import,
 * so a page that has that project open is never written under. Refused with a message
 * naming the project when another page holds it.
 */
export async function runFencedImport(options: {
  locks: ProjectLockManager | null;
  targetSlug: string;
  openSlug: string;
  importArchive: () => Promise<string>;
}): Promise<string> {
  const { locks, targetSlug, openSlug, importArchive } = options;
  if (!locks || targetSlug === openSlug) return importArchive();
  let granted = false;
  const imported = await locks.request(lockName(targetSlug), { ifAvailable: true }, async (lock) => {
    if (!lock) return undefined;
    granted = true;
    return importArchive();
  });
  if (!granted) {
    throw new Error(`“${targetSlug}” is open in another tab or window — close it before importing over it`);
  }
  return imported as string;
}

/** The browser's lock manager, or `null` where there is none. */
export function browserLocks(): ProjectLockManager | null {
  const locks = (navigator as Navigator & { locks?: ProjectLockManager }).locks;
  return locks && typeof locks.request === 'function' ? locks : null;
}

export interface BootLock {
  /**
   * Resolve the slug and take its lock. `true`: boot — the lock is held, or the browser
   * has none. `false`: a card is up and its *Try again* calls `retry`. A grant is kept
   * for the document, so a boot retried after a failed start never asks twice.
   */
  ready: () => Promise<boolean>;
  /** Whether this page holds its project's lock (false where the API is absent). */
  holdsLock: () => boolean;
}

/** The boot's lock and its two cards, wired to the page's markup by id. */
export function createBootLock(options: { listUrl: string; retry: () => void }): BootLock {
  const status = document.getElementById('game-loading');
  const stage = document.querySelector<HTMLElement>('.playground-embed .stage');
  const ownerCard = document.getElementById('owner-card');
  const ownerProject = document.getElementById('owner-card-project');
  const listCard = document.getElementById('project-list-card');
  const firstRunHint = document.getElementById('playground-hint');
  const projectField = document.getElementById('project-select')?.closest<HTMLElement>('.field-group');
  let outcome: LockOutcome | null = null;
  let moveRetriesSpent = false;

  // The card takes the editor's place, so an instruction to use the editor goes with it, as
  // the compatibility panel's does; the boot restores the hint when it retries. The Project
  // field goes too: the engine never ran to fill it, so it would name its static default
  // beside a card naming the project that is open elsewhere.
  const showCard = (card: HTMLElement | null) => {
    if (status) status.textContent = '';
    if (stage) stage.hidden = true;
    if (firstRunHint) firstRunHint.hidden = true;
    if (projectField) projectField.hidden = true;
    if (card) card.hidden = false;
  };

  for (const id of ['owner-card-retry', 'project-list-retry']) {
    document.getElementById(id)?.addEventListener('click', () => options.retry());
  }
  document.getElementById('owner-card-close')?.addEventListener('click', () => {
    // A window the editor opened closes; a tab the visitor opened cannot, and goes to
    // the plain parked card instead.
    window.close();
    window.setTimeout(() => window.location.replace('/playground/parked/'), 200);
  });

  return {
    async ready() {
      if (outcome === 'granted' || outcome === 'unsupported') return true;
      if (ownerCard) ownerCard.hidden = true;
      if (listCard) listCard.hidden = true;
      if (stage) stage.hidden = false;
      if (projectField) projectField.hidden = false;
      const slug = await resolveProjectSlug({
        search: window.location.search,
        listUrl: options.listUrl,
        fetchList: (url, init) => fetch(url, init),
        timeoutMs: PROJECT_LIST_TIMEOUT_MS,
      });
      if (!slug) {
        showCard(listCard);
        return false;
      }
      history.replaceState(history.state, '', withProject(window.location.href, slug));
      const attempts = isMoveBoot(window.location.search) && !moveRetriesSpent ? MOVE_RETRY_ATTEMPTS : 1;
      moveRetriesSpent = true;
      outcome = await acquireProjectLock({
        locks: browserLocks(),
        slug,
        attempts,
        intervalMs: MOVE_RETRY_INTERVAL_MS,
        wait: (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds)),
        onRetrying: () => {
          if (status) status.textContent = 'Moving the editor…';
        },
      });
      if (outcome !== 'held') return true;
      if (ownerProject) ownerProject.textContent = `“${slug}”`;
      showCard(ownerCard);
      return false;
    },
    holdsLock: () => outcome === 'granted',
  };
}
