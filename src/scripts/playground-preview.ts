export {};

import { probeWebGpu, describeWebGpuFailure } from './webgpu-gate.ts';
import {
  acceptedMessage,
  PREVIEW_BOOT_DEADLINE_MS,
  PREVIEW_SNAPSHOT_DEADLINE_MS,
  type PreviewMessage,
} from './playground-preview-protocol.ts';

/**
 * The preview window's side of the protocol: boot the playground bundle in preview
 * mode, tell the editor when the runtime is up, load the one archive it sends, and
 * report what happened.
 *
 * The engine dispatches its ready event only from `run_playground`, which preview mode
 * never reaches — `start()` returns right after it announces the mode. So the ready
 * signal here is `wasm.default()` RESOLVING, and this file listens for no engine event
 * at all; the editor's page is the one that gets one.
 */

/** The preview-mode exports, from the engine's docs/WEB_PLAYGROUND.md § The preview window. */
type PreviewModule = {
  default: () => Promise<unknown>;
  playground_load_preview: (bytes: Uint8Array, sceneEntry: string) => void;
  playground_preview_state: () => string;
  playground_preview_pause: () => boolean;
  playground_preview_restart: () => void;
};

const embed = document.querySelector('.preview-embed');
const source = embed?.getAttribute('data-wasm-src');
const status = document.getElementById('game-loading');
const banner = document.getElementById('playground-banner');
const orphan = document.getElementById('preview-orphan');
const projectName = document.getElementById('preview-project');
const pauseButton = document.getElementById('preview-pause') as HTMLButtonElement | null;
const restartButton = document.getElementById('preview-restart') as HTMLButtonElement | null;
const closeButton = document.getElementById('preview-close') as HTMLButtonElement | null;
const compatibilityPanel = document.getElementById('compatibility-panel');
const compatibilityReason = document.getElementById('compatibility-reason');
const compatibilityRetry = document.getElementById(
  'compatibility-retry'
) as HTMLButtonElement | null;

const searchParams = new URLSearchParams(window.location.search);
const generationParam = searchParams.get('generation');
const generation = generationParam === null ? Number.NaN : Number(generationParam);
const opener = window.opener as Window | null;
const isPreviewDocument =
  searchParams.get('mode') === 'preview' && Number.isFinite(generation) && Boolean(opener);

function setStatus(text: string) {
  if (status) status.textContent = text;
}

/** Resolved when needed: winit replaces the placeholder canvas at boot and keeps the id. */
function focusCanvas() {
  document.getElementById('game-canvas')?.focus({ preventScroll: true });
}

function post(message: PreviewMessage) {
  opener?.postMessage(message, window.location.origin);
}

/** Terminal for this document: nothing after it may post, poll or unhide anything. */
let settled = false;
let snapshotDeadlineId = 0;
let bootDeadlineId = 0;
let statePollId = 0;

function clearTimers() {
  window.clearTimeout(snapshotDeadlineId);
  window.clearTimeout(bootDeadlineId);
  window.clearInterval(statePollId);
  snapshotDeadlineId = 0;
  bootDeadlineId = 0;
  statePollId = 0;
}

function fail(error: string) {
  if (settled) return;
  settled = true;
  clearTimers();
  setStatus(error);
  post({ type: 'preview-failed', generation, error });
}

if (!isPreviewDocument) {
  // Not a launch: no opener to tell, and no runtime worth starting. The audits load
  // the page exactly like this, which is why the message is static markup.
  setStatus('');
  if (orphan) orphan.hidden = false;
  // `window.close()` only closes a window a script opened, and this one has no opener.
  if (closeButton) closeButton.hidden = true;
} else if (source) {
  closeButton?.addEventListener('click', () => window.close());

  window.addEventListener('pagehide', () => {
    post({ type: 'preview-closed', generation });
  });

  void bootPreview(source);
}

async function bootPreview(glueSource: string) {
  try {
    const probe = await probeWebGpu();
    if (!probe.ok) {
      const reason = describeWebGpuFailure(probe.reason);
      setStatus(`The preview needs WebGPU. ${reason}`);
      if (compatibilityReason) compatibilityReason.textContent = reason;
      if (compatibilityPanel) compatibilityPanel.hidden = false;
      // Retry would boot a second runtime into a page that already has one; the
      // editor is where a fixed browser gets tried again.
      if (compatibilityRetry) compatibilityRetry.disabled = true;
      post({ type: 'preview-failed', generation, error: `The preview needs WebGPU. ${reason}` });
      settled = true;
      return;
    }

    setStatus('Loading preview…');
    const dynamicImport = new Function('u', 'return import(u)') as (
      u: string
    ) => Promise<PreviewModule>;
    const wasm = await dynamicImport(glueSource);

    wireControls(wasm);
    window.addEventListener('message', (event) => onEditorMessage(event, wasm));

    await wasm.default();
    setStatus('Waiting for the editor’s scene…');
    post({ type: 'preview-ready', generation });

    snapshotDeadlineId = window.setTimeout(() => {
      if (settled || loading) return;
      settled = true;
      clearTimers();
      setStatus(
        'The editor did not send a scene — close this window and press Play ↗ again.'
      );
      closeButton?.focus();
    }, PREVIEW_SNAPSHOT_DEADLINE_MS);
  } catch (error) {
    fail('Failed to start the preview: ' + error);
  }
}

/** One archive per document: the engine refuses a second, and the editor never sends one. */
let loading = false;

function onEditorMessage(event: MessageEvent, wasm: PreviewModule) {
  const message = acceptedMessage(event, opener, generation);
  if (!message || message.type !== 'preview-snapshot') return;
  if (settled || loading) return;
  loading = true;
  window.clearTimeout(snapshotDeadlineId);

  if (projectName) projectName.textContent = message.title;
  document.title = `${message.title} — game preview`;
  setStatus('Starting the scene…');

  try {
    wasm.playground_load_preview(message.bytes, message.sceneEntry);
  } catch (error) {
    fail(String(error));
    return;
  }

  bootDeadlineId = window.setTimeout(() => {
    fail('The preview did not start.');
  }, PREVIEW_BOOT_DEADLINE_MS);

  statePollId = window.setInterval(() => {
    if (settled) return;
    const state = wasm.playground_preview_state();
    if (state === 'running') {
      settled = true;
      clearTimers();
      setStatus('');
      if (pauseButton) pauseButton.disabled = false;
      if (restartButton) restartButton.disabled = false;
      post({ type: 'preview-loaded', generation });
      focusCanvas();
    } else if (state.startsWith('failed:')) {
      fail(state.slice('failed:'.length).trim());
    }
  }, 100);
}

function wireControls(wasm: PreviewModule) {
  pauseButton?.addEventListener('click', () => {
    try {
      // The name never flips to "Resume": aria-pressed is what says which state it is
      // in, and a label that changes under the pointer is the harder thing to hit twice.
      const paused = wasm.playground_preview_pause();
      pauseButton.setAttribute('aria-pressed', paused ? 'true' : 'false');
    } catch (error) {
      if (banner) banner.textContent = String(error);
    }
  });

  restartButton?.addEventListener('click', () => {
    try {
      wasm.playground_preview_restart();
      pauseButton?.setAttribute('aria-pressed', 'false');
      if (banner) banner.textContent = '';
      focusCanvas();
    } catch (error) {
      if (banner) banner.textContent = String(error);
    }
  });
}
