// The assistant-workspace file rows as DOM (name · size · Copy · Download) and the "download all" helper —
// shared by the Profile page (the whole file set) and the two assistant pages (the spreadsheet / meal-plan guide rows).
// DOM only, like allocation-bars.js; the file set itself comes from workspace-docs.js.
import { copyText, downloadText } from "./download.js";

export const DOWNLOAD_SPACING_MILLISECONDS = 300;

/** "1.2 kB" / "532 B" for a text's UTF-8 size. */
export function formatSize(text) {
  const bytes = new TextEncoder().encode(text).length;
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} kB`;
}

/** One workspace file ({fileName, text, mediaType}) as a row: name · size · Copy · Download. */
export function renderFileRow(entry) {
  const row = document.createElement("div");
  row.className = "file-row";
  const name = document.createElement("code");
  name.textContent = entry.fileName;
  const size = document.createElement("span");
  size.className = "muted";
  size.textContent = formatSize(entry.text);
  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.textContent = "Copy";
  copyButton.addEventListener("click", async () => {
    try {
      await copyText(entry.text);
      copyButton.textContent = "Copied";
      setTimeout(() => { copyButton.textContent = "Copy"; }, 1500);
    } catch (error) {
      alert(`Copy failed: ${error.message}`);
    }
  });
  const downloadButton = document.createElement("button");
  downloadButton.type = "button";
  downloadButton.textContent = "Download";
  downloadButton.addEventListener("click", () => downloadText(entry.fileName, entry.text, entry.mediaType));
  row.append(name, size, copyButton, downloadButton);
  return row;
}

/** Download every document, spaced out so browsers that throttle multiple downloads still take them all. */
export function downloadAll(documents) {
  documents.forEach((entry, index) => {
    setTimeout(() => downloadText(entry.fileName, entry.text, entry.mediaType), index * DOWNLOAD_SPACING_MILLISECONDS);
  });
}
