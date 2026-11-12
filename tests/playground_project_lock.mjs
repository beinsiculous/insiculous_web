import assert from 'node:assert/strict';
import {
  acquireProjectLock,
  isMoveBoot,
  lockName,
  MOVE_RETRY_ATTEMPTS,
  resolveProjectSlug,
  runFencedImport,
  withoutMove,
  withProject,
} from '../src/scripts/playground-project-lock.ts';

/**
 * Web Locks as a browser grants them to `ifAvailable` requests: a free name is granted
 * and held until the callback's promise settles; a held name calls back with `null` at
 * once. A request that would queue fails the test, because no page may wait in line.
 */
function fakeLocks() {
  const held = new Set();
  const requests = [];
  return {
    held,
    requests,
    request(name, options, callback) {
      assert.equal(options?.ifAvailable, true, 'every request is ifAvailable, never queued');
      requests.push(name);
      if (held.has(name)) return Promise.resolve(callback(null));
      held.add(name);
      return Promise.resolve(callback({ name })).finally(() => held.delete(name));
    },
  };
}

const response = (body, ok = true) => ({ ok, json: async () => (typeof body === 'string' ? JSON.parse(body) : body) });
let scenarios = 0;
const scenario = async (name, body) => {
  await body();
  scenarios += 1;
};

await scenario('the names and the query rules', () => {
  assert.equal(lockName('pong'), 'beinsiculous.playground:pong');
  assert.equal(isMoveBoot('?project=pong&move=1'), true);
  assert.equal(isMoveBoot('?project=pong'), false);
  assert.equal(withProject('https://site.test/playground/window/?move=1', 'pong'), '/playground/window/?move=1&project=pong');
  assert.equal(withoutMove('https://site.test/playground/?project=pong&move=1'), '/playground/?project=pong');
});

await scenario('the slug comes from the query, or from the bundle list the engine reads', async () => {
  const fetches = [];
  const fetchList = async (url) => {
    fetches.push(url);
    return response([{ slug: 'examples' }, { slug: 'pong' }]);
  };
  const options = { listUrl: '/playground/v6/assets/projects.json', fetchList, timeoutMs: 1_000 };
  assert.equal(await resolveProjectSlug({ ...options, search: '?project=pong' }), 'pong');
  assert.deepEqual(fetches, [], 'an explicit project fetches nothing');
  assert.equal(await resolveProjectSlug({ ...options, search: '' }), 'examples');
  assert.deepEqual(fetches, ['/playground/v6/assets/projects.json']);
});

await scenario('a list that fails, is slow, is empty or will not parse stops the page', async () => {
  const base = { search: '', listUrl: '/list.json', timeoutMs: 20 };
  const outcomes = [
    await resolveProjectSlug({ ...base, fetchList: async () => { throw new TypeError('offline'); } }),
    await resolveProjectSlug({ ...base, fetchList: async () => response([], false) }),
    await resolveProjectSlug({ ...base, fetchList: async () => response([]) }),
    await resolveProjectSlug({ ...base, fetchList: async () => response('not json') }),
    await resolveProjectSlug({
      ...base,
      fetchList: (url, init) =>
        new Promise((_, reject) => init.signal.addEventListener('abort', () => reject(new Error('aborted')))),
    }),
  ];
  assert.deepEqual(outcomes, [null, null, null, null, null], 'never a guessed name');
});

await scenario('a free project is granted and held for the document', async () => {
  const locks = fakeLocks();
  const options = { locks, slug: 'pong', attempts: 1, intervalMs: 100, wait: async () => {} };
  assert.equal(await acquireProjectLock(options), 'granted');
  assert.ok(locks.held.has('beinsiculous.playground:pong'), 'the grant never settles, so the lock stays held');
  assert.equal(await acquireProjectLock(options), 'held', 'a second page meets the owner card');
});

await scenario('a move boot asks again, a bounded number of times, and is granted once the source goes', async () => {
  const locks = fakeLocks();
  locks.held.add(lockName('pong'));
  const waits = [];
  let retrying = 0;
  const outcome = await acquireProjectLock({
    locks,
    slug: 'pong',
    attempts: MOVE_RETRY_ATTEMPTS,
    intervalMs: 100,
    wait: async (milliseconds) => {
      waits.push(milliseconds);
      if (waits.length === 3) locks.held.delete(lockName('pong'));
    },
    onRetrying: () => (retrying += 1),
  });
  assert.equal(outcome, 'granted');
  assert.equal(locks.requests.length, 4);
  assert.deepEqual(waits, [100, 100, 100]);
  assert.equal(retrying, 1, 'Moving the editor… is said once');
});

await scenario('a source that never lets go leaves the move boot on the owner card after its attempts', async () => {
  const locks = fakeLocks();
  locks.held.add(lockName('pong'));
  let waits = 0;
  const outcome = await acquireProjectLock({
    locks, slug: 'pong', attempts: MOVE_RETRY_ATTEMPTS, intervalMs: 100, wait: async () => { waits += 1; },
  });
  assert.equal(outcome, 'held');
  assert.equal(locks.requests.length, MOVE_RETRY_ATTEMPTS, 'exactly the bounded count, 5 s at 100 ms');
  assert.equal(waits, MOVE_RETRY_ATTEMPTS - 1);
});

await scenario('no lock API, or one that throws, boots as before', async () => {
  const wait = async () => {};
  assert.equal(await acquireProjectLock({ locks: null, slug: 'pong', attempts: 1, intervalMs: 1, wait }), 'unsupported');
  const throwing = { request: () => { throw new DOMException('denied', 'SecurityError'); } };
  assert.equal(await acquireProjectLock({ locks: throwing, slug: 'pong', attempts: 1, intervalMs: 1, wait }), 'unsupported');
  const rejecting = { request: () => Promise.reject(new DOMException('denied', 'SecurityError')) };
  assert.equal(await acquireProjectLock({ locks: rejecting, slug: 'pong', attempts: 1, intervalMs: 1, wait }), 'unsupported');
});

await scenario('an archive naming the open project imports under the lock the page holds', async () => {
  const locks = fakeLocks();
  let imported = 0;
  const slug = await runFencedImport({
    locks, targetSlug: 'pong', openSlug: 'pong', importArchive: async () => { imported += 1; return 'pong'; },
  });
  assert.equal(slug, 'pong');
  assert.equal(imported, 1);
  assert.deepEqual(locks.requests, [], 'the open project is already this page’s');
});

await scenario('an archive naming another project takes that project’s lock for the import', async () => {
  const locks = fakeLocks();
  const slug = await runFencedImport({
    locks,
    targetSlug: 'mine',
    openSlug: 'pong',
    importArchive: async () => {
      assert.ok(locks.held.has(lockName('mine')), 'held while the store is written');
      return 'mine';
    },
  });
  assert.equal(slug, 'mine');
  assert.ok(!locks.held.has(lockName('mine')), 'released for the navigation that opens it');
});

await scenario('an archive naming a project open in another tab is refused before anything is written', async () => {
  const locks = fakeLocks();
  locks.held.add(lockName('mine'));
  let imported = 0;
  await assert.rejects(
    runFencedImport({ locks, targetSlug: 'mine', openSlug: 'pong', importArchive: async () => { imported += 1; return 'mine'; } }),
    /“mine” is open in another tab or window — close it before importing over it/
  );
  assert.equal(imported, 0);
});

console.log(`Project lock: ${scenarios} scenarios passed`);
