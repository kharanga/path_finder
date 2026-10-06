import { test, mock } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, mkdirSync, symlinkSync } from "node:fs";
import { join } from "node:path";
import { parseArgs, sseFrame, resolveStaticFile, createHub, DEFAULTS, CONTENT_TYPES } from "../../../webhook/server.js";
import { makeTmpDir } from "../../helpers/tmp-dir.js";

const sessionLine = (overrides) => JSON.stringify({ ts: "2026-10-05T21:40:00Z", type: "session", session: "a-1", folder: "a", pid: 1, state: "busy", role: null, ...overrides });
const messageLine = JSON.stringify({ ts: "2026-10-05T21:40:05Z", type: "message", from: "a-1", to: "b", text: "hi", notify_on_idle: true });

test("DEFAULTS bind to localhost only and point at the dashboard file", () => {
  assert.equal(DEFAULTS.host, "127.0.0.1");
  assert.equal(DEFAULTS.port, 4747);
  assert.ok(DEFAULTS.eventsPath.endsWith("/.claude/dashboard/events.jsonl"));
  assert.ok(DEFAULTS.frontendDir.endsWith("/frontend"));
  assert.equal(Object.keys(CONTENT_TYPES).length, 10);
});

test("parseArgs overrides defaults flag by flag and leaves the rest", () => {
  const options = parseArgs(["--events", "/tmp/e", "--port", "5000", "--liveness-interval", "0", "--demo", "--host", "127.0.0.2", "--poll", "10", "--frontend", "/f", "--sessions-dir", "/s"], { port: 1, demo: false, keep: true });
  assert.deepEqual(options, { port: 5000, demo: true, keep: true, eventsPath: "/tmp/e", livenessIntervalMs: 0, host: "127.0.0.2", pollMs: 10, frontendDir: "/f", sessionsDir: "/s" });
  assert.deepEqual(parseArgs([], { a: 1 }), { a: 1 });
});

test("parseArgs rejects unknown flags, numeric flags without a usable number, and path flags without a value", () => {
  assert.throws(() => parseArgs(["--bogus"]), /unknown flag --bogus/);
  for (const flag of ["--port", "--liveness-interval", "--poll"]) {
    assert.throws(() => parseArgs([flag]), new RegExp(`${flag} needs a non-negative number`));
    assert.throws(() => parseArgs([flag, "abc"]), /needs a non-negative number/);
    assert.throws(() => parseArgs([flag, "-1"]), /needs a non-negative number/);
  }
  for (const flag of ["--events", "--frontend", "--sessions-dir", "--host"]) assert.throws(() => parseArgs([flag]), new RegExp(`${flag} needs a value`));
});

test("sseFrame formats an event name and JSON payload", () => {
  assert.equal(sseFrame("session", { a: 1 }), 'event: session\ndata: {"a":1}\n\n');
  assert.equal(sseFrame("snapshot", { sessions: [], messages: [] }), 'event: snapshot\ndata: {"sessions":[],"messages":[]}\n\n');
});

test("resolveStaticFile serves files inside the directory with content types and refuses everything else", (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  const outside = join(path, "outside.txt");
  writeFileSync(outside, "secret");
  const root = join(path, "frontend");
  mkdirSync(join(root, "fixtures"), { recursive: true });
  writeFileSync(join(root, "index.html"), "<html>");
  writeFileSync(join(root, "app.js"), "");
  writeFileSync(join(root, "orbit.css"), "");
  writeFileSync(join(root, "fixtures", "few.json"), "{}");
  writeFileSync(join(root, "blob.bin"), "");
  symlinkSync(outside, join(root, "escape.txt"));
  assert.equal(resolveStaticFile(root, "/").filePath, join(root, "index.html"));
  assert.equal(resolveStaticFile(root, "/").contentType, "text/html; charset=utf-8");
  assert.equal(resolveStaticFile(root, "/app.js").contentType, "text/javascript; charset=utf-8");
  assert.equal(resolveStaticFile(root, "/orbit.css").contentType, "text/css; charset=utf-8");
  assert.equal(resolveStaticFile(root, "/fixtures/few.json").contentType, "application/json; charset=utf-8");
  assert.equal(resolveStaticFile(root, "/blob.bin").contentType, "application/octet-stream");
  assert.equal(resolveStaticFile(root, "//app.js").contentType, "text/javascript; charset=utf-8");
  for (const bad of ["/../outside.txt", "/%2e%2e/outside.txt", "/fixtures", "/nope.js", "/%E0%A4%A", "/escape.txt", "/..%5Coutside.txt"]) {
    assert.equal(resolveStaticFile(root, bad), null, bad);
  }
});

test("createHub counts lines, rejects malformed ones, applies valid ones, and broadcasts only live events", () => {
  const hub = createHub({ isAlive: () => true, readStatus: () => null });
  const frames = [];
  const remove = hub.addClient({ write: (frame) => frames.push(frame) });
  assert.equal(frames[0], sseFrame("snapshot", { sessions: [], messages: [] }));
  assert.equal(hub.ingestLine("not json"), null);
  assert.equal(hub.ingestLine(""), null);
  assert.equal(hub.ingestLine("   "), null);
  assert.equal(hub.ingestLine('{"ts":"bad"}'), null);
  assert.equal(hub.ingestLine(sessionLine(), { replaying: true }).state, "busy");
  assert.equal(hub.ingestLine(messageLine).text, "hi");
  assert.deepEqual(hub.stats, { linesRead: 6, malformedLines: 2, eventsApplied: 2, livenessEnded: 0, statusCorrections: 0 });
  assert.deepEqual(frames.map((frame) => frame.split("\n")[0]), ["event: snapshot", "event: message"]);
  remove();
  hub.ingestLine(sessionLine({ state: "idle" }));
  assert.equal(frames.length, 2);
  assert.equal(hub.state.sessions.get(1).state, "idle");
});

test("createHub snapshot for a late client reflects the current state", () => {
  const hub = createHub({ isAlive: () => true, readStatus: () => null });
  hub.ingestLine(sessionLine(), { replaying: true });
  hub.ingestLine(messageLine, { replaying: true });
  const frames = [];
  hub.addClient({ write: (frame) => frames.push(frame) });
  const payload = JSON.parse(frames[0].split("\n")[1].slice(6));
  assert.equal(payload.sessions[0].pid, 1);
  assert.equal(payload.messages[0].text, "hi");
});

test("createHub honors the message limit", () => {
  const hub = createHub({ messageLimit: 1, isAlive: () => true, readStatus: () => null });
  hub.ingestLine(messageLine);
  hub.ingestLine(messageLine.replace('"hi"', '"later"'));
  assert.deepEqual(hub.state.messages.map((m) => m.text), ["later"]);
});

test("runLivenessCheck applies and broadcasts dead pids as liveness and registry corrections as session", () => {
  const isAlive = mock.fn((pid) => pid !== 1);
  const readStatus = mock.fn((pid) => (pid === 2 ? { status: "idle", name: "b-2", statusUpdatedAt: Date.parse("2026-10-05T21:44:00Z") } : null));
  const hub = createHub({ isAlive, readStatus });
  hub.ingestLine(sessionLine({ pid: 1 }), { replaying: true });
  hub.ingestLine(sessionLine({ pid: 2, session: null, folder: "b" }), { replaying: true });
  const frames = [];
  hub.addClient({ write: (frame) => frames.push(frame) });
  const result = hub.runLivenessCheck(new Date("2026-10-05T21:45:00Z"));
  assert.deepEqual(result.ended.map((e) => [e.pid, e.state]), [[1, "ended"]]);
  assert.deepEqual(result.corrections.map((e) => [e.pid, e.session, e.state]), [[2, "b-2", "idle"]]);
  assert.equal(hub.state.sessions.get(1).state, "ended");
  assert.deepEqual([hub.state.sessions.get(2).session, hub.state.sessions.get(2).state], ["b-2", "idle"]);
  assert.deepEqual(frames.slice(1).map((frame) => frame.split("\n")[0]), ["event: liveness", "event: session"]);
  assert.deepEqual(hub.stats, { linesRead: 2, malformedLines: 0, eventsApplied: 2, livenessEnded: 1, statusCorrections: 1 });
  assert.deepEqual(hub.runLivenessCheck(new Date("2026-10-05T21:46:00Z")), { ended: [], corrections: [] });
  assert.deepEqual(isAlive.mock.calls.map((c) => c.arguments[0]), [1, 2, 2]);
});
