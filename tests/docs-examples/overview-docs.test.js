import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validateEvent, SESSION_STATES } from "../../webhook/schema.js";
import { createHub, sseFrame } from "../../webhook/server.js";

const overview = readFileSync(new URL("../../docs/overview.md", import.meta.url), "utf8");
const jsonBlocks = [...overview.matchAll(/```json\n([\s\S]*?)```/g)].map((match) => match[1].trim());
const examples = jsonBlocks.flatMap((block) => block.split("\n")).map((line) => JSON.parse(line));

test("overview.md has one session and one message example", () => {
  assert.deepEqual(examples.map((event) => event.type), ["session", "message"]);
});

for (const event of examples) {
  test(`overview.md ${event.type} example validates`, () => {
    assert.deepEqual(validateEvent(event), { ok: true, errors: [] });
  });
}

test("overview.md lists exactly the schema's states", () => {
  const row = overview.split("\n").find((line) => line.startsWith("| `state` |"));
  for (const state of SESSION_STATES) assert.ok(row.includes(`\`${state}\``), state);
});

test("overview.md contract: the first SSE frame is a snapshot with sessions and messages, later frames are session, message, or liveness", () => {
  const hub = createHub({ isAlive: () => false, readStatus: () => null });
  const frames = [];
  hub.addClient({ write: (frame) => frames.push(frame) });
  hub.ingestLine(JSON.stringify(examples[0]));
  hub.ingestLine(JSON.stringify(examples[1]));
  hub.runLivenessCheck(new Date("2026-10-05T21:45:00Z"));
  const names = frames.map((frame) => frame.split("\n")[0].slice(7));
  assert.deepEqual(names, ["snapshot", "session", "message", "liveness"]);
  const snapshot = JSON.parse(frames[0].split("\n")[1].slice(6));
  assert.deepEqual(Object.keys(snapshot), ["sessions", "messages"]);
  assert.equal(frames[1], sseFrame("session", examples[0]));
  assert.ok(overview.includes("`event: liveness`"));
});
