export interface ScriptsBridge {
  playground_list_files: () => string[];
  playground_read_file: (path: string) => string;
  playground_write_file: (path: string, text: string) => void;
  playground_script_errors: () => string[];
}

export interface ScriptsPanel {
  isDirty: () => boolean;
  enable: () => void;
}

export function createScriptsPanel(
  bridge: ScriptsBridge,
  registerFileChanges: (hook: (paths: string[]) => void) => void
): ScriptsPanel {
  const scriptSelect = document.getElementById('script-select') as HTMLSelectElement | null;
  const scriptSource = document.getElementById('script-source') as HTMLTextAreaElement | null;
  const scriptSaveButton = document.getElementById('script-save') as HTMLButtonElement | null;
  const scriptStatus = document.getElementById('script-status') as HTMLOutputElement | null;
  const scriptRuntimeErrors = document.getElementById('script-runtime-errors') as HTMLOutputElement | null;

  let currentPath = '';
  let lastSaved = '';
  let pollErrorsIntervalId = 0;
  let lastErrorsJoined = '';
  let enabled = false;
  // The exact text a failed list refresh wrote to the status, so a later successful refresh
  // clears that and nothing else: a load or save error belongs to the visitor until retried.
  let listError = '';

  const isDirty = (): boolean => {
    if (!scriptSource) return false;
    return scriptSource.value !== lastSaved;
  };

  const loadFile = (path: string) => {
    if (!scriptSource) return;
    try {
      const content = bridge.playground_read_file(path);
      scriptSource.value = content;
      lastSaved = content;
      currentPath = path;
      if (scriptStatus) {
        scriptStatus.textContent = '';
      }
    } catch (error) {
      // The browser has already moved the select; without this a later Save would write the
      // still-open file's text while the control names the one that failed to open.
      if (scriptSelect) scriptSelect.value = currentPath;
      if (scriptStatus) {
        scriptStatus.textContent = String(error);
      }
    }
  };

  const saveCurrent = () => {
    if (!scriptSource || !currentPath) return;
    const value = scriptSource.value;
    try {
      bridge.playground_write_file(currentPath, value);
      lastSaved = value;
      if (scriptStatus) {
        scriptStatus.textContent = 'saved — syntax OK; runtime errors show during Play';
      }
    } catch (error) {
      if (scriptStatus) {
        scriptStatus.textContent = String(error);
      }
    }
  };

  const pollRuntimeErrors = () => {
    try {
      const errors = bridge.playground_script_errors();
      const joined = errors && errors.length > 0 ? errors.join('\n') : '';
      if (joined !== lastErrorsJoined) {
        lastErrorsJoined = joined;
        if (scriptRuntimeErrors) {
          scriptRuntimeErrors.textContent = joined;
        }
      }
    } catch {
      // A throw here is the module not yet initialised; the next tick retries.
    }
  };

  if (scriptSelect) {
    scriptSelect.addEventListener('change', () => {
      const targetPath = scriptSelect.value;
      if (targetPath === currentPath) return;

      if (isDirty()) {
        const confirmed = window.confirm(
          'You have unsaved script changes. Discard them and switch files?'
        );
        if (!confirmed) {
          scriptSelect.value = currentPath;
          return;
        }
      }

      if (targetPath) {
        loadFile(targetPath);
      } else {
        currentPath = '';
        lastSaved = '';
        if (scriptSource) scriptSource.value = '';
        if (scriptStatus) scriptStatus.textContent = '';
      }
    });
  }

  if (scriptSaveButton) {
    scriptSaveButton.addEventListener('click', () => {
      saveCurrent();
    });
  }

  if (scriptSource) {
    scriptSource.addEventListener('keydown', (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && (event.key === 's' || event.key === 'S')) {
        event.preventDefault();
        saveCurrent();
      }
    });
  }

  // The drain reports the panel's own Save as a change too, so the open file's bytes are read
  // and compared first: a self-save or any no-op write leaves the textarea, its caret and
  // the saved message alone; only bytes that differ replace a clean buffer, and a dirty one
  // is kept and told.
  const followOpenFileChange = () => {
    if (!scriptSource) return;
    let onDisk = '';
    try {
      onDisk = bridge.playground_read_file(currentPath);
    } catch (error) {
      if (scriptStatus) scriptStatus.textContent = String(error);
      return;
    }
    if (onDisk === scriptSource.value) {
      lastSaved = onDisk;
      return;
    }
    if (isDirty()) {
      if (scriptStatus) scriptStatus.textContent = `${currentPath} changed on disk; your unsaved edits are kept — Save writes them over it`;
    } else {
      loadFile(currentPath);
    }
  };

  // A refresh runs in the middle of an editing session, so it never replaces or clears a
  // dirty buffer: the open file gone from the list keeps its text and path, and the status
  // line says so; only a clean buffer moves on or is blanked.
  const refreshList = (changedPaths: string[] = []) => {
    let files: string[] = [];
    try {
      files = bridge.playground_list_files() || [];
    } catch (error) {
      listError = String(error);
      if (scriptStatus) scriptStatus.textContent = listError;
      return;
    }
    if (listError && scriptStatus && scriptStatus.textContent === listError) scriptStatus.textContent = '';
    listError = '';

    const rhaiFiles = files
      .filter((file) => file.endsWith('.rhai'))
      .sort((first, second) => first.localeCompare(second));

    if (scriptSelect) {
      scriptSelect.innerHTML = '';
      for (const file of rhaiFiles) {
        const option = document.createElement('option');
        option.value = file;
        option.textContent = file;
        scriptSelect.appendChild(option);
      }
      scriptSelect.disabled = rhaiFiles.length === 0;
    }

    const openFileListed = rhaiFiles.includes(currentPath);
    if (currentPath && !openFileListed && isDirty()) {
      // Keep the edits: the select shows no entry for the file, the status says what Save
      // now does — the panel has no Save As, so Save recreates the path with these edits.
      if (scriptSelect) scriptSelect.value = '';
      if (scriptStatus) scriptStatus.textContent = `${currentPath} is no longer in the project; Save recreates it with your edits, or discard them`;
      return;
    }

    if (rhaiFiles.length > 0) {
      const nextPath = openFileListed ? currentPath : rhaiFiles[0];
      if (scriptSelect) {
        scriptSelect.value = nextPath;
      }
      if (nextPath !== currentPath) {
        loadFile(nextPath);
      } else if (changedPaths.includes(currentPath)) {
        followOpenFileChange();
      }
      if (scriptSource) scriptSource.disabled = false;
      if (scriptSaveButton) scriptSaveButton.disabled = false;
    } else {
      currentPath = '';
      lastSaved = '';
      if (scriptSource) {
        scriptSource.value = '';
        scriptSource.disabled = true;
      }
      if (scriptSaveButton) scriptSaveButton.disabled = true;
    }
  };

  registerFileChanges((paths) => {
    if (enabled && paths.some((path) => path.endsWith('.rhai'))) refreshList(paths);
  });

  const enable = () => {
    enabled = true;
    refreshList();
    if (!pollErrorsIntervalId) {
      pollErrorsIntervalId = window.setInterval(pollRuntimeErrors, 500);
    }
  };

  return {
    isDirty,
    enable,
  };
}
