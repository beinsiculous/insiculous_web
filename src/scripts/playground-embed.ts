export {};

import { createScriptsPanel } from './playground-scripts-panel.ts';
import { probeWebGpu, describeWebGpuFailure } from './webgpu-gate.ts';
import { createPreviewLaunch } from './playground-preview-launch.ts';

const embed = document.querySelector('.playground-embed');
const src = embed?.getAttribute('data-wasm-src');
const status = document.getElementById('game-loading');
const banner = document.getElementById('playground-banner');
const importRejectionActions = document.getElementById('import-rejection-actions');
const conflictedActions = document.getElementById('conflicted-actions');
const projectSelect = document.getElementById('project-select') as HTMLSelectElement | null;
const resetButton = document.getElementById('reset-button') as HTMLButtonElement | null;
const resetNote = document.getElementById('reset-note');
const exportButton = document.getElementById('export-button') as HTMLButtonElement | null;
const saveButton = document.getElementById('save-button') as HTMLButtonElement | null;
const importInput = document.getElementById('import-input') as HTMLInputElement | null;
const commandForm = document.getElementById('command-form') as HTMLFormElement | null;
const commandInput = document.getElementById('command-input') as HTMLInputElement | null;
const commandSubmit = document.getElementById('command-submit') as HTMLButtonElement | null;
const commandOutput = document.getElementById('command-output');
const compatibilityPanel = document.getElementById('compatibility-panel');
const compatibilityReason = document.getElementById('compatibility-reason');
const compatibilityRetry = document.getElementById(
  'compatibility-retry'
) as HTMLButtonElement | null;
const stage = embed?.querySelector<HTMLElement>('.stage') ?? null;
const playButton = document.getElementById('play-button') as HTMLButtonElement | null;
const previewBlocked = document.getElementById('preview-blocked');
const previewRetry = document.getElementById('preview-retry') as HTMLButtonElement | null;
const firstRunHint = document.getElementById('playground-hint');

function downloadBytes(data: Uint8Array | Blob, filename: string) {
  const isZip = filename.endsWith('.zip');
  const mimeType = isZip ? 'application/zip' : 'application/octet-stream';
  const blob =
    data instanceof Blob ? data : new Blob([data as unknown as BlobPart], { type: mimeType });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  // Firefox can drop a download whose blob URL is revoked before the navigation commits.
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
}

// Mirrors MAX_ARCHIVE_BYTES in the engine's crates/playground/src/archive.rs (refused when
// larger); checking here spares the tab from buffering a multi-gigabyte pick before the
// refusal. The engine also caps the decompressed bytes as it reads them.
const MAX_ARCHIVE_BYTES = 64 * 1024 * 1024;

function basename(path: string): string {
  const slashIndex = path.lastIndexOf('/');
  return slashIndex === -1 ? path : path.slice(slashIndex + 1);
}

function renderImportRejectionDownload(file: File) {
  if (!importRejectionActions) return;
  importRejectionActions.innerHTML = '';
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn-banner-action';
  button.textContent = `Download ${file.name}`;
  button.addEventListener('click', () => {
    downloadBytes(file, file.name);
  });
  importRejectionActions.appendChild(button);
}

/** The wasm-bindgen glue's exports the page reaches. */
type PlaygroundModule = {
  default: () => Promise<unknown>;
  playground_list_projects: () => Array<{
    manifest: {
      slug: string;
      title: string;
      bundle_version: string;
      content_hash: string;
      origin: string;
    };
    is_bundled: boolean;
    has_stored_files: boolean;
    differs_from_bundle: boolean;
  }>;
  playground_open_project: (slug: string) => Promise<unknown>;
  playground_reset_project: (slug: string) => Promise<unknown>;
  playground_dispatch: (line: string) => boolean;
  playground_poll_responses: () => string[];
  playground_is_dirty: () => boolean;
  playground_export_zip: () => Promise<Uint8Array>;
  playground_snapshot: (generation: bigint) => Promise<{ sceneEntry: string; bytes: Uint8Array }>;
  playground_set_preview_open: (open: boolean) => void;
  playground_import_zip: (bytes: Uint8Array) => Promise<string>;
  playground_read_file_bytes: (path: string) => Uint8Array;
  playground_conflicted_paths: () => string[];
  playground_list_files: () => string[];
  playground_read_file: (path: string) => string;
  playground_write_file: (path: string, text: string) => void;
  playground_script_errors: () => string[];
};

// A boot whose `wasm.default()` RESOLVED started the engine's event loop, and a page
// holding one cannot boot a second — so Try again is dead once that happens, and a
// later failure says to reload instead. A `wasm.default()` that rejected (a chunked
// download failing mid-stream is the common case) started no loop, so it can retry.
let booting = false;
let initResolved = false;
let controlsWired = false;

// The panel takes the canvas's place: a black stage under it is the failure state the
// panel exists to replace.
function showCompatibility(message: string) {
  if (compatibilityReason) compatibilityReason.textContent = message;
  if (compatibilityPanel) compatibilityPanel.hidden = false;
  if (stage) stage.hidden = true;
  // An instruction to use the Hierarchy above a panel saying the editor
  // cannot run here would contradict it.
  if (firstRunHint) firstRunHint.hidden = true;
}

/**
 * Every control listener, wired once per page. A `wasm.default()` that rejected leaves
 * the page holding this same (module-cached) glue, so a retry must not wire a second
 * set: one chosen ZIP would import twice, and two response pollers would race the
 * save queue.
 */
function wireControls(wasm: PlaygroundModule) {
  const scriptsPanel = createScriptsPanel(wasm);
  const isDirty = (): boolean => wasm.playground_is_dirty() || scriptsPanel.isDirty();

  const searchParams = new URLSearchParams(window.location.search);
  let currentSlug = searchParams.get('project') || '';

  const previewLaunch = createPreviewLaunch({
    wasm,
    playButton,
    blockedAlert: previewBlocked,
    retryButton: previewRetry,
    banner,
    canvas: () => document.getElementById('game-canvas'),
    // The select carries the titles the manifest named; before it is filled the slug
    // is the only name the page has.
    title: () =>
      projectSelect?.selectedOptions[0]?.textContent?.trim() || currentSlug || 'Preview',
  });
  // A confirmed switch or reset navigates on purpose; without this flag the
  // beforeunload handler below would ask a second time on top of the confirm.
  let leavingByChoice = false;
  let pollIntervalId = 0;
  let lastConflictedPaths: string[] = [];

  // The engine answers one JSON line per dispatched line, in order, so who asked is
  // a queue rather than anything read off the response: every accepted dispatch
  // pushes its asker, and each response line shifts one off. Reading the answer's
  // content to guess the asker would misattribute two commands with the same shape.
  type ResponseSink = 'console' | 'save';
  const responseSinks: ResponseSink[] = [];

  // A refusal the banner carries is cleared by the next save that goes through — and
  // only that refusal, so a banner some other failure wrote is left standing.
  let lastSaveError: string | null = null;
  const reportSaveResponse = (line: string) => {
    try {
      const parsed = JSON.parse(line);
      if (!parsed || !banner) return;
      if (parsed.ok === false) {
        lastSaveError = String(parsed.error);
        banner.textContent = lastSaveError;
      } else if (parsed.ok === true && lastSaveError !== null && banner.textContent === lastSaveError) {
        banner.textContent = '';
        lastSaveError = null;
      }
    } catch {
      // A response that is not JSON is still shown in the console below; the banner
      // only ever carries an error the engine named.
    }
  };

  const pollResponses = () => {
    const responses = wasm.playground_poll_responses();
    if (responses && responses.length > 0) {
      for (const line of responses) {
        const sink = responseSinks.shift() ?? 'console';
        if (sink === 'save') reportSaveResponse(line);
        if (commandOutput) {
          const row = document.createElement('div');
          row.className = 'response-line';
          row.textContent = line;
          commandOutput.appendChild(row);
        }
      }
      if (commandOutput) commandOutput.scrollTop = commandOutput.scrollHeight;
    }

    const conflicted = wasm.playground_conflicted_paths();
    const pathsChanged =
      conflicted.length !== lastConflictedPaths.length ||
      conflicted.some((path, index) => path !== lastConflictedPaths[index]);
    if (pathsChanged) {
      lastConflictedPaths = [...conflicted];
      if (conflictedActions) {
        conflictedActions.innerHTML = '';
        for (const path of conflicted) {
          const filename = basename(path);
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'btn-banner-action';
          // Two conflicted files can share a basename; the label carries the whole path.
          button.textContent = `Download ${path}`;
          button.addEventListener('click', () => {
            try {
              const bytes = wasm.playground_read_file_bytes(path);
              downloadBytes(bytes, filename);
            } catch (error) {
              if (banner) banner.textContent = String(error);
            }
          });
          conflictedActions.appendChild(button);
        }
      }
    }
  };

  // Register playground-ready listener on window BEFORE awaiting init()
  window.addEventListener('playground-ready', () => {
    if (status) status.textContent = '';
    const entries = wasm.playground_list_projects();
    if (!entries || entries.length === 0) return;

    if (!currentSlug || !entries.some((entry) => entry.manifest.slug === currentSlug)) {
      currentSlug = entries[0].manifest.slug;
    }

    // Only the DATA optgroup is rebuilt: the Rust-games group beside it is
    // static markup from the page, and clearing the whole select would drop it.
    const dataGroup = document.getElementById('project-select-data');
    if (projectSelect && dataGroup) {
      dataGroup.innerHTML = '';
      for (const entry of entries) {
        const option = document.createElement('option');
        option.value = entry.manifest.slug;
        option.textContent = entry.manifest.title;
        if (entry.manifest.slug === currentSlug) {
          option.selected = true;
        }
        dataGroup.appendChild(option);
      }
      projectSelect.value = currentSlug;
      projectSelect.disabled = false;
    }

    const currentEntry = entries.find((entry) => entry.manifest.slug === currentSlug);
    if (resetButton && resetNote) {
      if (currentEntry && currentEntry.is_bundled && currentEntry.has_stored_files) {
        resetButton.hidden = false;
        resetButton.disabled = false;
        if (currentEntry.differs_from_bundle) {
          resetNote.hidden = false;
          resetNote.textContent =
            currentEntry.manifest.origin === 'imported'
              ? 'you imported over the bundled project'
              : 'the bundled project changed since you saved';
        } else {
          resetNote.hidden = true;
          resetNote.textContent = '';
        }
      } else {
        resetButton.hidden = true;
        resetButton.disabled = true;
        resetNote.hidden = true;
        resetNote.textContent = '';
      }
    }

    if (exportButton) exportButton.disabled = false;
    previewLaunch.enable();
    if (saveButton) saveButton.disabled = false;
    if (importInput) importInput.disabled = false;
    if (commandInput) commandInput.disabled = false;
    if (commandSubmit) commandSubmit.disabled = false;
    scriptsPanel.enable();
    // Every glue export dereferences the module; before init resolves a poll throws.
    if (!pollIntervalId) pollIntervalId = window.setInterval(pollResponses, 100);
  });

  if (saveButton) {
    // The same verb Ctrl+S sends inside the canvas, now visible — and its refusal
    // while a batch is open or a simulation is running lands on the banner instead
    // of only in the console.
    saveButton.addEventListener('click', () => {
      const accepted = wasm.playground_dispatch('save');
      if (!accepted) {
        // Save-owned like a refusal the engine names, so the next save that goes
        // through clears it.
        lastSaveError = 'The editor is busy — try saving again.';
        if (banner) banner.textContent = lastSaveError;
        return;
      }
      responseSinks.push('save');
    });
  }

  if (projectSelect) {
    projectSelect.addEventListener('change', async () => {
      const targetSlug = projectSelect.value;
      if (targetSlug === currentSlug) return;

      if (isDirty()) {
        const confirmed = window.confirm(
          'You have unsaved changes. Discard them and switch projects?'
        );
        if (!confirmed) {
          // The browser has already moved the value; without this reset the
          // cancelled option can never fire `change` again.
          projectSelect.value = currentSlug;
          return;
        }
      }

      // A value that is a path is one of the Rust games' editor pages, not a
      // project this bundle can open.
      if (targetSlug.startsWith('/')) {
        leavingByChoice = true;
        window.location.href = targetSlug;
        return;
      }

      try {
        projectSelect.disabled = true;
        await wasm.playground_open_project(targetSlug);
        leavingByChoice = true;
        window.location.search = '?project=' + encodeURIComponent(targetSlug);
      } catch (error) {
        leavingByChoice = false;
        projectSelect.disabled = false;
        projectSelect.value = currentSlug;
        if (banner) banner.textContent = String(error);
      }
    });
  }

  if (resetButton) {
    resetButton.addEventListener('click', async () => {
      const message = isDirty()
        ? 'You have unsaved changes. Reset this project to bundled content? All stored edits in this browser will be discarded.'
        : 'Reset this project to bundled content? All stored edits in this browser will be discarded.';
      const confirmed = window.confirm(message);
      if (!confirmed) return;

      try {
        resetButton.disabled = true;
        await wasm.playground_reset_project(currentSlug);
        leavingByChoice = true;
        window.location.search = '?project=' + encodeURIComponent(currentSlug);
      } catch (error) {
        leavingByChoice = false;
        resetButton.disabled = false;
        if (banner) banner.textContent = String(error);
      }
    });
  }

  if (exportButton) {
    // The export is answered on a later frame, so the button stays disabled from the
    // click until it settles: a second click would file a second archive of the same
    // world and download both.
    exportButton.addEventListener('click', async () => {
      exportButton.disabled = true;
      try {
        const bytes = await wasm.playground_export_zip();
        downloadBytes(bytes, `${currentSlug}.zip`);
      } catch (error) {
        if (banner) banner.textContent = String(error);
      } finally {
        exportButton.disabled = false;
      }
    });
  }

  if (importInput) {
    importInput.addEventListener('change', async () => {
      const file = importInput.files?.[0];
      if (!file) return;

      if (file.size > MAX_ARCHIVE_BYTES) {
        if (banner) banner.textContent = `${file.name} is over the 64 MiB import limit`;
        importInput.value = '';
        return;
      }

      // One store mutation at a time: a switch, reset or second import during the
      // drain-and-replace window would race it.
      const transitionControls = [importInput, projectSelect, resetButton, exportButton];
      const setTransitionControlsDisabled = (disabled: boolean) => {
        for (const control of transitionControls) {
          if (control) control.disabled = disabled;
        }
      };

      try {
        if (isDirty()) {
          const confirmed = window.confirm(
            'You have unsaved changes. Discard them and import project?'
          );
          if (!confirmed) {
            return;
          }
        }

        if (importRejectionActions) {
          importRejectionActions.innerHTML = '';
        }

        setTransitionControlsDisabled(true);
        const buffer = await file.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        const slug = await wasm.playground_import_zip(bytes);
        leavingByChoice = true;
        window.location.search = '?project=' + encodeURIComponent(slug);
      } catch (error) {
        setTransitionControlsDisabled(false);
        if (banner) banner.textContent = String(error);
        renderImportRejectionDownload(file);
      } finally {
        importInput.value = '';
      }
    });
  }

  if (commandForm && commandInput) {
    commandForm.addEventListener('submit', (event) => {
      event.preventDefault();
      const line = commandInput.value.trim();
      if (!line) return;

      const echoedRow = document.createElement('div');
      echoedRow.className = 'command-echo';
      echoedRow.textContent = `> ${line}`;
      commandOutput?.appendChild(echoedRow);

      const accepted = wasm.playground_dispatch(line);
      if (!accepted) {
        const errorRow = document.createElement('div');
        errorRow.className = 'error-line';
        errorRow.textContent = 'busy — try again';
        commandOutput?.appendChild(errorRow);
      } else {
        responseSinks.push('console');
        commandInput.value = '';
      }
      if (commandOutput) commandOutput.scrollTop = commandOutput.scrollHeight;
    });
  }

  window.addEventListener('beforeunload', (event) => {
    if (leavingByChoice) return;
    if (isDirty()) {
      event.preventDefault();
      event.returnValue = 'Changes you made may not be saved.';
      return 'Changes you made may not be saved.';
    }
  });
}

async function bootPlayground(source: string) {
  if (booting || initResolved) return;
  booting = true;
  if (compatibilityPanel) compatibilityPanel.hidden = true;
  if (stage) stage.hidden = false;
  // A retry after a failed boot restores the hint the failure hid — unless
  // the visitor dismissed it, which the hint's own script records on it.
  if (firstRunHint) firstRunHint.hidden = firstRunHint.dataset.dismissed === 'true';
  try {
    const probe = await probeWebGpu();
    if (!probe.ok) {
      // The status is the live region, so the reason is announced there; the panel
      // repeats it beside what to do about it.
      const reason = describeWebGpuFailure(probe.reason);
      if (status) status.textContent = `The playground needs WebGPU. ${reason}`;
      showCompatibility(reason);
      return;
    }

    if (status) status.textContent = 'Loading playground…';
    const dynamicImport = new Function('u', 'return import(u)') as (
      u: string
    ) => Promise<PlaygroundModule>;

    const wasm = await dynamicImport(source);

    if (!controlsWired) {
      // Marked before wiring: a wiring that threw halfway must not be retried into a
      // second set of listeners.
      controlsWired = true;
      wireControls(wasm);
    }

    await wasm.default();
    initResolved = true;
    if (compatibilityRetry) compatibilityRetry.disabled = true;
  } catch (error) {
    if (status) status.textContent = 'Failed to start: ' + error;
    showCompatibility(
      initResolved
        ? 'The editor stopped after it started. Reload the page to try again.'
        : String(error)
    );
  } finally {
    booting = false;
  }
}

if (src) {
  compatibilityRetry?.addEventListener('click', () => {
    void bootPlayground(src);
  });
  // The stage is laid out before this runs, so winit finds a canvas with a real box.
  await bootPlayground(src);
}
