/**
 * The message contract between the editor page and the preview window it opens,
 * imported by both sides so one file defines the shapes.
 *
 * Every launch carries a GENERATION: a counter in the editor, put on the preview's
 * URL and repeated on every message. A message whose generation is not the current
 * one is ignored on both sides, which is what makes a late answer from a window the
 * user already closed harmless.
 *
 * There is deliberately no heartbeat. A hidden window's timers are throttled to about
 * one wake a minute, so silence cannot distinguish a dead preview from a sleeping one;
 * releasing the reservation on silence would let two simulations run at once.
 */

export const PREVIEW_STORAGE_KEY = 'beinsiculous.playground.preview';

/** The editor's own boot deadline for a launch, and the preview's for a snapshot. */
export const PREVIEW_BOOT_DEADLINE_MS = 20_000;
export const PREVIEW_SNAPSHOT_DEADLINE_MS = 15_000;

/** How often the editor asks whether the window it opened has been closed. */
export const PREVIEW_CLOSED_POLL_MS = 1_000;

export type PreviewMessage =
  | { type: 'preview-ready'; generation: number }
  | {
      type: 'preview-snapshot';
      generation: number;
      title: string;
      sceneEntry: string;
      bytes: Uint8Array;
    }
  | { type: 'preview-loaded'; generation: number }
  | { type: 'preview-failed'; generation: number; error: string }
  | { type: 'preview-closed'; generation: number };

export type PreviewMessageType = PreviewMessage['type'];

/** What the editor remembers about a preview it opened, so a reload can re-take it. */
export interface PreviewReservation {
  windowName: string;
  tabId: string;
}

/**
 * This tab's identity, kept in `window.name` rather than `sessionStorage`: a duplicated
 * tab copies session storage but starts with an empty name, so only `window.name` can
 * tell the original tab from its copy. Minted once, and a reload keeps it.
 */
export function ownTabId(): string {
  if (!window.name) {
    window.name = `playground-tab-${Math.random().toString(36).slice(2, 10)}`;
  }
  return window.name;
}

/**
 * One preview window per tab. Two playground tabs must never share a name, or the second
 * would navigate the first's preview into a document whose opener check can never pass.
 */
export function previewWindowName(tabId: string): string {
  return `playground-preview-${tabId}`;
}

export function previewUrl(generation: number): string {
  return `/playground/preview/?mode=preview&generation=${generation}`;
}

export function readReservation(): PreviewReservation | null {
  try {
    const raw = window.sessionStorage.getItem(PREVIEW_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    const { windowName, tabId } = parsed as Partial<PreviewReservation>;
    if (typeof windowName !== 'string' || typeof tabId !== 'string') return null;
    return { windowName, tabId };
  } catch {
    // Storage a browser refuses, or a value some other version wrote: no reservation.
    return null;
  }
}

export function writeReservation(reservation: PreviewReservation): void {
  try {
    window.sessionStorage.setItem(PREVIEW_STORAGE_KEY, JSON.stringify(reservation));
  } catch {
    // Losing the key costs a re-take after a reload, not the launch in hand.
  }
}

export function clearReservation(): void {
  try {
    window.sessionStorage.removeItem(PREVIEW_STORAGE_KEY);
  } catch {
    // As above.
  }
}

/**
 * A message is ours only when it came from this origin, from the window we are talking
 * to, and carries the generation in flight. The caller supplies the expected source
 * because the two sides disagree on what it is: the opener, or the window it opened.
 */
export function acceptedMessage(
  event: MessageEvent,
  expectedSource: Window | null,
  currentGeneration: number
): PreviewMessage | null {
  if (event.origin !== window.location.origin) return null;
  if (!expectedSource || event.source !== expectedSource) return null;
  const data = event.data as Partial<PreviewMessage> | null;
  if (!data || typeof data !== 'object') return null;
  if (typeof data.type !== 'string' || typeof data.generation !== 'number') return null;
  if (data.generation !== currentGeneration) return null;
  return data as PreviewMessage;
}
