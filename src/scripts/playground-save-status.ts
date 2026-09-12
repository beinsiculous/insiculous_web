/**
 * The playground bar's save indicator: what this browser has done with the editor's
 * edits, read from the engine's `playground_save_state` once per poll.
 *
 * The output is a live region, so the text is written only when the reading changes,
 * and a save that lands inside the debounce window is never announced at all — a
 * Ctrl+S that completes in 50 ms should not make the bar say two things.
 */

export interface SaveStatusBridge {
  playground_save_state: () => string;
}

export interface SaveStatus {
  poll: () => void;
  current: () => string;
}

/** A save still running this long after it started is worth announcing. */
const SAVING_ANNOUNCE_MILLISECONDS = 400;

export function createSaveStatus(
  bridge: SaveStatusBridge,
  element: HTMLElement | null,
  extraDirty?: () => boolean
): SaveStatus {
  let lastText = '';
  let savingTimerId = 0;
  // Whether the saving period now open has armed its timer or already announced, so
  // the timer is armed once per period rather than re-armed on every poll.
  let savingAnnounced = false;

  const write = (text: string) => {
    if (text === lastText) return;
    lastText = text;
    if (element) element.textContent = text;
  };

  const textFor = (state: string, reason: string): string => {
    if (state === 'saved') return 'Saved in this browser';
    if (state === 'unsaved') return 'Unsaved changes';
    if (state === 'failed') return `Save failed — ${reason}`;
    return '';
  };

  const stillSaving = (): boolean => {
    try {
      const reading = JSON.parse(bridge.playground_save_state()) as { state?: unknown };
      return reading?.state === 'saving';
    } catch {
      // The next poll settles the correct reading either way.
      return false;
    }
  };

  const applyReading = (state: string, reason: string) => {
    if (state === 'saving') {
      if (!savingAnnounced && savingTimerId === 0) {
        savingTimerId = window.setTimeout(() => {
          savingTimerId = 0;
          // The save may have landed between the arming poll and this callback — a
          // stale "Saving…" would immediately be followed by "Saved", exactly the
          // double announcement the debounce exists to prevent. Re-read before writing.
          if (!stillSaving()) return;
          savingAnnounced = true;
          write('Saving…');
        }, SAVING_ANNOUNCE_MILLISECONDS);
      }
      return;
    }

    // Any other reading ends the saving period, which is what keeps a quick save from
    // ever being announced as one: the timer dies before it can write.
    savingAnnounced = false;
    if (savingTimerId !== 0) {
      window.clearTimeout(savingTimerId);
      savingTimerId = 0;
    }
    write(textFor(state, reason));
  };

  const poll = () => {
    let reading: unknown;
    try {
      reading = JSON.parse(bridge.playground_save_state());
    } catch {
      // A throw is the module not yet initialised, and an empty string is a
      // serialization that failed; the indicator keeps its last reading either way.
      return;
    }
    if (typeof reading !== 'object' || reading === null) return;

    const { state: rawState, reason } = reading as { state?: unknown; reason?: unknown };
    if (typeof rawState !== 'string') return;
    // The engine only knows its own scene state — edits sitting unsubmitted in the
    // Scripts panel's textarea are invisible to it, so "saved" would be a lie.
    const scriptsUnsaved = rawState === 'saved' && !!extraDirty && extraDirty();
    const state = scriptsUnsaved ? 'unsaved' : rawState;
    applyReading(state, typeof reason === 'string' ? reason : '');
  };

  return { poll, current: () => lastText };
}
