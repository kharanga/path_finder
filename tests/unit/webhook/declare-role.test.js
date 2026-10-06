import { test } from "node:test";
import assert from "node:assert/strict";
import { parseRole, resolveCallingSession, buildRoleEvent, main } from "../../../webhook/declare-role.js";
import { validateEvent } from "../../../webhook/schema.js";

test("parseRole trims and accepts letters, digits, spaces, underscores, and dashes up to 40 characters", () => {
  assert.equal(parseRole(["  manager "]), "manager");
  assert.equal(parseRole(["webhook-builder 2_x"]), "webhook-builder 2_x");
  assert.equal(parseRole(["a".repeat(40)]), "a".repeat(40));
});

test("parseRole throws the usage error for missing, empty, too long, or badly shaped roles", () => {
  for (const argv of [[], [""], ["   "], ["bad/role!"], ["a".repeat(41)], ["-leading"], [" _x"], ["tab\there"]]) {
    assert.throws(() => parseRole(argv), /^Error: usage: declare-role\.js <role>/, JSON.stringify(argv));
  }
});

test("resolveCallingSession combines the pid walk and registry lookup", () => {
  const calls = [];
  const resolved = resolveCallingSession({ findPid: () => 7, lookup: (pid) => { calls.push(pid); return { pid, name: "x-1", cwd: "/a/b/listings", status: "idle" }; } });
  assert.deepEqual(resolved, { pid: 7, name: "x-1", folder: "listings", state: "idle" });
  assert.deepEqual(calls, [7]);
});

test("resolveCallingSession falls back to busy for unknown, ended, or missing statuses and empty folder for a missing cwd", () => {
  for (const status of ["weird", "ended", null, undefined]) {
    const resolved = resolveCallingSession({ findPid: () => 1, lookup: () => ({ pid: 1, name: null, cwd: null, status }) });
    assert.deepEqual(resolved, { pid: 1, name: null, folder: "", state: "busy" }, String(status));
  }
  assert.equal(resolveCallingSession({ findPid: () => 1, lookup: () => ({ pid: 1, name: "n", cwd: "/x", status: "waiting" }) }).state, "waiting");
});

test("resolveCallingSession throws one-line errors when the pid or registry entry is missing", () => {
  assert.throws(() => resolveCallingSession({ findPid: () => null }), /^Error: declare-role: no claude process found above this one$/);
  assert.throws(() => resolveCallingSession({ findPid: () => 999999, lookup: () => null }), /^Error: declare-role: no registry entry for claude pid 999999$/);
});

test("buildRoleEvent produces a valid session event carrying the role", () => {
  const event = buildRoleEvent({ pid: 29904, name: "listings-bc", folder: "listings", state: "idle" }, "validator", new Date("2026-10-05T21:40:00Z"));
  assert.deepEqual(event, { ts: "2026-10-05T21:40:00.000Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: "validator" });
  assert.equal(validateEvent(event).ok, true);
  assert.equal(validateEvent(buildRoleEvent({ pid: 1, name: null, folder: "", state: "busy" }, "m")).ok, true);
});

test("main returns 1 and writes exactly one stderr line for a bad role without touching the file system", (t) => {
  const written = [];
  t.mock.method(process.stderr, "write", (chunk) => { written.push(String(chunk)); return true; });
  assert.equal(main(["!!"]), 1);
  assert.deepEqual(written, ["usage: declare-role.js <role>   (1-40 letters, digits, spaces, _ or -)\n"]);
});
