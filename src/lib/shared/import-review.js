// The review a person reads after applying an import document: readable tables of what landed
// (commitments, tasks), what their assistant skipped and why, its review lines, and anything the app
// could not read. DOM only — the rows come from importReviewRows() (import-document.js). Shared by the
// Questionnaire (Startup 2 shows what was applied) and Assistant (where it is applied) pages.
import { importReviewRows } from "./import-document.js";
import { copyText } from "./download.js";

function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function table(headings, rows) {
  const node = element("table", "import-review-table");
  const head = element("thead");
  const headRow = element("tr");
  for (const heading of headings) headRow.appendChild(element("th", null, heading));
  head.appendChild(headRow);
  node.appendChild(head);
  const body = element("tbody");
  for (const row of rows) {
    const tableRow = element("tr");
    row.forEach((cell, index) => tableRow.appendChild(element(index === 0 ? "th" : "td", null, cell)));
    body.appendChild(tableRow);
  }
  node.appendChild(body);
  return node;
}

function list(items, className) {
  const node = element("ul", className);
  for (const item of items) node.appendChild(element("li", null, item));
  return node;
}

/** Render the review of `importDocument` into `container` (emptied first). `extraProblems` are the app's own
 *  rejections (duplicates, invalid canonical records) shown beside the parse problems. `listApplied: false` leaves
 *  out the commitments and tasks tables (for a page that already lists them) and keeps skipped / review / problems. */
export function renderImportReview(container, importDocument, categories, extraProblems = [], { listApplied = true } = {}) {
  container.replaceChildren();
  if (!importDocument) return;
  const rows = importReviewRows(importDocument, categories);
  const problems = [...rows.problems, ...extraProblems];
  const sections = [];
  if (listApplied && rows.commitments.length) {
    sections.push(element("h3", null, `Commitments (${rows.commitments.length})`));
    sections.push(table(["What", "Repeats", "Starts", "Lasts", "Category"], rows.commitments.map((row) => [row.title, row.repeats, row.start, row.lasts, row.category])));
  }
  if (listApplied && rows.tasks.length) {
    sections.push(element("h3", null, `Tasks (${rows.tasks.length})`));
    sections.push(table(["What", "Repeats", "When", "Lasts", "Category"], rows.tasks.map((row) => [row.title, row.repeats, row.when, row.lasts, row.category])));
  }
  if (rows.skipped.length) {
    sections.push(element("h3", null, `Skipped by your assistant (${rows.skipped.length})`));
    sections.push(table(["What", "Why"], rows.skipped.map((row) => [row.title, row.why])));
  }
  if (rows.review.length) {
    sections.push(element("h3", null, "Your assistant's review"));
    sections.push(list(rows.review, "import-review-lines"));
  }
  if (problems.length) {
    sections.push(element("h3", "import-review-problems", `Not applied (${problems.length})`));
    sections.push(list(problems, "import-review-lines import-review-problems"));
    sections.push(retryBox(retryMessage(problems, importDocument)));
  }
  if (!sections.length) {
    if (listApplied) container.appendChild(element("p", "muted", "This document lists no commitments or tasks."));
    return;
  }
  for (const section of sections) container.appendChild(section);
}

/** The status sentence after Apply: "Applied 5 commitments (2 new), 2 tasks from google-calendar (2 skipped by your assistant; 1 not applied)." */
export function importSummary(merged, importDocument) {
  const counted = (count, added, noun) => `${count} ${noun}${count === 1 ? "" : "s"}${count !== added ? ` (${added} new)` : ""}`;
  const applied = [counted(merged.listed, merged.added, "commitment"), ...(merged.tasksListed ? [counted(merged.tasksListed, merged.tasksAdded, "task")] : []), ...merged.applied];
  const asides = [];
  if (merged.skipped) asides.push(`${merged.skipped} skipped by your assistant`);
  if (merged.rejected.length) asides.push(`${merged.rejected.length} not applied`);
  if (merged.ignored.length) asides.push(`not yet used: ${merged.ignored.join(", ")}`);
  const sourceWords = importDocument.source?.kind ? ` from ${importDocument.source.kind}` : "";
  return `Applied ${applied.join(", ")}${sourceWords}${asides.length ? ` (${asides.join("; ")})` : ""}.`;
}

/** The message the person pastes back into the chat they used, so the assistant can fix and resend: the
 *  problems as the app reported them plus the offending records (matched by the title the problem names). */
export function retryMessage(problems, importDocument) {
  const lines = ["FortKnight could not apply these entries of the import document you wrote for me:", ""];
  for (const problem of problems) lines.push(`- ${problem}`);
  const offending = [];
  for (const problem of problems) {
    const match = /^(commitments|tasks) #\d+ "((?:[^"\\]|\\.)*)":/.exec(problem);
    if (!match) continue;
    const listName = match[1];
    const title = JSON.parse(`"${match[2]}"`);
    for (const record of importDocument?.[listName] || []) {
      if (record?.title === title && !offending.some((entry) => entry.record === record)) offending.push({ listName, record });
    }
  }
  if (offending.length) {
    lines.push("", "The records as you wrote them:");
    for (const { listName, record } of offending) lines.push(`${listName}: ${JSON.stringify(record)}`);
  }
  lines.push("", "Please fix them (docs: import-from-spreadsheet.md §3 has the field grammar — repeats phrases, \"H:MM AM/PM\" times, \"1 h 30 min\" durations, weekday names, the seven categories) and send me the whole import document again as one JSON code block, schemaVersion 2, with everything else unchanged.");
  return lines.join("\n");
}

function retryBox(text) {
  const box = element("div", "retry-box");
  box.appendChild(element("p", "muted", "Paste this into the chat you got the document from and it can fix and resend the whole thing:"));
  const area = element("textarea", "retry-text");
  area.readOnly = true;
  area.rows = 6;
  area.value = text;
  area.addEventListener("focus", () => area.select());
  box.appendChild(area);
  const row = element("div", "button-row");
  const copy = element("button", null, "Copy for your assistant");
  copy.type = "button";
  copy.addEventListener("click", async () => {
    try {
      await copyText(text);
      copy.textContent = "Copied";
      setTimeout(() => { copy.textContent = "Copy for your assistant"; }, 1500);
    } catch (error) {
      area.select();
      copy.textContent = "Select and copy by hand";
    }
  });
  row.appendChild(copy);
  box.appendChild(row);
  return box;
}
