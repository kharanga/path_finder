import { test } from "node:test";
import assert from "node:assert/strict";
import { createState, applyEvent, findSessionByName, snapshot, DEFAULT_MESSAGE_LIMIT } from "../../../webhook/state.js";

const sessionEvent = (overrides) => ({ ts: "2026-10-05T21:40:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "started", role: null, ...overrides });
const messageEvent = (overrides) => ({ ts: "2026-10-05T21:41:00Z", type: "message", from: "a", to: "b", text: "m", notify_on_idle: false, ...overrides });

test("createState starts empty with the default or given message limit", () => {
  assert.equal(DEFAULT_MESSAGE_LIMIT, 500);
  const state = createState();
  assert.equal(state.sessions.size, 0);
  assert.deepEqual(state.messages, []);
  assert.equal(state.messageLimit, 500);
  assert.equal(createState(2).messageLimit, 2);
});

test("applyEvent stores a session keyed by pid and returns the stored object", () => {
  const state = createState();
  const stored = applyEvent(state, sessionEvent());
  assert.deepEqual(stored, sessionEvent());
  assert.equal(state.sessions.get(29904), stored);
});

test("applyEvent keeps the known name, folder, and role when a later event has null or empty values", () => {
  const state = createState();
  applyEvent(state, sessionEvent({ session: null, role: null }));
  applyEvent(state, sessionEvent({ ts: "2026-10-05T21:40:01Z", session: "listings-bc", state: "busy", role: "validator" }));
  const stored = applyEvent(state, sessionEvent({ ts: "2026-10-05T21:40:02Z", session: null, folder: "", state: "idle", role: null }));
  assert.deepEqual(stored, { ts: "2026-10-05T21:40:02Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: "validator" });
});

test("applyEvent lets a later non-null name, folder, or role replace the earlier one", () => {
  const state = createState();
  applyEvent(state, sessionEvent({ session: "old-11", role: "manager" }));
  const stored = applyEvent(state, sessionEvent({ ts: "2026-10-05T21:40:01Z", session: "new-22", folder: "other", role: "validator" }));
  assert.deepEqual([stored.session, stored.folder, stored.role], ["new-22", "other", "validator"]);
});

test("applyEvent on a session without prior state fills folder with an empty string when the event folder is empty", () => {
  const state = createState();
  assert.equal(applyEvent(state, sessionEvent({ folder: "" })).folder, "");
});

test("applyEvent keeps separate entries per pid and accepts every state including waiting", () => {
  const state = createState();
  applyEvent(state, sessionEvent({ pid: 1, state: "waiting" }));
  applyEvent(state, sessionEvent({ pid: 2, state: "ended" }));
  assert.equal(state.sessions.size, 2);
  assert.equal(state.sessions.get(1).state, "waiting");
  assert.equal(state.sessions.get(2).state, "ended");
});

test("applyEvent appends messages oldest first, returns the event, and trims to the limit from the front", () => {
  const state = createState(2);
  const first = messageEvent({ text: "m0" });
  assert.equal(applyEvent(state, first), first);
  applyEvent(state, messageEvent({ text: "m1" }));
  applyEvent(state, messageEvent({ text: "m2" }));
  assert.deepEqual(state.messages.map((m) => m.text), ["m1", "m2"]);
});

test("applyEvent keeps a null sender on a message", () => {
  const state = createState();
  applyEvent(state, messageEvent({ from: null }));
  assert.equal(state.messages[0].from, null);
});

test("findSessionByName prefers a live session over an ended one with the same name", () => {
  const state = createState();
  applyEvent(state, sessionEvent({ pid: 1, session: "same-aa", state: "ended" }));
  applyEvent(state, sessionEvent({ pid: 2, session: "same-aa", state: "idle" }));
  assert.equal(findSessionByName(state, "same-aa").pid, 2);
  applyEvent(state, sessionEvent({ pid: 2, session: "same-aa", state: "ended" }));
  assert.equal(findSessionByName(state, "same-aa").pid, 1);
  assert.equal(findSessionByName(state, "nobody"), undefined);
});

test("snapshot sorts sessions by ts ascending and copies the message list", () => {
  const state = createState();
  applyEvent(state, sessionEvent({ pid: 2, ts: "2026-10-05T21:40:05Z" }));
  applyEvent(state, sessionEvent({ pid: 1, ts: "2026-10-05T21:40:01Z" }));
  applyEvent(state, messageEvent());
  const snap = snapshot(state);
  assert.deepEqual(snap.sessions.map((s) => s.pid), [1, 2]);
  assert.deepEqual(snap.messages, state.messages);
  assert.notEqual(snap.messages, state.messages);
  assert.deepEqual(snapshot(createState()), { sessions: [], messages: [] });
});
