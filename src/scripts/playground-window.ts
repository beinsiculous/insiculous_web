/**
 * *Open in a window ↗* — moving the Playground editor to a window of its own.
 *
 * The move is the project switch with a different destination: the page requires
 * everything saved, settles what the bridge already accepted, drains persistence
 * (`playground_open_project`, the switch's own drain), sends the window to the editor
 * and itself to a parked card. The window boots as any page does, under the project's
 * lock (`playground-project-lock.ts`). Nothing is handed between pages: no message, no
 * named window, no queue. The way back is the visitor closing the window and pressing
 * *Bring the editor back here* on the parked card.
 *
 * No step waits on an animation frame: a popup that opens as a foreground tab hides
 * this one, and a hidden document's frames do not come. The barrier is a read-only
 * command answered in the order the bridge accepted it, so its answer means every
 * command accepted before the click has run.
 */

/** How long the barrier's answer may take before the move gives up and closes the window. */
export const BARRIER_DEADLINE_MS = 5_000;
export const WINDOW_FEATURES = 'popup,width=1280,height=800';

export const NOTE_SAVE_FIRST = 'Save first — the window opens the saved project';
export const NOTE_IN_FLIGHT = 'Wait for the import to finish';
export const NOTE_PREVIEW_OPEN = 'Close the preview window first — it stays with this page';
export const NOTE_BARRIER_REFUSED = 'The editor is busy — try Open in a window again';
export const NOTE_BARRIER_SILENT = 'The editor did not answer — try Open in a window again';
export const NOTE_NO_STORAGE =
  'This browser is not keeping your edits, so the editor cannot move — it would lose them';
export const NOTE_NO_LOCKS =
  'This browser cannot keep a project to one page, so the editor cannot move to a window';

export function editorUrl(slug: string): string {
  return `/playground/?project=${encodeURIComponent(slug)}&move=1`;
}

export function windowUrl(slug: string): string {
  return `/playground/window/?project=${encodeURIComponent(slug)}&move=1`;
}

export function parkedUrl(slug: string): string {
  return `/playground/parked/?project=${encodeURIComponent(slug)}`;
}

/** Whether the button may be pressed, and what the bar says when it may not. */
export function windowButtonState(options: { holdsLock: boolean; storagePersists: boolean }): {
  enabled: boolean;
  note: string;
} {
  if (!options.holdsLock) return { enabled: false, note: NOTE_NO_LOCKS };
  if (!options.storagePersists) return { enabled: false, note: NOTE_NO_STORAGE };
  return { enabled: true, note: '' };
}

/** The part of a `Window` the move touches. */
export interface WindowHandle {
  readonly closed: boolean;
  close: () => void;
  location: { href: string };
}

export type BarrierAnswer = 'answered' | 'refused';

export type MoveOutcome =
  | 'refused-in-flight'
  | 'refused-dirty'
  | 'refused-preview'
  | 'blocked'
  | 'barrier-refused'
  | 'barrier-silent'
  | 'dirty-after-barrier'
  | 'drain-failed'
  | 'window-closed'
  | 'moved';

export interface MoveSteps {
  slug: string;
  isDirty: () => boolean;
  /** The imports, archive import, reset and switch still running. */
  inFlight: () => number;
  /**
   * Whether this page's Play preview is open. Its reservation names this tab, so the window
   * could not re-take it and its next Play would start a second simulation beside it.
   */
  previewOpen: () => boolean;
  /** Open the blank window; called synchronously, so the click's activation is spent here. */
  open: () => WindowHandle | null;
  /** Dispatch a read-only command and answer when its response arrives, or at once if refused. */
  barrier: () => Promise<BarrierAnswer>;
  drain: (slug: string) => Promise<unknown>;
  /** Replace this page's document. */
  navigate: (url: string) => void;
  wait: (milliseconds: number) => Promise<void>;
  barrierDeadlineMs: number;
  note: (text: string) => void;
  blocked: (shown: boolean) => void;
  panel: (shown: boolean) => void;
  banner: (text: string) => void;
  /** Called before this page navigates on purpose, so `beforeunload` does not ask. */
  leaving: () => void;
}

/** The click's four steps, in order: open → barrier → drain → the window's location → this page's. */
export async function moveToWindow(steps: MoveSteps): Promise<MoveOutcome> {
  if (steps.inFlight() > 0) {
    steps.note(NOTE_IN_FLIGHT);
    return 'refused-in-flight';
  }
  if (steps.isDirty()) {
    steps.note(NOTE_SAVE_FIRST);
    return 'refused-dirty';
  }
  if (steps.previewOpen()) {
    steps.note(NOTE_PREVIEW_OPEN);
    return 'refused-preview';
  }
  const handle = steps.open();
  if (!handle) {
    steps.blocked(true);
    return 'blocked';
  }
  steps.blocked(false);
  steps.note('');
  steps.panel(true);

  const giveUp = (note: string) => {
    handle.close();
    steps.panel(false);
    steps.note(note);
  };
  const answer = await Promise.race([
    steps.barrier(),
    steps.wait(steps.barrierDeadlineMs).then(() => 'silent' as const),
  ]);
  if (answer === 'refused') {
    giveUp(NOTE_BARRIER_REFUSED);
    return 'barrier-refused';
  }
  if (answer === 'silent') {
    giveUp(NOTE_BARRIER_SILENT);
    return 'barrier-silent';
  }
  if (steps.isDirty()) {
    giveUp(NOTE_SAVE_FIRST);
    return 'dirty-after-barrier';
  }

  try {
    await steps.drain(steps.slug);
  } catch (error) {
    handle.close();
    steps.panel(false);
    steps.banner(String(error));
    return 'drain-failed';
  }

  // From the drain on this page cannot save again: it leaves, as a project switch does.
  steps.leaving();
  if (!handle.closed) {
    try {
      handle.location.href = windowUrl(steps.slug);
      steps.navigate(parkedUrl(steps.slug));
      return 'moved';
    } catch {
      // A window the browser will not let this page navigate is no window to park behind.
      // Still the blank one this page opened, it is closed; one whose address cannot be
      // read has gone somewhere of the visitor's choosing and is left alone.
      try {
        if (handle.location.href === 'about:blank') handle.close();
      } catch {
        // Not this page's to close.
      }
    }
  }
  steps.navigate(editorUrl(steps.slug));
  return 'window-closed';
}

/**
 * The barrier through the command bridge: `selection` changes nothing, and the bridge
 * answers lines in the order it accepted them. `enqueue` files the answer's sink in the
 * page's response queue, so the queue stays aligned even if the move stops waiting.
 */
export function commandBarrier(
  dispatch: (line: string) => boolean,
  enqueue: (sink: (line: string) => void) => void
): Promise<BarrierAnswer> {
  return new Promise((resolve) => {
    if (!dispatch('selection')) {
      resolve('refused');
      return;
    }
    enqueue(() => resolve('answered'));
  });
}

/** The page's half: the button, its note, the blocked alert and the moving panel, by id. */
export function createWindowButton(options: {
  slug: () => string;
  isDirty: () => boolean;
  inFlight: () => number;
  previewOpen: () => boolean;
  barrier: () => Promise<BarrierAnswer>;
  drain: (slug: string) => Promise<unknown>;
  banner: HTMLElement | null;
  leaving: () => void;
}): { enable: (state: { holdsLock: boolean; storagePersists: boolean }) => void } {
  const button = document.getElementById('window-button') as HTMLButtonElement | null;
  const note = document.getElementById('window-note');
  const blocked = document.getElementById('window-blocked');
  const panel = document.getElementById('moving-panel');
  const reload = document.getElementById('moving-reload') as HTMLAnchorElement | null;
  // Everything the visitor could still submit through; the panel itself sits outside it.
  const underPanel = [document.querySelector('.bar-controls'), document.getElementById('main')];
  let moving = false;

  const move = async () => {
    if (moving) return;
    moving = true;
    try {
      await moveToWindow({
        ...options,
        slug: options.slug(),
        banner: (text) => {
          if (options.banner) options.banner.textContent = text;
        },
        open: () => window.open('about:blank', '_blank', WINDOW_FEATURES),
        navigate: (url) => window.location.replace(url),
        wait: (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds)),
        barrierDeadlineMs: BARRIER_DEADLINE_MS,
        note: (text) => {
          if (note) note.textContent = text;
        },
        blocked: (shown) => {
          if (blocked) blocked.hidden = !shown;
        },
        panel: (shown) => {
          if (reload) reload.href = window.location.pathname + window.location.search;
          for (const element of underPanel) if (element instanceof HTMLElement) element.inert = shown;
          if (panel) panel.hidden = !shown;
        },
      });
    } finally {
      moving = false;
    }
  };
  button?.addEventListener('click', () => void move());
  document.getElementById('window-retry')?.addEventListener('click', () => void move());

  return {
    enable(state) {
      const { enabled, note: reason } = windowButtonState(state);
      if (button) button.disabled = !enabled;
      if (note) note.textContent = reason;
    },
  };
}

/**
 * A Rust game's editor page: its window is a second, independent editor — a game page
 * stores nothing, so there is nothing to lock or park. Always a new, unnamed window, so a
 * second click never navigates one that holds unsaved edits. `false` when blocked.
 */
export function openIndependentWindow(
  open: (url: string, target: string, features: string) => unknown,
  href: string
): boolean {
  return open(href, '_blank', WINDOW_FEATURES) !== null;
}
