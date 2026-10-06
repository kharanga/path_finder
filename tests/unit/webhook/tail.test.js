import { test } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { readNewLines, tailFile, DEFAULT_POLL_MS } from "../../../webhook/tail.js";
import { makeTmpDir } from "../../helpers/tmp-dir.js";

const fileIn = (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  return join(path, "events.jsonl");
};

test("DEFAULT_POLL_MS is 300", () => {
  assert.equal(DEFAULT_POLL_MS, 300);
});

test("readNewLines splits complete lines and carries the partial tail", (t) => {
  const file = fileIn(t);
  writeFileSync(file, "a\nb\npartial");
  const first = readNewLines(file, 0);
  assert.deepEqual(first, { lines: ["a", "b"], offset: 11, carry: "partial", truncated: false, missing: false });
  appendFileSync(file, "-done\nc\n");
  const second = readNewLines(file, first.offset, first.carry);
  assert.deepEqual(second, { lines: ["partial-done", "c"], offset: 19, carry: "", truncated: false, missing: false });
});

test("readNewLines returns nothing new when the file has not grown", (t) => {
  const file = fileIn(t);
  writeFileSync(file, "a\n");
  const first = readNewLines(file, 0);
  assert.deepEqual(readNewLines(file, first.offset, first.carry), { lines: [], offset: 2, carry: "", truncated: false, missing: false });
});

test("readNewLines restarts from byte 0 and drops the carry when the file shrank", (t) => {
  const file = fileIn(t);
  writeFileSync(file, "a\nb\nhalf");
  const first = readNewLines(file, 0);
  writeFileSync(file, "z\n");
  const after = readNewLines(file, first.offset, first.carry);
  assert.deepEqual(after, { lines: ["z"], offset: 2, carry: "", truncated: true, missing: false });
});

test("readNewLines reports a missing file without changing the offset or carry", (t) => {
  const file = fileIn(t);
  assert.deepEqual(readNewLines(file, 5, "keep"), { lines: [], offset: 5, carry: "keep", truncated: false, missing: true });
});

test("readNewLines handles an empty file and a file with only a newline", (t) => {
  const file = fileIn(t);
  writeFileSync(file, "");
  assert.deepEqual(readNewLines(file, 0).lines, []);
  writeFileSync(file, "\n");
  assert.deepEqual(readNewLines(file, 0), { lines: [""], offset: 1, carry: "", truncated: false, missing: false });
});

test("readNewLines passes malformed lines through untouched for the caller to reject", (t) => {
  const file = fileIn(t);
  writeFileSync(file, 'not json\n{"ts":"bad"}\n\n{"ok":1}\n');
  assert.deepEqual(readNewLines(file, 0).lines, ["not json", '{"ts":"bad"}', "", '{"ok":1}']);
});

test("readNewLines keeps multi-byte characters intact across a split", (t) => {
  const file = fileIn(t);
  writeFileSync(file, "é\n");
  const first = readNewLines(file, 0);
  assert.deepEqual(first.lines, ["é"]);
  assert.equal(first.offset, 3);
});

test("tailFile replays existing lines, signals replay completion, then delivers appended lines on the poll timer", (t) => {
  t.mock.timers.enable({ apis: ["setInterval"] });
  const file = fileIn(t);
  writeFileSync(file, "one\n");
  const seen = [];
  const stop = tailFile(file, (line) => seen.push(line), { pollMs: 50, onReplayComplete: () => seen.push("<replayed>") });
  assert.deepEqual(seen, ["one", "<replayed>"]);
  appendFileSync(file, "two\nthr");
  t.mock.timers.tick(50);
  assert.deepEqual(seen, ["one", "<replayed>", "two"]);
  appendFileSync(file, "ee\n");
  t.mock.timers.tick(50);
  assert.deepEqual(seen, ["one", "<replayed>", "two", "three"]);
  stop();
  appendFileSync(file, "four\n");
  t.mock.timers.tick(200);
  assert.equal(seen.length, 4);
});

test("tailFile with fromStart false skips existing content", (t) => {
  t.mock.timers.enable({ apis: ["setInterval"] });
  const file = fileIn(t);
  writeFileSync(file, "old\n");
  const seen = [];
  const stop = tailFile(file, (line) => seen.push(line), { pollMs: 50, fromStart: false });
  appendFileSync(file, "new\n");
  t.mock.timers.tick(50);
  stop();
  assert.deepEqual(seen, ["new"]);
});

test("tailFile tolerates a file that appears later and reports truncation", (t) => {
  t.mock.timers.enable({ apis: ["setInterval"] });
  const file = fileIn(t);
  const seen = [];
  let truncations = 0;
  const stop = tailFile(file, (line) => seen.push(line), { pollMs: 50, onTruncate: () => { truncations += 1; } });
  t.mock.timers.tick(50);
  assert.deepEqual(seen, []);
  writeFileSync(file, "late\nlines\n");
  t.mock.timers.tick(50);
  assert.deepEqual(seen, ["late", "lines"]);
  writeFileSync(file, "x\n");
  t.mock.timers.tick(50);
  assert.deepEqual(seen, ["late", "lines", "x"]);
  assert.equal(truncations, 1);
  stop();
});
