import assert from 'node:assert/strict';
import {
  commandBarrier,
  editorUrl,
  moveToWindow,
  NOTE_BARRIER_REFUSED,
  NOTE_BARRIER_SILENT,
  NOTE_IN_FLIGHT,
  NOTE_NO_LOCKS,
  NOTE_NO_STORAGE,
  NOTE_PREVIEW_OPEN,
  NOTE_SAVE_FIRST,
  openIndependentWindow,
  parkedUrl,
  windowButtonState,
  windowUrl,
  WINDOW_FEATURES,
} from '../src/scripts/playground-window.ts';

const never = () => new Promise(() => {});

/** The move's steps over fakes that record what happened, in order. */
function fakeMove(overrides = {}) {
  const calls = [];
  const view = { notes: [], banners: [], blocked: [], panel: [] };
  const handle = {
    closed: false,
    closedByMove: false,
    href: 'about:blank',
    close() {
      calls.push('close');
      this.closedByMove = true;
    },
    location: {
      set href(url) {
        calls.push(`window → ${url}`);
        handle.href = url;
      },
      get href() {
        return handle.href;
      },
    },
  };
  let dirty = false;
  const steps = {
    slug: 'pong',
    isDirty: () => dirty,
    inFlight: () => 0,
    previewOpen: () => false,
    open: () => {
      calls.push('open');
      return handle;
    },
    barrier: async () => {
      calls.push('barrier');
      return 'answered';
    },
    drain: async (slug) => {
      calls.push(`drain ${slug}`);
    },
    navigate: (url) => calls.push(`page → ${url}`),
    wait: never,
    barrierDeadlineMs: 5_000,
    note: (text) => view.notes.push(text),
    blocked: (shown) => view.blocked.push(shown),
    panel: (shown) => view.panel.push(shown),
    banner: (text) => view.banners.push(text),
    leaving: () => calls.push('leaving'),
    ...overrides,
  };
  return { steps, calls, view, handle, setDirty: (value) => (dirty = value) };
}

let scenarios = 0;
const scenario = async (name, body) => {
  await body();
  scenarios += 1;
};

await scenario('dirty or in flight refuses before anything opens', async () => {
  const dirty = fakeMove({ isDirty: () => true });
  assert.equal(await moveToWindow(dirty.steps), 'refused-dirty');
  assert.deepEqual(dirty.calls, []);
  assert.deepEqual(dirty.view.notes, [NOTE_SAVE_FIRST]);

  const busy = fakeMove({ inFlight: () => 1 });
  assert.equal(await moveToWindow(busy.steps), 'refused-in-flight');
  assert.deepEqual(busy.calls, []);
  assert.deepEqual(busy.view.notes, [NOTE_IN_FLIGHT]);

  const previewing = fakeMove({ previewOpen: () => true });
  assert.equal(await moveToWindow(previewing.steps), 'refused-preview');
  assert.deepEqual(previewing.calls, [], 'the preview would be stranded behind the parked page');
  assert.deepEqual(previewing.view.notes, [NOTE_PREVIEW_OPEN]);
});

await scenario('a blocked popup stops before anything else', async () => {
  const move = fakeMove({ open: () => null });
  assert.equal(await moveToWindow(move.steps), 'blocked');
  assert.deepEqual(move.calls, []);
  assert.deepEqual(move.view.blocked, [true]);
  assert.deepEqual(move.view.panel, [], 'no panel, no barrier, no drain');
});

await scenario('dirty after the barrier, a refused barrier and a silent one each close the window', async () => {
  const dirtyAfter = fakeMove();
  dirtyAfter.steps.barrier = async () => {
    dirtyAfter.calls.push('barrier');
    dirtyAfter.setDirty(true);
    return 'answered';
  };
  assert.equal(await moveToWindow(dirtyAfter.steps), 'dirty-after-barrier');
  assert.deepEqual(dirtyAfter.calls, ['open', 'barrier', 'close']);
  assert.deepEqual(dirtyAfter.view.panel, [true, false]);
  assert.equal(dirtyAfter.view.notes.at(-1), NOTE_SAVE_FIRST);

  const refused = fakeMove({ barrier: async () => 'refused' });
  assert.equal(await moveToWindow(refused.steps), 'barrier-refused');
  assert.deepEqual(refused.calls, ['open', 'close']);
  assert.equal(refused.view.notes.at(-1), NOTE_BARRIER_REFUSED);

  const silent = fakeMove({ barrier: never, wait: async () => {} });
  assert.equal(await moveToWindow(silent.steps), 'barrier-silent');
  assert.deepEqual(silent.calls, ['open', 'close'], 'nothing drained on silence');
  assert.equal(silent.view.notes.at(-1), NOTE_BARRIER_SILENT);
  assert.deepEqual(silent.view.panel, [true, false]);
});

await scenario('a failed drain closes the window and leaves the page as it was', async () => {
  const move = fakeMove({
    drain: async () => {
      throw new Error('refusing the switch: assets/scenes/main.scene.ron is stranded');
    },
  });
  assert.equal(await moveToWindow(move.steps), 'drain-failed');
  assert.deepEqual(move.calls, ['open', 'barrier', 'close']);
  assert.deepEqual(move.view.panel, [true, false]);
  assert.match(move.view.banners[0], /stranded/);
  assert.ok(!move.calls.some((call) => call.startsWith('page →')), 'the page does not navigate');
});

await scenario('a window closed during the drain sends the page to the ordinary editor', async () => {
  const move = fakeMove();
  move.steps.drain = async (slug) => {
    move.calls.push(`drain ${slug}`);
    move.handle.closed = true;
  };
  assert.equal(await moveToWindow(move.steps), 'window-closed');
  assert.deepEqual(move.calls.slice(-2), ['leaving', `page → ${editorUrl('pong')}`]);
  assert.equal(editorUrl('pong'), '/playground/?project=pong&move=1', 'a hand-off boot, which never falls back to memory');
});

await scenario('a window that will not be navigated sends the page to the ordinary editor', async () => {
  const move = fakeMove();
  Object.defineProperty(move.handle.location, 'href', {
    set() {
      throw new DOMException('blocked', 'SecurityError');
    },
  });
  assert.equal(await moveToWindow(move.steps), 'window-closed');
  assert.deepEqual(move.calls.slice(-2), ['close', `page → ${editorUrl('pong')}`], 'no blank window is left behind');

  const elsewhere = fakeMove();
  Object.defineProperty(elsewhere.handle.location, 'href', {
    get() {
      throw new DOMException('cross-origin', 'SecurityError');
    },
    set() {
      throw new DOMException('blocked', 'SecurityError');
    },
  });
  assert.equal(await moveToWindow(elsewhere.steps), 'window-closed');
  assert.ok(!elsewhere.calls.includes('close'), 'a window the visitor took elsewhere is not this page’s to close');
  assert.equal(elsewhere.calls.at(-1), `page → ${editorUrl('pong')}`);
});

await scenario('the move runs open → barrier → drain → the window’s location → this page’s', async () => {
  const move = fakeMove();
  assert.equal(await moveToWindow(move.steps), 'moved');
  assert.deepEqual(move.calls, [
    'open',
    'barrier',
    'drain pong',
    'leaving',
    `window → ${windowUrl('pong')}`,
    `page → ${parkedUrl('pong')}`,
  ]);
  assert.equal(windowUrl('pong'), '/playground/window/?project=pong&move=1');
  assert.equal(parkedUrl('pong'), '/playground/parked/?project=pong');
  assert.ok(!move.handle.closedByMove);
});

await scenario('the button needs the lock and a store that persists, and says which is missing', () => {
  assert.deepEqual(windowButtonState({ holdsLock: false, storagePersists: true }), { enabled: false, note: NOTE_NO_LOCKS });
  assert.deepEqual(windowButtonState({ holdsLock: true, storagePersists: false }), { enabled: false, note: NOTE_NO_STORAGE });
  assert.deepEqual(windowButtonState({ holdsLock: true, storagePersists: true }), { enabled: true, note: '' });
});

await scenario('the barrier is a read-only line answered in order, or refused at once when the channel is full', async () => {
  const sinks = [];
  const dispatched = [];
  const accepted = commandBarrier((line) => (dispatched.push(line), true), (sink) => sinks.push(sink));
  assert.deepEqual(dispatched, ['selection']);
  assert.equal(sinks.length, 1, 'filed in the response queue in its turn');
  sinks[0]('{"ok":true}');
  assert.equal(await accepted, 'answered');

  const queued = [];
  assert.equal(await commandBarrier(() => false, (sink) => queued.push(sink)), 'refused');
  assert.deepEqual(queued, [], 'a refused line files no sink, so the queue stays aligned');
});

await scenario('a game page opens a new, unnamed window every time', () => {
  const opened = [];
  assert.equal(openIndependentWindow((...call) => (opened.push(call), {}), '/playground/tong/window/'), true);
  assert.deepEqual(opened, [['/playground/tong/window/', '_blank', WINDOW_FEATURES]]);
  assert.match(WINDOW_FEATURES, /^popup,/);
  assert.equal(openIndependentWindow(() => null, '/playground/tong/window/'), false, 'blocked');
});

console.log(`Editor window: ${scenarios} scenarios passed`);
