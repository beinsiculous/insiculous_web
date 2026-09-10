import {
  acceptedMessage,
  clearReservation,
  ownTabId,
  PREVIEW_BOOT_DEADLINE_MS,
  PREVIEW_CLOSED_POLL_MS,
  previewUrl,
  previewWindowName,
  readReservation,
  writeReservation,
} from './playground-preview-protocol.ts';

/**
 * Play ↗ — the editor's side of the preview window.
 *
 * Two lifetimes, deliberately separate. The LAUNCH runs `idle → opening → ready →
 * loaded | failed` and ends at `finishLaunch`, which is its only exit. The WINDOW
 * lifetime is the closed-poll plus the reservation that makes the editor refuse its own
 * Play; it begins when the window opens and ends on `preview-closed` or on finding the
 * window closed — never on `loaded`, so a preview that crashes an hour later is released
 * the moment its window goes away.
 *
 * A crashed preview therefore keeps the reservation until the user closes its window.
 * That is the honest residual of having no heartbeat: a hidden window's timers are
 * throttled to about one wake a minute, so silence cannot tell a dead preview from a
 * sleeping one, and releasing on silence would let two simulations run.
 */

/** The launch's half of the glue's exports. */
export type PreviewLaunchModule = {
  playground_snapshot: (generation: bigint) => Promise<{ sceneEntry: string; bytes: Uint8Array }>;
  playground_set_preview_open: (open: boolean) => void;
};

export interface PreviewLaunchOptions {
  wasm: PreviewLaunchModule;
  playButton: HTMLButtonElement | null;
  blockedAlert: HTMLElement | null;
  retryButton: HTMLButtonElement | null;
  banner: HTMLElement | null;
  /**
   * Resolved at focus time, never captured: winit replaces the placeholder canvas with
   * its own at boot and gives the new one the same id, so a node held from before the
   * boot is detached by the time anything focuses it.
   */
  canvas: () => HTMLElement | null;
  /** The open project's title, read at launch so the preview window can name it. */
  title: () => string;
}

export interface PreviewLaunch {
  /**
   * Called from the editor's `playground-ready` handler, beside Export. It is also
   * where a reloaded tab re-takes a preview it left running: the engine's reservation
   * setter is a silent no-op until the bridge hooks exist, which is a moment before
   * that event, so an earlier call would be swallowed and never retried.
   */
  enable: () => void;
}

const PREVIEW_OPEN_NOTE =
  'A preview window is open — Play ↗ again to send it new edits; Play inside the editor waits until it closes';
const PREVIEW_RETAKEN_NOTE =
  'A preview window is still open from before the reload — Play ↗ again to send it new edits; Play inside the editor waits until it closes';

export function createPreviewLaunch(options: PreviewLaunchOptions): PreviewLaunch {
  const { wasm, playButton, blockedAlert, retryButton, banner, canvas, title } = options;
  const tabId = ownTabId();

  let editorReady = false;
  let generation = 0;
  let launchState: 'idle' | 'opening' | 'ready' | 'loaded' | 'failed' = 'idle';
  let previewWindow: Window | null = null;
  let windowLifetimeActive = false;
  let closedPollId = 0;
  let bootDeadlineId = 0;
  let envelope: { sceneEntry: string; bytes: Uint8Array } | null = null;
  let readyBeforeSnapshot = false;

  const launchInFlight = () => launchState === 'opening' || launchState === 'ready';

  // The banner is a live alert: rewriting the same text re-announces it on every
  // relaunch, so an unchanged note is left alone.
  function setNote(text: string) {
    if (banner && banner.textContent !== text) banner.textContent = text;
  }

  function clearNote(text: string) {
    if (banner && banner.textContent === text) banner.textContent = '';
  }

  // An open window does not disable the button: a second Play ↗ navigates that same
  // window to a fresh document with the next generation. What the reservation refuses
  // is the editor's own Play.
  function refreshPlayButton() {
    if (!playButton) return;
    playButton.disabled = !editorReady || launchInFlight();
  }

  /** The launch-only half of an exit, shared by `finishLaunch` and the window's end. */
  function exitLaunch(outcome: 'loaded' | 'failed', failureText?: string) {
    if (!launchInFlight()) return;
    window.clearTimeout(bootDeadlineId);
    bootDeadlineId = 0;
    launchState = outcome;
    envelope = null;
    readyBeforeSnapshot = false;
    if (failureText) setNote(failureText);
    refreshPlayButton();
  }

  /**
   * A failed launch closes the window itself: a preview that finishes booting after the
   * deadline must not come up behind a failure line the user has already read.
   */
  function finishLaunch(launched: number, outcome: 'loaded' | 'failed', failureText?: string) {
    if (launched !== generation || !launchInFlight()) return;
    const windowToClose = outcome === 'failed' ? previewWindow : null;
    exitLaunch(outcome, outcome === 'failed' ? (failureText ?? 'The preview failed to start.') : undefined);
    if (windowToClose && !windowToClose.closed) windowToClose.close();
    if (outcome === 'failed') endWindowLifetime();
  }

  function beginWindowLifetime(windowName: string, note: string) {
    windowLifetimeActive = true;
    writeReservation({ windowName, tabId });
    setNote(note);
    closedPollId = window.setInterval(() => {
      if (!previewWindow || previewWindow.closed) endWindowLifetime();
    }, PREVIEW_CLOSED_POLL_MS);
    refreshPlayButton();
  }

  function endWindowLifetime() {
    if (!windowLifetimeActive) return;
    windowLifetimeActive = false;
    window.clearInterval(closedPollId);
    closedPollId = 0;
    clearReservation();
    try {
      wasm.playground_set_preview_open(false);
    } catch {
      // The engine is the one that refuses Play; a page that cannot reach it has no
      // reservation to release either.
    }
    previewWindow = null;
    // A window closed mid-launch ends it, with nothing on the banner: the visitor
    // closing the window is the answer, not a failure to report back to them.
    exitLaunch('failed');
    clearNote(PREVIEW_OPEN_NOTE);
    clearNote(PREVIEW_RETAKEN_NOTE);
    refreshPlayButton();
    returnFocusToEditor();
  }

  /** A visitor typing in the console or the script editor keeps their caret. */
  function returnFocusToEditor() {
    const active = document.activeElement as HTMLElement | null;
    if (active) {
      const tag = active.tagName;
      const nonTextInputTypes = ['button', 'checkbox', 'file', 'radio', 'submit', 'reset'];
      const isTextInput =
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        active.isContentEditable ||
        (tag === 'INPUT' && !nonTextInputTypes.includes((active as HTMLInputElement).type));
      if (isTextInput) return;
    }
    canvas()?.focus({ preventScroll: true });
  }

  function sendEnvelope() {
    if (!envelope || !previewWindow) return;
    const { sceneEntry, bytes } = envelope;
    envelope = null;
    previewWindow.postMessage(
      { type: 'preview-snapshot', generation, title: title(), sceneEntry, bytes },
      window.location.origin,
      [bytes.buffer]
    );
  }

  async function openPreview() {
    if (launchInFlight()) {
      setNote('The preview is already opening.');
      return;
    }

    const windowName = previewWindowName(tabId);
    const launched = generation + 1;
    // The first side effect of the click, with nothing awaited before it: a popup
    // blocker judges the gesture, and an await would have spent it.
    const opened = window.open(previewUrl(launched), windowName);
    if (!opened) {
      // Nothing filed: no request, no reservation, no generation spent, so there is
      // nothing for a finalizer to clean up and Retry is a fresh gesture.
      if (blockedAlert) blockedAlert.hidden = false;
      return;
    }
    if (blockedAlert) blockedAlert.hidden = true;

    generation = launched;
    launchState = 'opening';
    previewWindow = opened;
    refreshPlayButton();
    bootDeadlineId = window.setTimeout(() => {
      finishLaunch(launched, 'failed', 'The preview did not start.');
    }, PREVIEW_BOOT_DEADLINE_MS);
    // Reuse keeps the lifetime it has: the window is the same one, the old document's
    // `preview-closed` carries the old generation and is dropped, and a second poll
    // would never be cleared.
    if (windowLifetimeActive) setNote(PREVIEW_OPEN_NOTE);
    else beginWindowLifetime(windowName, PREVIEW_OPEN_NOTE);

    try {
      const snapshot = await wasm.playground_snapshot(BigInt(launched));
      if (launched !== generation || !launchInFlight()) return;
      envelope = snapshot;
      if (readyBeforeSnapshot) sendEnvelope();
    } catch (error) {
      finishLaunch(launched, 'failed', String(error));
    }
  }

  function onPreviewMessage(event: MessageEvent) {
    const message = acceptedMessage(event, previewWindow, generation);
    if (!message) return;
    if (message.type === 'preview-ready') {
      // Ignored outside a launch: a preview the visitor reloads posts a fresh ready into
      // a settled opener, and its own no-snapshot deadline is the right end for it.
      if (!launchInFlight()) return;
      launchState = 'ready';
      if (envelope) sendEnvelope();
      else readyBeforeSnapshot = true;
    } else if (message.type === 'preview-loaded') {
      finishLaunch(generation, 'loaded');
    } else if (message.type === 'preview-failed') {
      finishLaunch(generation, 'failed', message.error);
    } else if (message.type === 'preview-closed') {
      endWindowLifetime();
    }
  }

  /**
   * A reloaded editor tab re-takes the preview it left running; without this the reload
   * left a live simulation and an editor that would happily start a second one.
   */
  function adoptExistingPreview() {
    const reservation = readReservation();
    if (!reservation) return;
    if (reservation.tabId !== tabId) {
      // A duplicated tab copies session storage but mints its own `window.name`. It must
      // not adopt the original's window, nor refuse its own Play over it.
      clearReservation();
      return;
    }
    // An empty URL navigates nothing, so a live named window comes back as itself; when
    // there is none the browser hands back a fresh blank window instead.
    const handle = window.open('', reservation.windowName);
    if (!handle || handle === window) {
      clearReservation();
      return;
    }
    let href: string | null;
    try {
      href = handle.location.href;
    } catch {
      // Cross-origin: the visitor navigated the preview window somewhere else. It is
      // not ours to close, and it holds no runtime worth reserving against.
      href = null;
    }
    if (href === null) {
      clearReservation();
      return;
    }
    if (href === 'about:blank') {
      // The probe found no window, so the browser made this blank one.
      handle.close();
      clearReservation();
      return;
    }
    // The counter restarted with this document; the adopted window's document did not.
    // A relaunch must outnumber it, or that document's `preview-closed` on navigation
    // would pass the generation check and end the launch that replaced it.
    const adoptedGeneration = Number(new URL(href).searchParams.get('generation'));
    if (Number.isFinite(adoptedGeneration) && adoptedGeneration > generation) {
      generation = adoptedGeneration;
    }
    previewWindow = handle;
    try {
      wasm.playground_set_preview_open(true);
    } catch {
      // Same as the release: an unreachable engine has no reservation to take.
    }
    beginWindowLifetime(reservation.windowName, PREVIEW_RETAKEN_NOTE);
  }

  playButton?.addEventListener('click', () => {
    void openPreview();
  });
  retryButton?.addEventListener('click', () => {
    void openPreview();
  });
  window.addEventListener('message', onPreviewMessage);
  refreshPlayButton();

  return {
    enable() {
      editorReady = true;
      adoptExistingPreview();
      refreshPlayButton();
    },
  };
}
