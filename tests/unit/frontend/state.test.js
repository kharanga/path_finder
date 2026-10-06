import { test } from "node:test";
import assert from "node:assert/strict";
import { createState, applySnapshot, applyEvent, applySessionEvent, applyMessageEvent, prunePlaceholders, folderFromName, waitingThreads, liveSessions, sessionByName, sessionLabel } from "../../../frontend/state.js";

const NOW = 1_000_000;
const session = (overrides) => ({ ts: "2026-10-05T21:40:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: null, ...overrides });
const message = (overrides) => ({ ts: "2026-10-05T21:40:05Z", type: "message", from: "listings-bc", to: "tag-analyzer-63", text: "hi", notify_on_idle: false, ...overrides });
const labels = (state) => liveSessions(state).map(sessionLabel);

test("createState is empty", () => {
  assert.deepEqual(createState(), { sessions: new Map(), placeholders: new Map(), messages: [], threads: [], lastEventTs: null, snapshotSeq: 0 });
});

test("applySnapshot replaces everything, bumps snapshotSeq, and tolerates null or partial snapshots", () => {
  const state = createState();
  applyMessageEvent(state, message(), NOW);
  applySnapshot(state, { sessions: [session()], messages: [message({ notify_on_idle: true })] }, NOW);
  assert.equal(state.sessions.get(29904).state, "idle");
  assert.equal(state.messages.length, 1);
  assert.deepEqual(state.threads.map((t) => t.status), ["waiting"]);
  assert.equal(state.snapshotSeq, 1);
  assert.equal(state.lastEventTs, "2026-10-05T21:40:05Z");
  applySnapshot(state, null, NOW);
  assert.deepEqual([state.sessions.size, state.messages.length, state.threads.length, state.placeholders.size, state.snapshotSeq], [0, 0, 0, 0, 2]);
  applySnapshot(state, { sessions: [{ pid: "x" }], messages: [{ from: 1, to: 2 }] }, NOW);
  assert.deepEqual([state.sessions.size, state.messages.length], [0, 0]);
});

test("applyEvent routes session and liveness to the session reducer, message to the message reducer, and ignores others", () => {
  const state = createState();
  applyEvent(state, "liveness", session({ state: "ended" }), NOW);
  assert.equal(state.sessions.get(29904).state, "ended");
  applyEvent(state, "message", message(), NOW);
  assert.equal(state.messages.length, 1);
  applyEvent(state, "bogus", message(), NOW);
  applyEvent(state, "session", null, NOW);
  assert.equal(state.messages.length, 1);
  assert.equal(state.sessions.size, 1);
});

test("applySessionEvent keys by pid, keeps known name, folder, and role, and tracks firstSeen", () => {
  const state = createState();
  applySessionEvent(state, session({ ts: "2026-10-05T21:43:00Z", session: null, folder: "scratch", pid: 30444, state: "started" }));
  applySessionEvent(state, session({ ts: "2026-10-05T21:45:00Z", session: "scratch-7a", folder: "scratch", pid: 30444, state: "idle" }));
  applySessionEvent(state, session({ ts: "2026-10-05T21:46:00Z", session: null, folder: "scratch", pid: 30444, state: "busy", role: "validator" }));
  applySessionEvent(state, session({ ts: "2026-10-05T21:47:00Z", session: null, pid: 30444, state: "waiting", role: null, folder: undefined }));
  assert.deepEqual(state.sessions.get(30444), { pid: 30444, session: "scratch-7a", folder: "scratch", role: "validator", state: "waiting", ts: "2026-10-05T21:47:00Z", firstSeen: "2026-10-05T21:43:00Z", formerNames: [], stateBeforeRemoval: null });
  assert.equal(applySessionEvent(state, { pid: "nope" }).sessions.size, 1);
  assert.equal(applySessionEvent(state, { pid: 5 }).sessions.get(5).folder, "unknown");
  assert.equal(state.sessions.get(5).state, "started");
});

test("lastEventTs keeps the maximum timestamp seen", () => {
  const state = createState();
  applySessionEvent(state, session({ ts: "2026-10-05T21:50:00Z" }));
  applySessionEvent(state, session({ ts: "2026-10-05T21:40:00Z", pid: 2 }));
  applyMessageEvent(state, message({ ts: null }), NOW);
  assert.equal(state.lastEventTs, "2026-10-05T21:50:00Z");
});

test("applyMessageEvent stores defaults, keeps a null or absent sender, and drops bad shapes", () => {
  const state = createState();
  applyMessageEvent(state, { to: "b" }, NOW);
  assert.deepEqual(state.messages[0], { ts: null, from: null, to: "b", text: "", notify_on_idle: false });
  applyMessageEvent(state, message({ from: null, notify_on_idle: true }), NOW);
  assert.equal(state.messages[1].from, null);
  assert.deepEqual(state.threads.map((t) => [t.id, t.from, t.to]), [[1, null, "tag-analyzer-63"]]);
  for (const bad of [null, { from: "a" }, { from: 5, to: "b" }, { from: "a", to: 7 }]) applyMessageEvent(state, bad, NOW);
  assert.equal(state.messages.length, 2);
});

test("threads wait until the recipient goes idle (snapped) or ended (dropped)", () => {
  const state = createState();
  applyMessageEvent(state, message({ to: "r-1", notify_on_idle: true }), NOW);
  applyMessageEvent(state, message({ to: "r-2", notify_on_idle: true }), NOW);
  applyMessageEvent(state, message({ to: "r-1", notify_on_idle: false }), NOW);
  assert.deepEqual(waitingThreads(state).map((t) => t.to), ["r-1", "r-2"]);
  for (const st of ["started", "busy", "waiting"]) applySessionEvent(state, session({ pid: 1, session: "r-1", state: st }));
  assert.deepEqual(waitingThreads(state).map((t) => t.to), ["r-1", "r-2"]);
  applySessionEvent(state, session({ ts: "2026-10-05T21:41:00Z", pid: 1, session: "r-1", state: "idle" }));
  applySessionEvent(state, session({ ts: "2026-10-05T21:42:00Z", pid: 2, session: "r-2", state: "ended" }));
  assert.deepEqual(state.threads.map((t) => [t.to, t.status, t.resolvedTs]), [["r-1", "snapped", "2026-10-05T21:41:00Z"], ["r-2", "dropped", "2026-10-05T21:42:00Z"]]);
  applySessionEvent(state, session({ ts: "2026-10-05T21:43:00Z", pid: 1, session: "r-1", state: "idle" }));
  assert.equal(state.threads[0].resolvedTs, "2026-10-05T21:41:00Z");
});

test("at most 50 finished threads are kept while every waiting thread survives", () => {
  const state = createState();
  for (let i = 0; i < 60; i += 1) applyMessageEvent(state, message({ to: `r-${i}`, notify_on_idle: true }), NOW);
  applyMessageEvent(state, message({ to: "keep", notify_on_idle: true }), NOW);
  for (let i = 0; i < 60; i += 1) applySessionEvent(state, session({ pid: i + 1, session: `r-${i}`, state: "idle" }));
  assert.equal(state.threads.length, 51);
  assert.deepEqual(waitingThreads(state).map((t) => t.to), ["keep"]);
  assert.equal(state.threads[0].id, 10);
});

test("placeholders are created for unknown names, merged on a session event, and pruned by age", () => {
  const state = createState();
  applyMessageEvent(state, message({ from: "a-11", to: "b-22" }), 5000);
  assert.deepEqual([...state.placeholders.keys()], ["a-11", "b-22"]);
  assert.deepEqual(state.placeholders.get("a-11"), { name: "a-11", folder: "a", createdAtMs: 5000 });
  assert.deepEqual(liveSessions(state).map((s) => s.pid), ["placeholder:a-11", "placeholder:b-22"]);
  assert.equal(sessionByName(state, "a-11").state, "placeholder");
  applySessionEvent(state, session({ pid: 1, session: "b-22", folder: "b", state: "started" }));
  assert.deepEqual([...state.placeholders.keys()], ["a-11"]);
  assert.deepEqual(liveSessions(state).map((s) => s.pid), ["placeholder:a-11", 1]);
  assert.equal(prunePlaceholders(state, 5000 + 59999), 0);
  assert.equal(prunePlaceholders(state, 5000 + 60000), 1);
  assert.equal(state.placeholders.size, 0);
  applyMessageEvent(state, message({ from: null, to: "b-22" }), 9000);
  assert.equal(state.placeholders.size, 0);
  applyMessageEvent(state, message({ from: "c-33", to: "b-22" }), 9000);
  assert.equal(prunePlaceholders(state, 9000 + 100, 100), 1);
});

test("folderFromName strips a trailing two-hex-digit id and leaves other names alone", () => {
  assert.equal(folderFromName("path-finder-18"), "path-finder");
  assert.equal(folderFromName("listings-bc"), "listings");
  assert.equal(folderFromName("add-semantic-similarity-scores"), "add-semantic-similarity-scores");
  assert.equal(folderFromName("manager-drives-feature-work"), "manager-drives-feature-work");
  assert.equal(folderFromName("x-1"), "x-1");
  assert.throws(() => folderFromName(null), TypeError);
});

test("liveSessions excludes ended sessions, includes placeholders, and sorts folders with _ and - as equal", () => {
  const state = createState();
  applySessionEvent(state, session({ pid: 1, session: "path-finder-18", folder: "path_finder" }));
  applySessionEvent(state, session({ pid: 2, session: "zed-01", folder: "zed", state: "ended" }));
  applySessionEvent(state, session({ pid: 3, session: "alpha-01", folder: "alpha", state: "waiting" }));
  applySessionEvent(state, session({ pid: 4, session: null, folder: "alpha", state: "started" }));
  applyMessageEvent(state, message({ from: "path-finder-99", to: "alpha-01" }), NOW);
  assert.deepEqual(labels(state), ["alpha-01", "pid 4", "path-finder-18", "path-finder-99"]);
  assert.deepEqual(liveSessions(state).map((s) => s.folder), ["alpha", "alpha", "path_finder", "path-finder"]);
});

test("sessionByName resolves current names, then former names of live sessions, then placeholders", () => {
  const state = createState();
  applySessionEvent(state, session({ pid: 1, session: "old-aa", state: "busy" }));
  applySessionEvent(state, session({ pid: 1, session: "new-bb", state: "busy" }));
  applyMessageEvent(state, message({ from: "ghost-zz", to: "new-bb" }), NOW);
  assert.equal(sessionByName(state, "new-bb").pid, 1);
  assert.equal(sessionByName(state, "old-aa").pid, 1);
  assert.equal(sessionByName(state, "ghost-zz").pid, "placeholder:ghost-zz");
  assert.equal(sessionByName(state, "nobody"), undefined);
  assert.equal(sessionByName(state, null), undefined);
  assert.equal(sessionByName(state, 7), undefined);
  applySessionEvent(state, session({ pid: 1, session: "new-bb", state: "ended" }));
  assert.equal(sessionByName(state, "new-bb").pid, 1);
  assert.equal(sessionByName(state, "old-aa"), undefined);
});

test("renames append former names without duplicates and a first naming is not a rename", () => {
  const state = createState();
  applySessionEvent(state, session({ pid: 1, session: null }));
  applySessionEvent(state, session({ pid: 1, session: "a" }));
  assert.deepEqual(state.sessions.get(1).formerNames, []);
  for (const name of ["b", "a", "c"]) applySessionEvent(state, session({ pid: 1, session: name }));
  assert.deepEqual(state.sessions.get(1).formerNames, ["a", "b"]);
  assert.equal(state.sessions.get(1).session, "c");
});

test("a rename removes placeholders for any of the session's names and resolves threads to a former name", () => {
  const state = createState();
  applyMessageEvent(state, message({ from: "x", to: "old-aa", notify_on_idle: true }), NOW);
  assert.deepEqual([...state.placeholders.keys()], ["x", "old-aa"]);
  applySessionEvent(state, session({ pid: 1, session: "old-aa", state: "busy" }));
  applySessionEvent(state, session({ pid: 1, session: "new-bb", state: "busy" }));
  applyMessageEvent(state, message({ from: "old-aa", to: "x" }), NOW);
  assert.deepEqual([...state.placeholders.keys()], ["x"]);
  assert.deepEqual(waitingThreads(state).map((t) => t.to), ["old-aa"]);
  applySessionEvent(state, session({ pid: 1, session: "new-bb", state: "idle" }));
  assert.deepEqual(state.threads.map((t) => t.status), ["snapped"]);
});

test("sessionLabel falls back to the pid while the name is unknown", () => {
  assert.equal(sessionLabel({ pid: 30444, session: null }), "pid 30444");
  assert.equal(sessionLabel({ pid: 30444, session: "scratch-7a" }), "scratch-7a");
});

test("removed sessions are not live, keep their entry, and reappear on any later event", () => {
  const state = createState();
  applySessionEvent(state, session({ pid: 1, session: "a-1", role: "validator", state: "busy" }));
  applySessionEvent(state, session({ pid: 1, session: "a-1", role: "validator", state: "removed", ts: "2026-10-05T21:41:00Z" }));
  assert.deepEqual(labels(state), []);
  assert.equal(state.sessions.get(1).state, "removed");
  assert.equal(sessionByName(state, "a-1").pid, 1);
  applySessionEvent(state, session({ pid: 1, session: null, role: null, state: "idle", ts: "2026-10-05T21:42:00Z" }));
  assert.deepEqual(liveSessions(state).map((s) => [s.pid, s.session, s.role, s.state]), [[1, "a-1", "validator", "idle"]]);
});

test("a removed recipient does not resolve a waiting thread, and a later message reinstates it in its pre-removal state", () => {
  const state = createState();
  applySessionEvent(state, session({ pid: 1, session: "r-1", state: "busy" }));
  applyMessageEvent(state, message({ from: "s-0", to: "r-1", notify_on_idle: true }), NOW);
  applySessionEvent(state, session({ pid: 1, session: "r-1", state: "removed", ts: "2026-10-05T21:41:00Z" }));
  assert.deepEqual([state.sessions.get(1).state, state.sessions.get(1).stateBeforeRemoval], ["removed", "busy"]);
  assert.deepEqual(waitingThreads(state).map((t) => t.to), ["r-1"]);
  applyMessageEvent(state, message({ from: "x-9", to: "r-1", ts: "2026-10-05T21:42:00Z" }), NOW);
  assert.deepEqual([...state.placeholders.keys()], ["s-0", "x-9"]);
  assert.deepEqual([state.sessions.get(1).state, state.sessions.get(1).stateBeforeRemoval, state.sessions.get(1).ts], ["busy", null, "2026-10-05T21:42:00Z"]);
  assert.deepEqual(liveSessions(state).filter((s) => s.pid === 1).length, 1);
});

test("stateBeforeRemoval records the state at removal, survives repeated removals, and reinstates to idle when not live-able", () => {
  const state = createState();
  applySessionEvent(state, session({ pid: 1, session: "a-1", state: "waiting" }));
  applySessionEvent(state, session({ pid: 1, session: "a-1", state: "removed" }));
  applySessionEvent(state, session({ pid: 1, session: "a-1", state: "removed" }));
  assert.equal(state.sessions.get(1).stateBeforeRemoval, "waiting");
  applySessionEvent(state, session({ pid: 1, session: "a-1", state: "idle" }));
  assert.equal(state.sessions.get(1).stateBeforeRemoval, null);
  applySessionEvent(state, session({ pid: 2, session: "b-2", state: "ended" }));
  applySessionEvent(state, session({ pid: 2, session: "b-2", state: "removed" }));
  assert.equal(state.sessions.get(2).stateBeforeRemoval, "ended");
  applyMessageEvent(state, message({ from: "b-2", to: "a-1" }), NOW);
  assert.equal(state.sessions.get(2).state, "idle");
  applySessionEvent(state, session({ pid: 3, session: "c-3", state: "removed" }));
  assert.equal(state.sessions.get(3).stateBeforeRemoval, null);
  applyMessageEvent(state, message({ from: "a-1", to: "c-3" }), NOW);
  assert.equal(state.sessions.get(3).state, "idle");
  assert.equal(state.placeholders.size, 0);
});

test("a removed session is found and reinstated by a former name, while a truly unknown name still gets a placeholder", () => {
  const state = createState();
  applySessionEvent(state, session({ pid: 1, session: "a-11", state: "busy" }));
  applySessionEvent(state, session({ pid: 1, session: "b-22", state: "busy" }));
  applySessionEvent(state, session({ pid: 1, session: "b-22", state: "removed" }));
  assert.equal(sessionByName(state, "a-11").pid, 1);
  assert.equal(sessionByName(state, "b-22").state, "removed");
  applyMessageEvent(state, message({ from: "a-11", to: "x-99" }), NOW);
  assert.deepEqual([state.sessions.get(1).state, state.sessions.get(1).session], ["busy", "b-22"]);
  assert.deepEqual([...state.placeholders.keys()], ["x-99"]);
});
