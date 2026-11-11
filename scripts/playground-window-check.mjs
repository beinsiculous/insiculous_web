// The editor window's browser test: real Web Locks and real IndexedDB, several pages in one
// browser context, over the built site (`npm run build` first). It boots the real playground
// bundle, so it needs WebGPU; headless Chromium gets it from SwiftShader with the flags below,
// which the audit browsers do not have — that is why this is not a step of `npm run verify`.
//
// Usage:  node scripts/playground-window-check.mjs                      (every scenario)
//         WINDOW_ONLY=fence node scripts/playground-window-check.mjs   (names containing "fence")
//
// Each scenario runs in a fresh context, so its store and its locks are its own.
//
// What this browser cannot do is named, not faked. Headless Chromium destroys the WebGPU
// device a few frames after the editor boots — every bundle, the games' included — and the
// engine stops its frame loop on a lost device, so nothing that needs a frame runs here: a
// command's answer (the move's barrier), a scene save, an export. Saves below go through the
// Scripts panel, whose write is synchronous and needs no frame, and archives are built from the
// bundle's own files. The scenarios that need frames are listed at the end as Jesse's check,
// with the blocked-popup paths and the game page's window.

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "playwright";
import { serveDist } from "./lib/serve-dist.mjs";

const DIST = resolve(import.meta.dirname, "..", "dist");
const BOOT_TIMEOUT_MS = 180_000;
const ANSWER_TIMEOUT_MS = 30_000;
const SCRIPT = "assets/scripts/paddle.rhai";
const only = process.env.WINDOW_ONLY;

const { server, port } = await serveDist(DIST);
const origin = `http://localhost:${port}`;
const browser = await chromium.launch({
  channel: "chromium",
  headless: true,
  args: ["--enable-unsafe-webgpu", "--use-vulkan=swiftshader", "--enable-features=Vulkan", "--ignore-gpu-blocklist"],
});

/** The bundled pong as an exported archive would carry it: `project.ron` beside its `assets/`. */
function pongArchive() {
  const directory = mkdtempSync(join(tmpdir(), "playground-window-"));
  const archive = join(directory, "pong.zip");
  execFileSync("python3", [
    "-c",
    `import pathlib, sys, zipfile
root = pathlib.Path(sys.argv[1])
manifest = '(slug: "pong", title: "Pong", bundle_version: "v6", content_hash: "", origin: bundled)'
with zipfile.ZipFile(sys.argv[2], "w", zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("project.ron", manifest)
    for path in sorted(root.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(root.parent).as_posix())`,
    join(DIST, "playground", "v6", "assets", "projects", "pong", "assets"),
    archive,
  ]);
  return archive;
}

/** A context whose pages never meet the first-achievement profile dialog. */
async function freshContext() {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await context.addInitScript(() => {
    try {
      localStorage.setItem("beinsiculous.achievements.profile-prompt", "dismissed");
    } catch {
      // A page without storage has no dialog to dismiss either.
    }
  });
  return context;
}

async function open(context, path) {
  const page = await context.newPage();
  await page.goto(`${origin}${path}`);
  return page;
}

/** The editor is up: the engine dispatched `playground-ready`, which enables Save. */
async function ready(page) {
  await page.waitForFunction(() => document.getElementById("save-button")?.disabled === false, null, {
    timeout: BOOT_TIMEOUT_MS,
  });
}

async function ownerCard(page) {
  await page.waitForFunction(() => document.getElementById("owner-card")?.hidden === false, null, {
    timeout: ANSWER_TIMEOUT_MS,
  });
  return page.evaluate(() => document.getElementById("owner-card").textContent.replace(/\s+/g, " "));
}

/** The boot status's text as written — its CSS upper-cases what `innerText` would read. */
async function bootStatus(page, pattern) {
  await page.waitForFunction(
    (source) => new RegExp(source).test(document.getElementById("game-loading")?.textContent ?? ""),
    pattern.source,
    { timeout: BOOT_TIMEOUT_MS }
  );
  return page.evaluate(() => document.getElementById("game-loading").textContent);
}

/** Open `path` in the Scripts panel, append a comment line, and save it unless told not to. */
async function editScript(page, path, line, { save = true } = {}) {
  await page.evaluate(
    ({ path, line, save }) => {
      const select = document.getElementById("script-select");
      if (select.value !== path) {
        select.value = path;
        select.dispatchEvent(new Event("change"));
      }
      const source = document.getElementById("script-source");
      source.value = `${source.value}\n// ${line}\n`;
      if (save) document.getElementById("script-save").click();
    },
    { path, line, save }
  );
}

async function saveStatus(page, expected) {
  await page.waitForFunction((text) => document.getElementById("save-status")?.textContent === text, expected, {
    timeout: ANSWER_TIMEOUT_MS,
  });
}

/** Write raw records into the playground's IndexedDB from a page that runs no engine. */
async function writeRawRecords(page, { files = [], projects = [] }) {
  await page.evaluate(
    async ({ files, projects }) => {
      const database = await new Promise((done, fail) => {
        const request = indexedDB.open("beinsiculous.playground", 1);
        request.onupgradeneeded = () => {
          request.result.createObjectStore("files", { keyPath: ["project", "path"] });
          request.result.createObjectStore("projects", { keyPath: "slug" });
        };
        request.onsuccess = () => done(request.result);
        request.onerror = () => fail(request.error);
      });
      await new Promise((done, fail) => {
        const transaction = database.transaction(["files", "projects"], "readwrite");
        for (const file of files) transaction.objectStore("files").put(file);
        for (const project of projects) transaction.objectStore("projects").put(project);
        transaction.oncomplete = done;
        transaction.onerror = () => fail(transaction.error);
      });
      database.close();
    },
    { files, projects }
  );
}

async function readRawRecords(page) {
  return page.evaluate(async () => {
    const database = await new Promise((done, fail) => {
      const request = indexedDB.open("beinsiculous.playground", 1);
      request.onsuccess = () => done(request.result);
      request.onerror = () => fail(request.error);
    });
    const all = (store) =>
      new Promise((done) => {
        const request = database.transaction(store).objectStore(store).getAll();
        request.onsuccess = () => done(request.result);
      });
    const records = { files: await all("files"), projects: await all("projects") };
    database.close();
    return JSON.stringify(records);
  });
}

const bytesOf = (text) => Array.from(new TextEncoder().encode(text));

const results = [];
async function scenario(name, body) {
  if (only && !name.includes(only)) return;
  const context = await freshContext();
  const started = Date.now();
  try {
    await body(context);
    results.push({ name, outcome: "run: passed", seconds: (Date.now() - started) / 1000 });
  } catch (error) {
    results.push({ name, outcome: `run: failed — ${error.message.split("\n")[0]}`, seconds: (Date.now() - started) / 1000 });
  } finally {
    await context.close();
  }
}

try {
  await scenario("a second tab on the same project meets the owner card", async (context) => {
    const first = await open(context, "/playground/?project=pong");
    await ready(first);
    const second = await open(context, "/playground/?project=pong");
    assert.match(await ownerCard(second), /“pong” is open in another tab or window/);
    assert.equal(await second.locator(".playground-embed .stage").isHidden(), true, "the engine never started");
  });

  await scenario("/playground/ and /playground/?project=<first slug> meet the same lock", async (context) => {
    const bare = await open(context, "/playground/");
    await ready(bare);
    assert.ok(bare.url().includes("?project=examples"), `the slug is written before the boot: ${bare.url()}`);
    const named = await open(context, "/playground/?project=examples");
    assert.match(await ownerCard(named), /“examples”/);
  });

  await scenario("the way back: Bring the editor back here with the window open meets the owner card after its retries, and Try again starts once it is closed", async (context) => {
    const editorWindow = await open(context, "/playground/window/?project=pong&move=1");
    await ready(editorWindow);
    assert.ok(!editorWindow.url().includes("move=1"), `move is stripped at playground-ready: ${editorWindow.url()}`);
    assert.equal(await editorWindow.locator("#window-button").count(), 0, "the window has no Open in a window");
    assert.match(await editorWindow.locator(".bar-controls").innerText(), /To move the editor back: close this window/);
    const parked = await open(context, "/playground/parked/?project=pong");
    assert.match(await parked.locator("#parked-moved").innerText(), /open in its own window/);
    const started = Date.now();
    await parked.click("#parked-return");
    assert.match(await ownerCard(parked), /“pong” is open in another tab or window/);
    assert.ok(Date.now() - started >= 4_000, "the move boot asked for its 5 s first");
    await editorWindow.close();
    await parked.click("#owner-card-retry");
    await ready(parked);
  });

  await scenario("a page whose engine fell back to the memory store has the button disabled, and a move boot there stops", async (context) => {
    await context.addInitScript(() => {
      Object.defineProperty(window, "indexedDB", { get: () => undefined });
    });
    const page = await open(context, "/playground/?project=examples");
    await ready(page);
    assert.equal(await page.locator("#window-button").isDisabled(), true);
    assert.match(await page.locator("#window-note").innerText(), /not keeping your edits/);
    const destination = await open(context, "/playground/?project=pong&move=1");
    assert.match(await bootStatus(destination, /Startup failed/), /This window could not open your saved project/);
  });

  await scenario("an unsaved script refuses the move before any window opens", async (context) => {
    const page = await open(context, "/playground/?project=pong");
    await ready(page);
    await editScript(page, SCRIPT, "not saved", { save: false });
    await page.click("#window-button");
    await page.waitForFunction(
      () => document.getElementById("window-note")?.textContent === "Save first — the window opens the saved project",
      null,
      { timeout: ANSWER_TIMEOUT_MS }
    );
    assert.equal(context.pages().length, 1, "no window was opened");
  });

  await scenario("fence: an archive naming a project open in another tab is refused", async (context) => {
    const holder = await open(context, "/playground/?project=pong");
    await ready(holder);
    const importer = await open(context, "/playground/?project=examples");
    await ready(importer);
    await importer.setInputFiles("#import-input", pongArchive());
    await importer.waitForFunction(
      () => /“pong” is open in another tab or window — close it before importing over it/.test(
        document.getElementById("playground-banner")?.textContent ?? ""
      ),
      null,
      { timeout: ANSWER_TIMEOUT_MS }
    );
    assert.ok(importer.url().includes("?project=examples"), "the importing page stayed");
  });

  await scenario("store: a file record with malformed metadata and intact bytes stops the boot and is byte-identical afterwards", async (context) => {
    const seed = await open(context, "/playground/parked/");
    await writeRawRecords(seed, {
      projects: [{ slug: "pong", title: "Pong", bundle_version: "v6", content_hash: "", origin: "saved" }],
      files: [{
        project: "pong",
        path: "assets/scenes/pong.scene.ron",
        bytes: bytesOf("the visitor's own scene"),
        revision: "one",
        bundle_version: "v6",
        deleted: false,
      }],
    });
    const before = await readRawRecords(seed);
    const page = await open(context, "/playground/?project=pong");
    assert.match(await bootStatus(page, /Startup failed/), /could not be read/);
    assert.equal(await readRawRecords(seed), before);
  });

  await scenario("store: an imported-only project whose own manifest is undecodable stops the boot with its URL unchanged and its files intact", async (context) => {
    const seed = await open(context, "/playground/parked/");
    await writeRawRecords(seed, {
      projects: [{ slug: "mine", title: 5, bundle_version: "v6", content_hash: "", origin: "imported" }],
      files: [{
        project: "mine",
        path: "assets/scenes/main.scene.ron",
        bytes: bytesOf("SceneData(name: \"mine\")"),
        revision: 1,
        bundle_version: "v6",
        deleted: false,
      }],
    });
    const before = await readRawRecords(seed);
    const page = await open(context, "/playground/?project=mine");
    assert.match(await bootStatus(page, /Startup failed/), /may be "mine"/);
    assert.ok(page.url().includes("?project=mine"), `never redirected: ${page.url()}`);
    assert.equal(await readRawRecords(seed), before);
    const other = await open(context, "/playground/?project=pong");
    await ready(other);
    assert.equal(await readRawRecords(seed), before, "another project opens, and no sweep ran");
  });

  await scenario("store: a page holding a project at revision 1 gets StaleRevision after another page imports over it", async (context) => {
    const holder = await open(context, "/playground/?project=pong");
    await ready(holder);
    await editScript(holder, SCRIPT, "saved at revision 1");
    await saveStatus(holder, "Saved in this browser");
    // A page from the release before the lock: it asks for none, so nothing fences its import.
    const older = await context.newPage();
    await older.addInitScript(() => {
      Object.defineProperty(Navigator.prototype, "locks", { get: () => undefined });
    });
    await older.goto(`${origin}/playground/?project=examples`);
    await ready(older);
    await older.setInputFiles("#import-input", pongArchive());
    await older.waitForURL((url) => url.href.includes("?project=pong"), { timeout: ANSWER_TIMEOUT_MS });
    await editScript(holder, SCRIPT, "saved over the import");
    await saveStatus(holder, `Save failed — conflicted: ${SCRIPT}`);
  });
} finally {
  await browser.close();
  server.close();
}

const jessesCheck = [
  "the move: page A boots, edits, saves; Open in a window; the window shows the saved edit and A is the parked card; the window edits, saves and is closed; Bring the editor back here shows the window's edit",
  "the move made with the source tab hidden the moment the window opens (the barrier must not need a frame)",
  "a command batch left open refuses the move",
  "a failed read inside the sweep deletes nothing (real records cannot reach it: the strict manifest read stops the boot first)",
  "the blocked-popup path on both surfaces, and the game page's independent window",
];
for (const { name, outcome, seconds } of results) console.log(`${outcome}  ${name}  (${seconds.toFixed(1)} s)`);
for (const name of jessesCheck) console.log(`not run: Jesse's check  ${name}`);
const failed = results.filter((result) => result.outcome !== "run: passed");
console.log(`editor window browser test: ${results.length - failed.length} of ${results.length} run passed; ${jessesCheck.length} left for Jesse`);
process.exit(failed.length === 0 ? 0 : 1);
