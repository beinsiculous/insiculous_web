import assert from 'node:assert/strict';
import { createScriptsPanel } from '../src/scripts/playground-scripts-panel.ts';

class Element {
  value = '';
  textContent = '';
  disabled = false;
  children = [];
  listeners = new Map();
  set innerHTML(value) { this.children = []; }
  appendChild(child) { this.children.push(child); }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  click() { this.listeners.get('click')?.({}); }
}

function panelFixture() {
  const elements = new Map([
    'script-select', 'script-source', 'script-save', 'script-status', 'script-runtime-errors',
  ].map((name) => [name, new Element()]));
  globalThis.document = {
    getElementById: (name) => elements.get(name),
    createElement: () => new Element(),
  };
  let answer = true;
  globalThis.window = { setInterval: () => 1, confirm: () => answer };
  const files = new Map([['assets/scripts/old.rhai', 'original']]);
  const writes = [];
  let saveError = '';
  let fileChanges;
  const panel = createScriptsPanel({
    playground_list_files: () => [...files.keys()],
    playground_read_file: (path) => {
      assert.ok(files.has(path), `${path} exists`);
      return files.get(path);
    },
    playground_write_file: (path, text) => {
      if (saveError) throw Error(saveError);
      writes.push([path, text]);
      files.set(path, text);
    },
    playground_script_errors: () => [],
  }, (hook) => { fileChanges = hook; });
  // The stub bridge has no playground_set_file_mutation_guard: construction must not
  // reach for one, because the page registers the guard only once the module is live.
  assert.equal(typeof panel.fileMutationGuard, 'function');
  const mutationGuard = panel.fileMutationGuard;
  panel.enable();
  return {
    source: elements.get('script-source'),
    status: elements.get('script-status'),
    select: elements.get('script-select'),
    save: () => elements.get('script-save').click(),
    guard: (phase, removed = [], renamed = []) => mutationGuard(JSON.stringify({ phase, removed, renamed })),
    rawGuard: (json) => mutationGuard(json),
    setAnswer: (value) => { answer = value; },
    setSaveError: (message) => { saveError = message; },
    files, writes, fileChanges,
  };
}

const renames = [['assets/scripts/old.rhai', 'assets/scripts/new.rhai']];

{
  const fixture = panelFixture();
  fixture.source.value = 'edited before rename';
  assert.equal(fixture.guard('prepare', [], renames), '');
  assert.deepEqual(fixture.writes, [['assets/scripts/old.rhai', 'edited before rename']]);
  fixture.source.value = 'edited while moving';
  fixture.save();
  assert.equal(fixture.writes.length, 1, 'Prepare blocks intervening saves');
  assert.equal(fixture.guard('failed', [], renames), '');
  fixture.save();
  assert.deepEqual(fixture.writes.at(-1), ['assets/scripts/old.rhai', 'edited while moving']);
  assert.equal(fixture.select.value, 'assets/scripts/old.rhai', 'Failed keeps the old path');
}

{
  const fixture = panelFixture();
  assert.equal(fixture.guard('prepare', [], renames), '');
  fixture.files.set(renames[0][1], fixture.files.get(renames[0][0]));
  fixture.files.delete(renames[0][0]);
  assert.equal(fixture.guard('done', [], renames), '');
  fixture.source.value = 'after rename';
  fixture.save();
  assert.deepEqual(fixture.writes, [['assets/scripts/new.rhai', 'after rename']]);
  assert.equal(fixture.select.value, 'assets/scripts/new.rhai', 'Done follows the new path');
}

{
  const fixture = panelFixture();
  fixture.source.value = 'keep these edits';
  assert.match(fixture.guard('prepare', ['assets/scripts/old.rhai']), /unsaved script changes/);
  assert.equal(fixture.source.value, 'keep these edits');
  fixture.save();
  assert.deepEqual(fixture.writes, [['assets/scripts/old.rhai', 'keep these edits']], 'a refused delete never blocks Save');
}

{
  const fixture = panelFixture();
  fixture.source.value = 'dirty';
  fixture.setAnswer(false);
  assert.match(fixture.guard('prepare', [], renames), /rename cancelled/);
  assert.deepEqual(fixture.writes, []);
  fixture.setAnswer(true);
  fixture.setSaveError('syntax error');
  assert.match(fixture.guard('prepare', [], renames), /syntax error/);
  fixture.setSaveError('');
  fixture.save();
  assert.deepEqual(fixture.writes, [['assets/scripts/old.rhai', 'dirty']]);
}

{
  const fixture = panelFixture();
  assert.equal(fixture.guard('prepare', ['assets/scripts/old.rhai']), '');
  fixture.files.delete('assets/scripts/old.rhai');
  assert.equal(fixture.guard('done', ['assets/scripts/old.rhai']), '');
  assert.equal(fixture.source.value, '', 'a clean deleted script clears on Done');
  fixture.fileChanges(['assets/scripts/old.rhai']);
  fixture.save();
  assert.deepEqual(fixture.writes, [], 'the deleted path is never recreated by Save');
}

{
  const fixture = panelFixture();
  assert.equal(fixture.guard('prepare', [], renames), '');
  fixture.source.value = 'typed between the phases';
  fixture.save();
  assert.match(fixture.status.textContent, /file change is in progress/, 'a blocked Save says so');
  assert.deepEqual(fixture.writes, []);
  assert.equal(fixture.guard('failed', [], renames), '');
}

{
  const fixture = panelFixture();
  for (const payload of ['null', '{"phase":"prepare","renamed":[]}',
    '{"phase":"done","removed":[],"renamed":null}', '{"phase":"later","removed":[],"renamed":[]}',
    '{"phase":"prepare","removed":[1],"renamed":[]}', '{"phase":"prepare","removed":[],"renamed":[["a"]]}']) {
    assert.match(fixture.rawGuard(payload), /invalid file change/, payload);
  }
  fixture.source.value = 'still saveable';
  fixture.save();
  assert.deepEqual(fixture.writes, [['assets/scripts/old.rhai', 'still saveable']], 'a refused payload blocks nothing');
}

{
  const fixture = panelFixture();
  assert.equal(fixture.guard('prepare', [], renames), '');
  fixture.files.set(renames[0][1], fixture.files.get(renames[0][0]));
  fixture.files.delete(renames[0][0]);
  assert.match(fixture.rawGuard('{"phase":"done","removed":[]}'), /invalid file change/);
  fixture.source.value = 'after a done the page could not fully read';
  fixture.save();
  assert.deepEqual(fixture.writes, [['assets/scripts/new.rhai', 'after a done the page could not fully read']],
    'an unreadable done still moves the save target to the rename it accepted');
  assert.equal(fixture.select.value, 'assets/scripts/new.rhai');
  assert.equal(fixture.guard('prepare', [], [['assets/scripts/new.rhai', 'assets/scripts/newer.rhai']]), '',
    'and the next mutation is not refused as still in progress');
  assert.equal(fixture.guard('failed', [], [['assets/scripts/new.rhai', 'assets/scripts/newer.rhai']]), '');
}

{
  const fixture = panelFixture();
  assert.equal(fixture.guard('prepare', ['assets/scripts/old.rhai']), '');
  fixture.files.delete('assets/scripts/old.rhai');
  assert.match(fixture.rawGuard('{"phase":"done"}'), /invalid file change/);
  assert.equal(fixture.source.value, '', 'an unreadable done after a delete still lets the open script go');
  fixture.save();
  assert.deepEqual(fixture.writes, [], 'the deleted path is not recreated by Save');
}

{
  const fixture = panelFixture();
  fixture.files.set('assets/scripts/other.rhai', 'other');
  assert.equal(fixture.guard('prepare', [], renames), '');
  fixture.select.value = 'assets/scripts/other.rhai';
  fixture.select.listeners.get('change')();
  fixture.source.value = 'edited other';
  fixture.files.set(renames[0][1], fixture.files.get(renames[0][0]));
  fixture.files.delete(renames[0][0]);
  assert.equal(fixture.guard('done', [], renames), '');
  assert.equal(fixture.select.value, 'assets/scripts/other.rhai', 'Done leaves a script opened meanwhile alone');
  fixture.save();
  assert.deepEqual(fixture.writes, [['assets/scripts/other.rhai', 'edited other']], 'and Save writes it, never the renamed file');
}

console.log('Scripts panel mutation guard: 10 scenarios passed');
