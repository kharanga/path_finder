import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { saveRole } from "../../../webhook/declare-role.js";
import { readSavedRole, buildEvent, DEFAULT_ROLES_PATH } from "../../../webhook/hooks/dashboard-hook.js";
import { makeTmpDir } from "../../helpers/tmp-dir.js";

const at = new Date("2026-10-05T21:40:00Z");

test("DEFAULT_ROLES_PATH sits next to the events file", () => {
  assert.ok(DEFAULT_ROLES_PATH.endsWith("/.claude/dashboard/roles.json"));
});

test("saveRole creates the file and directory, merges by start folder, and replaces an existing role", (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  const file = join(path, "nested", "roles.json");
  assert.equal(saveRole(file, "/a/one", "manager"), true);
  assert.equal(saveRole(file, "/a/two", "validator"), true);
  assert.equal(saveRole(file, "/a/one", "reviewer"), true);
  assert.deepEqual(JSON.parse(readFileSync(file, "utf8")), { "/a/one": "reviewer", "/a/two": "validator" });
});

test("saveRole starts fresh when the file is malformed or not an object and refuses a missing cwd", (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  const file = join(path, "roles.json");
  writeFileSync(file, "{bad");
  assert.equal(saveRole(file, "/a", "x"), true);
  assert.deepEqual(JSON.parse(readFileSync(file, "utf8")), { "/a": "x" });
  writeFileSync(file, "[1,2]");
  assert.equal(saveRole(file, "/b", "y"), true);
  assert.deepEqual(JSON.parse(readFileSync(file, "utf8")), { "/b": "y" });
  assert.equal(saveRole(file, null, "x"), false);
  assert.equal(saveRole(file, "", "x"), false);
  assert.equal(saveRole("/nonexistent-root/roles.json", "/a", "x"), false);
  assert.equal(existsSync("/nonexistent-root"), false);
});

test("readSavedRole returns the role for the exact start folder and null otherwise", (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  const file = join(path, "roles.json");
  writeFileSync(file, JSON.stringify({ "/a/one": "manager", "/a/two": 5 }));
  assert.equal(readSavedRole("/a/one", file), "manager");
  assert.equal(readSavedRole("/a/two", file), null);
  assert.equal(readSavedRole("/a/one/", file), null);
  assert.equal(readSavedRole("/other", file), null);
  assert.equal(readSavedRole(null, file), null);
  assert.equal(readSavedRole("", file), null);
  assert.equal(readSavedRole("/a/one", join(path, "missing.json")), null);
  writeFileSync(file, "{bad");
  assert.equal(readSavedRole("/a/one", file), null);
});

test("saveRole and readSavedRole round-trip", (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  const file = join(path, "roles.json");
  saveRole(file, "/Users/x/path_finder", "validator");
  assert.equal(readSavedRole("/Users/x/path_finder", file), "validator");
});

test("buildEvent carries a saved role on session events and null when none is known", () => {
  const withRole = buildEvent({ hook_event_name: "SessionStart", cwd: "/x/listings" }, { pid: 1, name: "listings-bc", role: "validator" }, at);
  assert.equal(withRole.role, "validator");
  const without = buildEvent({ hook_event_name: "SessionStart", cwd: "/x/listings" }, { pid: 1, name: "listings-bc" }, at);
  assert.equal(without.role, null);
  const nullRole = buildEvent({ hook_event_name: "Stop", cwd: "/x" }, { pid: 1, name: null, role: null }, at);
  assert.equal(nullRole.role, null);
});
