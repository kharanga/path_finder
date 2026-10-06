import { test, mock } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { isPidAlive, hasSocket, readRegistryStatus, findDeadSessions, findStatusCorrections, SOCKET_DIR, DEFAULT_SESSIONS_DIR } from "../../../webhook/liveness.js";
import { createState, applyEvent } from "../../../webhook/state.js";
import { makeTmpDir } from "../../helpers/tmp-dir.js";

const now = new Date("2026-10-05T21:45:00Z");
const sessionEvent = (overrides) => ({ ts: "2026-10-05T21:40:02Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: null, ...overrides });
const stateWith = (...events) => {
  const state = createState();
  for (const event of events) applyEvent(state, event);
  return state;
};
const killError = (code) => Object.assign(new Error(code), { code });

test("constants point at the documented internals", () => {
  assert.equal(SOCKET_DIR, "/tmp/cc-socks");
  assert.ok(DEFAULT_SESSIONS_DIR.endsWith("/.claude/sessions"));
});

test("isPidAlive uses signal 0 and treats EPERM as alive, ESRCH as dead", (t) => {
  const kill = t.mock.method(process, "kill", () => true);
  assert.equal(isPidAlive(4242), true);
  assert.deepEqual(kill.mock.calls[0].arguments, [4242, 0]);
  kill.mock.mockImplementation(() => { throw killError("EPERM"); });
  assert.equal(isPidAlive(4242), true);
  kill.mock.mockImplementation(() => { throw killError("ESRCH"); });
  assert.equal(isPidAlive(4242), false);
  kill.mock.mockImplementation(() => { throw new Error("no code"); });
  assert.equal(isPidAlive(4242), false);
});

test("hasSocket checks <dir>/<pid>.sock in the given directory only", (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  writeFileSync(join(path, "7.sock"), "");
  assert.equal(hasSocket(7, path), true);
  assert.equal(hasSocket(8, path), false);
  assert.equal(hasSocket(7, join(path, "missing")), false);
});

test("readRegistryStatus returns typed fields, nulls for wrong types, and null for missing or bad files", (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  writeFileSync(join(path, "1.json"), JSON.stringify({ pid: 1, name: "a-11", status: "busy", statusUpdatedAt: 1791266113437 }));
  writeFileSync(join(path, "2.json"), JSON.stringify({ pid: 2, name: 5, status: null, statusUpdatedAt: "soon" }));
  writeFileSync(join(path, "3.json"), "{bad json");
  assert.deepEqual(readRegistryStatus(1, path), { status: "busy", name: "a-11", statusUpdatedAt: 1791266113437 });
  assert.deepEqual(readRegistryStatus(2, path), { status: null, name: null, statusUpdatedAt: null });
  assert.equal(readRegistryStatus(3, path), null);
  assert.equal(readRegistryStatus(4, path), null);
  assert.equal(readRegistryStatus(1, join(path, "missing")), null);
});

test("findDeadSessions returns an ended copy for each non-ended session whose pid is dead", () => {
  const state = stateWith(sessionEvent({ pid: 1 }), sessionEvent({ pid: 2, state: "busy" }), sessionEvent({ pid: 3, state: "ended" }));
  const isAlive = mock.fn((pid) => pid === 2);
  const ended = findDeadSessions(state, now, isAlive);
  assert.deepEqual(ended, [{ ...sessionEvent({ pid: 1 }), ts: "2026-10-05T21:45:00.000Z", state: "ended" }]);
  assert.deepEqual(isAlive.mock.calls.map((c) => c.arguments[0]), [1, 2]);
  assert.equal(state.sessions.get(1).state, "idle");
});

test("findDeadSessions returns nothing when every pid is alive or the state is empty", () => {
  assert.deepEqual(findDeadSessions(stateWith(sessionEvent()), now, () => true), []);
  assert.deepEqual(findDeadSessions(createState(), now, () => false), []);
});

test("findStatusCorrections emits a correction when the registry is newer and disagrees", () => {
  const state = stateWith(sessionEvent());
  const read = mock.fn(() => ({ status: "busy", name: "listings-bc", statusUpdatedAt: Date.parse("2026-10-05T21:44:00Z") }));
  assert.deepEqual(findStatusCorrections(state, now, read), [{ ...sessionEvent(), ts: "2026-10-05T21:45:00.000Z", state: "busy" }]);
  assert.deepEqual(read.mock.calls[0].arguments, [29904]);
});

test("findStatusCorrections ignores older, agreeing, ended, unknown, missing, and timestamp-less registry entries", () => {
  const state = stateWith(sessionEvent());
  const newer = Date.parse("2026-10-05T21:44:00Z");
  const older = Date.parse("2026-10-05T21:39:00Z");
  for (const registry of [
    { status: "busy", name: "listings-bc", statusUpdatedAt: older },
    { status: "idle", name: "listings-bc", statusUpdatedAt: newer },
    { status: "ended", name: "listings-bc", statusUpdatedAt: newer },
    { status: "sleeping", name: "listings-bc", statusUpdatedAt: newer },
    { status: "busy", name: "listings-bc", statusUpdatedAt: null },
    null,
  ]) {
    assert.deepEqual(findStatusCorrections(state, now, () => registry), [], JSON.stringify(registry));
  }
});

test("findStatusCorrections skips ended sessions entirely", () => {
  const read = mock.fn(() => ({ status: "busy", name: "x", statusUpdatedAt: Date.parse("2026-10-05T21:44:00Z") }));
  assert.deepEqual(findStatusCorrections(stateWith(sessionEvent({ state: "ended" })), now, read), []);
  assert.equal(read.mock.callCount(), 0);
});

test("findStatusCorrections fills a missing name from the registry even without a newer status", () => {
  const state = stateWith(sessionEvent({ session: null, state: "busy" }));
  const corrections = findStatusCorrections(state, now, () => ({ status: "busy", name: "listings-9f", statusUpdatedAt: null }));
  assert.deepEqual(corrections, [{ ...sessionEvent({ session: "listings-9f", state: "busy" }), ts: "2026-10-05T21:45:00.000Z" }]);
  assert.deepEqual(findStatusCorrections(state, now, () => ({ status: "busy", name: null, statusUpdatedAt: null })), []);
});

test("findStatusCorrections applies name and status together", () => {
  const state = stateWith(sessionEvent({ session: null, state: "busy" }));
  const corrections = findStatusCorrections(state, now, () => ({ status: "waiting", name: "listings-9f", statusUpdatedAt: Date.parse("2026-10-05T21:44:00Z") }));
  assert.deepEqual([corrections[0].session, corrections[0].state], ["listings-9f", "waiting"]);
});
