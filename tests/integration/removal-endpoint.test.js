import { test } from "node:test";
import assert from "node:assert/strict";
import { appendFileSync, writeFileSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { startServer } from "../../webhook/server.js";
import { parseEventLine } from "../../webhook/schema.js";
import { createState as createPageState, applySnapshot, applyEvent, liveSessions } from "../../frontend/state.js";
import { makeTmpDir } from "../helpers/tmp-dir.js";
import { connectSse } from "../helpers/sse-client.js";

const line = (event) => `${JSON.stringify(event)}\n`;
const sessionEvent = (overrides) => ({ ts: "2026-10-05T21:40:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "busy", role: "validator", ...overrides });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const serverOn = async (t, eventsPath) => {
  const started = await startServer({ eventsPath, port: 0, host: "127.0.0.1", livenessIntervalMs: 0, pollMs: 20 });
  let stopped = false;
  const stop = async () => { if (!stopped) { stopped = true; await started.stop(); } };
  t.after(stop);
  const base = `http://127.0.0.1:${started.server.address().port}`;
  return { ...started, base, stop, snapshot: async () => (await fetch(`${base}/snapshot`)).json(), remove: (pid, method = "POST") => fetch(`${base}/sessions/${pid}/remove`, { method }) };
};

test("POST /sessions/<pid>/remove drops the session, persists across a restart, and a later event brings it back", async (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  const eventsPath = join(path, "events.jsonl");
  writeFileSync(eventsPath, line(sessionEvent()) + line(sessionEvent({ pid: 2, session: "tag-analyzer-63", folder: "tag_analyzer", state: "ended", role: null })));
  const first = await serverOn(t, eventsPath);
  const sse = connectSse(`${first.base}/events`);
  t.after(() => sse.close());
  await sse.waitFor((frames) => frames.some((f) => f.event === "snapshot"));
  const page = createPageState();
  applySnapshot(page, sse.frames.find((f) => f.event === "snapshot").data, 0);
  assert.deepEqual(liveSessions(page).map((s) => s.pid), [29904]);

  const removed = await first.remove(29904);
  assert.equal(removed.status, 204);
  assert.equal(await removed.text(), "");
  await sse.waitFor((frames) => frames.some((f) => f.event === "session" && f.data.state === "removed"));
  const frame = sse.frames.find((f) => f.event === "session").data;
  assert.deepEqual([frame.pid, frame.state, frame.session, frame.folder, frame.role], [29904, "removed", "listings-bc", "listings", "validator"]);
  applyEvent(page, "session", frame, 0);
  assert.deepEqual(liveSessions(page), []);
  assert.equal(page.sessions.get(29904).state, "removed");

  const unknown = await first.remove(4242);
  assert.equal(unknown.status, 404);
  assert.equal(await unknown.text(), "unknown pid");
  const wrongMethod = await first.remove(29904, "GET");
  assert.equal(wrongMethod.status, 405);
  assert.equal(wrongMethod.headers.get("allow"), "POST");

  const nonNumeric = await first.remove("abc");
  assert.equal(nonNumeric.status, 404);
  const repeat = await first.remove(29904);
  assert.equal(repeat.status, 204);
  await sleep(80);
  assert.equal(sse.frames.filter((f) => f.event === "session" && f.data.state === "removed").length, 1);
  assert.equal(readFileSync(eventsPath, "utf8").trim().split("\n").length, 3);
  assert.equal((await first.snapshot()).stats.removals, 1);

  const endedRemoved = await first.remove(2);
  assert.equal(endedRemoved.status, 204);
  await sleep(80);
  const mid = await first.snapshot();
  assert.deepEqual(mid.sessions.map((s) => s.pid), []);
  assert.equal(mid.stats.removals, 2);
  assert.equal(sse.frames.filter((f) => f.event === "session" && f.data.state === "removed").length, 2);
  const lines = readFileSync(eventsPath, "utf8").trim().split("\n").map(parseEventLine);
  assert.deepEqual(lines.map((e) => e.state), ["busy", "ended", "removed", "removed"]);
  assert.ok(lines.every((e) => e !== null));
  await first.stop();

  const second = await serverOn(t, eventsPath);
  const afterRestart = await second.snapshot();
  assert.deepEqual(afterRestart.sessions.map((s) => s.pid), []);
  assert.equal(afterRestart.stats.eventsApplied, 4);
  assert.equal(afterRestart.stats.removals, 0);
  const late = connectSse(`${second.base}/events`);
  t.after(() => late.close());
  await late.waitFor((frames) => frames.some((f) => f.event === "snapshot"));
  assert.deepEqual(late.frames.find((f) => f.event === "snapshot").data.sessions, []);

  appendFileSync(eventsPath, line(sessionEvent({ ts: "2026-10-05T21:50:00Z", session: null, role: null, state: "busy" })));
  await late.waitFor((frames) => frames.some((f) => f.event === "session"));
  const back = late.frames.find((f) => f.event === "session").data;
  assert.deepEqual([back.pid, back.state, back.session, back.role], [29904, "busy", "listings-bc", "validator"]);
  const restored = await second.snapshot();
  assert.deepEqual(restored.sessions.map((s) => [s.pid, s.state]), [[29904, "busy"]]);
  const pageAfter = createPageState();
  applySnapshot(pageAfter, late.frames.find((f) => f.event === "snapshot").data, 0);
  applyEvent(pageAfter, "session", back, 0);
  assert.deepEqual(liveSessions(pageAfter).map((s) => s.pid), [29904]);
});

test("removal lines written by the server are not applied twice when the tailer reads them back", async (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  const eventsPath = join(path, "events.jsonl");
  writeFileSync(eventsPath, line(sessionEvent()));
  const server = await serverOn(t, eventsPath);
  await server.remove(29904);
  await sleep(100);
  const snap = await server.snapshot();
  assert.equal(snap.stats.eventsApplied, 2);
  assert.equal(snap.stats.linesRead, 2);
  assert.equal(snap.stats.removals, 1);
});
