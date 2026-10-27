/**
 * Import one song (.mid), sample (.wav) or SoundFont (.sf2) into the open project.
 *
 * The bridge checks the file whole before it writes anything — its name, its size against
 * the loader's limit, then the loader itself — and answers where the file went. A taken
 * name is written only after the visitor confirms, the prompt naming every song whose
  * sidecar uses the file and, for a song, the sidecar the replacement loses. A song is then
 * opened in the composer through the command API — whose answer lands in the command output,
 * so a dirty song's refusal is read there, not here; a sample or a SoundFont is announced as
 * reachable from Assets after Rescan. One import runs at a time.
 */

export interface FileImportBridge {
  playground_write_file_bytes: (name: string, bytes: Uint8Array, replace: boolean) => string;
  playground_dispatch: (line: string) => boolean;
}

export interface FileImport {
  enable: () => void;
}

/** What the bridge answers for an import, as `crate::upload::UploadOutcome` serializes it. */
interface UploadOutcome {
  written: boolean;
  kind: 'Song' | 'Sample' | 'SoundFont';
  destination: string;
  referenced_by: string[];
  sidecar_lost: boolean;
}

/** The question asked before a taken name is replaced. */
function replacePrompt(outcome: UploadOutcome): string {
  const lines = [`${outcome.destination} already exists. Replace it?`];
  if (outcome.referenced_by.length > 0) {
    lines.push(`Songs that use it: ${outcome.referenced_by.join(', ')}.`);
  }
  if (outcome.sidecar_lost) {
    lines.push(
      `Its song file ${outcome.destination}.ron will be removed: that song's bindings and instruments will be lost.`
    );
  }
  return lines.join('\n\n');
}

export function createFileImport(bridge: FileImportBridge): FileImport {
  const input = document.getElementById('import-file-input') as HTMLInputElement | null;
  const status = document.getElementById('import-file-status') as HTMLOutputElement | null;
  const say = (message: string) => {
    if (status) status.textContent = message;
  };

  if (input) {
    input.addEventListener('change', async () => {
      const file = input.files?.[0];
      if (!file) return;
      input.disabled = true;
      try {
        const bytes = new Uint8Array(await file.arrayBuffer());
        let outcome = JSON.parse(bridge.playground_write_file_bytes(file.name, bytes, false)) as UploadOutcome;
        if (!outcome.written) {
          if (!window.confirm(replacePrompt(outcome))) {
            say(`${file.name} was not imported: ${outcome.destination} kept as it was`);
            return;
          }
          outcome = JSON.parse(bridge.playground_write_file_bytes(file.name, bytes, true)) as UploadOutcome;
        }
        const assetPath = outcome.destination.replace(/^assets\//, '');
        if (outcome.kind === 'Song') {
          // Quoted: the command API's tokenizer splits on spaces outside double quotes. The
          // answer lands in the command output, so a dirty song's refusal is read there.
          const queued = bridge.playground_dispatch(`song open "${assetPath}"`);
          say(
            queued
              ? `${file.name} imported to ${assetPath}; the composer opens it unless a song with unsaved edits is open — the command output says so`
              : `${file.name} imported to ${assetPath} — open it from the composer's Songs list`
          );
        } else {
          const what = outcome.kind === 'Sample' ? 'sample' : 'SoundFont';
          say(`${file.name} imported as a ${what} at ${assetPath} — find it in Assets after Rescan`);
        }
      } catch (error) {
        say(String(error));
      } finally {
        input.disabled = false;
        input.value = '';
      }
    });
  }

  return {
    enable: () => {
      if (input) input.disabled = false;
    },
  };
}
