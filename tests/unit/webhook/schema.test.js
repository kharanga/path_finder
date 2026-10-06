import { test } from "node:test";
import assert from "node:assert/strict";
import { validateEvent, parseEventLine, SESSION_STATES } from "../../../webhook/schema.js";

const session = { ts: "2026-10-05T21:40:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "started", role: null };
const message = { ts: "2026-10-05T21:40:05Z", type: "message", from: "listings-bc", to: "tag-analyzer-63", text: "L16 is ready", notify_on_idle: true };

test("SESSION_STATES lists the five §3 states in order", () => {
  assert.deepEqual(SESSION_STATES, ["started", "busy", "waiting", "idle", "ended"]);
});

test("validateEvent accepts a well-formed session and message", () => {
  assert.deepEqual(validateEvent(session), { ok: true, errors: [] });
  assert.deepEqual(validateEvent(message), { ok: true, errors: [] });
});

test("validateEvent accepts every state, a null session name, a null role, and a null sender", () => {
  for (const state of SESSION_STATES) assert.equal(validateEvent({ ...session, state }).ok, true, state);
  assert.equal(validateEvent({ ...session, session: null, role: null }).ok, true);
  assert.equal(validateEvent({ ...message, from: null }).ok, true);
});

test("validateEvent rejects non-objects", () => {
  for (const value of [null, undefined, "nope", 1, true, []]) {
    assert.deepEqual(validateEvent(value), { ok: false, errors: ["event must be an object"] });
  }
});

test("validateEvent reports every session field problem at once", () => {
  assert.deepEqual(validateEvent({ ts: "bad", type: "session", session: 1, folder: 2, pid: 0, state: "sleeping", role: 3, extra: 1 }), {
    ok: false,
    errors: [
      "ts must be an ISO 8601 string",
      "session must be a string or null",
      "folder must be a string",
      "pid must be a positive integer",
      "state must be one of started, busy, waiting, idle, ended",
      "role must be a string or null",
      "unknown field extra",
    ],
  });
});

test("validateEvent rejects non-integer, negative, and string pids", () => {
  for (const pid of [1.5, -1, "29904", null]) assert.equal(validateEvent({ ...session, pid }).ok, false, String(pid));
});

test("validateEvent reports every message field problem at once", () => {
  assert.deepEqual(validateEvent({ ts: "2026-10-05T21:40:05Z", type: "message", from: 1, to: null, text: 2, notify_on_idle: "yes", bonus: 0 }), {
    ok: false,
    errors: ["from must be a string or null", "to must be a string", "text must be a string", "notify_on_idle must be a boolean", "unknown field bonus"],
  });
});

test("validateEvent rejects unknown and missing types", () => {
  assert.deepEqual(validateEvent({ ts: "2026-10-05T21:40:00Z", type: "other" }).errors, ["type must be session or message"]);
  assert.deepEqual(validateEvent({ ts: "2026-10-05T21:40:00Z" }).errors, ["type must be session or message"]);
});

test("parseEventLine returns the event for a valid line and null otherwise", () => {
  assert.deepEqual(parseEventLine(`  ${JSON.stringify(session)}  `), session);
  assert.equal(parseEventLine(""), null);
  assert.equal(parseEventLine("   "), null);
  assert.equal(parseEventLine("not json"), null);
  assert.equal(parseEventLine('{"ts":"bad"}'), null);
  assert.equal(parseEventLine(JSON.stringify({ ...session, state: "sleeping" })), null);
  assert.equal(parseEventLine("[1,2]"), null);
});
