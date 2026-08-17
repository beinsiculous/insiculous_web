// Browser-only helpers for handing text to the person: save as a file, or copy to the clipboard.
export function downloadText(fileName, text, mediaType = "application/json") {
  const blob = new Blob([text], { type: mediaType });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 60_000); // Safari needs the URL alive until the download starts
}

export function copyText(text) {
  return navigator.clipboard.writeText(text);
}
