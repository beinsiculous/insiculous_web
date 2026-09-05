export {};

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
const importInput = document.getElementById('import-input') as HTMLInputElement | null;
const commandForm = document.getElementById('command-form') as HTMLFormElement | null;
const commandInput = document.getElementById('command-input') as HTMLInputElement | null;
const commandSubmit = document.getElementById('command-submit') as HTMLButtonElement | null;
const commandOutput = document.getElementById('command-output');

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

if (src) {
  const gpu = 'gpu' in navigator ? (navigator as any).gpu : null;
  const adapter = gpu ? await gpu.requestAdapter().catch(() => null) : null;
  const device = adapter ? await adapter.requestDevice().catch(() => null) : null;
  device?.destroy();
  if (!adapter || !device) {
    if (status) {
      status.textContent =
        'The playground needs WebGPU — available in Chrome and Edge. In Firefox, enable dom.webgpu.enabled in about:config and fully restart the browser.';
    }
  } else {
    if (status) status.textContent = 'Loading playground…';
    try {
      const dynamicImport = new Function('u', 'return import(u)') as (
        u: string
      ) => Promise<{
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
        playground_export_zip: () => Uint8Array;
        playground_import_zip: (bytes: Uint8Array) => Promise<string>;
        playground_read_file_bytes: (path: string) => Uint8Array;
        playground_conflicted_paths: () => string[];
      }>;

      const wasm = await dynamicImport(src);

      const searchParams = new URLSearchParams(window.location.search);
      let currentSlug = searchParams.get('project') || '';
      // A confirmed switch or reset navigates on purpose; without this flag the
      // beforeunload handler below would ask a second time on top of the confirm.
      let leavingByChoice = false;
      let pollIntervalId = 0;
      let lastConflictedPaths: string[] = [];

      const pollResponses = () => {
        const responses = wasm.playground_poll_responses();
        if (responses && responses.length > 0 && commandOutput) {
          for (const line of responses) {
            const row = document.createElement('div');
            row.className = 'response-line';
            row.textContent = line;
            commandOutput.appendChild(row);
          }
          commandOutput.scrollTop = commandOutput.scrollHeight;
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

        if (projectSelect) {
          projectSelect.innerHTML = '';
          for (const entry of entries) {
            const option = document.createElement('option');
            option.value = entry.manifest.slug;
            option.textContent = entry.manifest.title;
            if (entry.manifest.slug === currentSlug) {
              option.selected = true;
            }
            projectSelect.appendChild(option);
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
        if (importInput) importInput.disabled = false;
        if (commandInput) commandInput.disabled = false;
        if (commandSubmit) commandSubmit.disabled = false;
        // Every glue export dereferences the module; before init resolves a poll throws.
        if (!pollIntervalId) pollIntervalId = window.setInterval(pollResponses, 100);
      });

      if (projectSelect) {
        projectSelect.addEventListener('change', async () => {
          const targetSlug = projectSelect.value;
          if (targetSlug === currentSlug) return;

          if (wasm.playground_is_dirty()) {
            const confirmed = window.confirm(
              'You have unsaved changes. Discard them and switch projects?'
            );
            if (!confirmed) {
              projectSelect.value = currentSlug;
              return;
            }
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
          const confirmed = window.confirm(
            'Reset this project to bundled content? All stored edits in this browser will be discarded.'
          );
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
        exportButton.addEventListener('click', () => {
          try {
            const bytes = wasm.playground_export_zip();
            downloadBytes(bytes, `${currentSlug}.zip`);
          } catch (error) {
            if (banner) banner.textContent = String(error);
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
            if (wasm.playground_is_dirty()) {
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
            commandInput.value = '';
          }
          if (commandOutput) commandOutput.scrollTop = commandOutput.scrollHeight;
        });
      }

      window.addEventListener('beforeunload', (event) => {
        if (leavingByChoice) return;
        if (wasm.playground_is_dirty()) {
          event.preventDefault();
          event.returnValue = 'Changes you made may not be saved.';
          return 'Changes you made may not be saved.';
        }
      });

      await wasm.default();
    } catch (e) {
      if (status) status.textContent = 'Failed to start: ' + e;
      throw e;
    }
  }
}
