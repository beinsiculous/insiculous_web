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

export function createScriptsPanel(bridge: ScriptsBridge): ScriptsPanel {
  const scriptSelect = document.getElementById('script-select') as HTMLSelectElement | null;
  const scriptSource = document.getElementById('script-source') as HTMLTextAreaElement | null;
  const scriptSaveButton = document.getElementById('script-save') as HTMLButtonElement | null;
  const scriptStatus = document.getElementById('script-status') as HTMLOutputElement | null;
  const scriptRuntimeErrors = document.getElementById('script-runtime-errors') as HTMLOutputElement | null;

  let currentPath = '';
  let lastSaved = '';
  let pollErrorsIntervalId = 0;
  let lastErrorsJoined = '';

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

  const enable = () => {
    let files: string[] = [];
    try {
      files = bridge.playground_list_files() || [];
    } catch {
      files = [];
    }

    const rhaiFiles = files
      .filter((file) => file.endsWith('.rhai'))
      .sort((a, b) => a.localeCompare(b));

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

    if (rhaiFiles.length > 0) {
      const first = rhaiFiles[0];
      if (scriptSelect) {
        scriptSelect.value = first;
      }
      loadFile(first);
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

    if (!pollErrorsIntervalId) {
      pollErrorsIntervalId = window.setInterval(pollRuntimeErrors, 500);
    }
  };

  return {
    isDirty,
    enable,
  };
}
