import { test } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, readFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { stateForHook, lookupSessionRegistry, lookupSessionRegistryByPid, readSessionRegistry, resolveSession, buildEvent, appendEvent, DEFAULT_EVENTS_PATH } from "../../../webhook/hooks/dashboard-hook.js";
import { validateEvent } from "../../../webhook/schema.js";
import { makeTmpDir } from "../../helpers/tmp-dir.js";

const HOOK = fileURLToPath(new URL("../../../webhook/hooks/dashboard-hook.js", import.meta.url));
const at = new Date("2026-10-05T21:40:00Z");

const registryDir = (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  writeFileSync(join(path, "123.json"), JSON.stringify({ pid: 123, sessionId: "sid-a", name: "listings-bc", cwd: "/x/listings", status: "busy" }));
  writeFileSync(join(path, "124.json"), "not json");
  writeFileSync(join(path, "125.json"), JSON.stringify({ pid: 125, sessionId: "sid-c" }));
  writeFileSync(join(path, "126.json"), JSON.stringify({ pid: "126", sessionId: "sid-d", name: "bad-pid" }));
  writeFileSync(join(path, "notes.txt"), JSON.stringify({ pid: 127, sessionId: "sid-e" }));
  return path;
};

test("DEFAULT_EVENTS_PATH is the dashboard file under the home directory", () => {
  assert.ok(DEFAULT_EVENTS_PATH.endsWith("/.claude/dashboard/events.jsonl"));
});

test("stateForHook maps each hook to its §3 state and everything else to null", () => {
  assert.equal(stateForHook({ hook_event_name: "SessionStart" }), "started");
  assert.equal(stateForHook({ hook_event_name: "UserPromptSubmit" }), "busy");
  assert.equal(stateForHook({ hook_event_name: "Stop" }), "idle");
  assert.equal(stateForHook({ hook_event_name: "SessionEnd" }), "ended");
  assert.equal(stateForHook({ hook_event_name: "Notification", notification_type: "permission_prompt" }), "waiting");
  assert.equal(stateForHook({ hook_event_name: "Notification", notification_type: "idle_prompt" }), null);
  assert.equal(stateForHook({ hook_event_name: "Notification" }), null);
  for (const name of ["PreToolUse", "PostToolUse", "SubagentStop", "PreCompact", undefined]) assert.equal(stateForHook({ hook_event_name: name }), null, String(name));
});

test("readSessionRegistry lists parseable <pid>.json entries with typed fields", (t) => {
  const dir = registryDir(t);
  const entries = readSessionRegistry(dir).sort((a, b) => a.pid - b.pid);
  assert.deepEqual(entries.map((e) => e.pid), [123, 125]);
  assert.deepEqual(entries[0], { pid: 123, sessionId: "sid-a", name: "listings-bc", cwd: "/x/listings", status: "busy" });
  assert.deepEqual(entries[1], { pid: 125, sessionId: "sid-c", name: null, cwd: null, status: null });
  assert.deepEqual(readSessionRegistry(join(dir, "missing")), []);
});

test("lookupSessionRegistry matches by sessionId and returns {pid, name}", (t) => {
  const dir = registryDir(t);
  assert.deepEqual(lookupSessionRegistry("sid-a", dir), { pid: 123, name: "listings-bc" });
  assert.deepEqual(lookupSessionRegistry("sid-c", dir), { pid: 125, name: null });
  assert.equal(lookupSessionRegistry("sid-d", dir), null);
  assert.equal(lookupSessionRegistry("sid-e", dir), null);
  assert.equal(lookupSessionRegistry("nope", dir), null);
  assert.equal(lookupSessionRegistry("sid-a", join(dir, "missing")), null);
});

test("lookupSessionRegistryByPid returns the entry for one pid or null", (t) => {
  const dir = registryDir(t);
  assert.equal(lookupSessionRegistryByPid(123, dir).name, "listings-bc");
  assert.equal(lookupSessionRegistryByPid(126, dir), null);
  assert.equal(lookupSessionRegistryByPid(999, dir), null);
});

test("resolveSession prefers the registry and falls back to the injected process walk", (t) => {
  const dir = registryDir(t);
  let walked = 0;
  const findPid = () => { walked += 1; return 4242; };
  assert.deepEqual(resolveSession({ session_id: "sid-a" }, { sessionsDir: dir, findPid }), { pid: 123, name: "listings-bc" });
  assert.equal(walked, 0);
  assert.deepEqual(resolveSession({ session_id: "nope" }, { sessionsDir: dir, findPid }), { pid: 4242, name: null });
  assert.equal(walked, 1);
  assert.deepEqual(resolveSession({ session_id: "nope" }, { sessionsDir: dir, findPid: () => null }), { pid: null, name: null });
});

test("buildEvent produces a session event for each state hook with the folder basename", () => {
  const identity = { pid: 29904, name: "listings-bc" };
  const built = buildEvent({ hook_event_name: "Stop", cwd: "/Users/k/listings" }, identity, at);
  assert.deepEqual(built, { ts: "2026-10-05T21:40:00.000Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: null });
  assert.equal(buildEvent({ hook_event_name: "SessionStart", cwd: "/a/b/" }, identity, at).folder, "b");
  assert.equal(buildEvent({ hook_event_name: "SessionStart" }, identity, at).folder, "");
  assert.equal(buildEvent({ hook_event_name: "Notification", notification_type: "permission_prompt", cwd: "/x" }, identity, at).state, "waiting");
  assert.equal(buildEvent({ hook_event_name: "SessionEnd", cwd: "/x" }, { pid: 7, name: null }, at).session, null);
});

test("buildEvent produces a message event from a SendMessage PostToolUse with defaults", () => {
  const identity = { pid: 29904, name: "listings-bc" };
  const full = buildEvent({ hook_event_name: "PostToolUse", tool_name: "SendMessage", cwd: "/x", tool_input: { to: "tag-analyzer-63", message: "L16 is ready", notify_when_idle: true } }, identity, at);
  assert.deepEqual(full, { ts: "2026-10-05T21:40:00.000Z", type: "message", from: "listings-bc", to: "tag-analyzer-63", text: "L16 is ready", notify_on_idle: true });
  const sparse = buildEvent({ hook_event_name: "PostToolUse", tool_name: "SendMessage", tool_input: { to: "a" } }, { pid: 1, name: null }, at);
  assert.deepEqual([sparse.from, sparse.text, sparse.notify_on_idle], [null, "", false]);
  assert.equal(buildEvent({ hook_event_name: "PostToolUse", tool_name: "SendMessage", tool_input: { to: "a", notify_when_idle: "yes" } }, identity, at).notify_on_idle, false);
});

test("buildEvent returns null for hooks that are not logged or identities without a pid", () => {
  assert.equal(buildEvent({ hook_event_name: "PostToolUse", tool_name: "Bash", cwd: "/x" }, { pid: 1, name: null }, at), null);
  assert.equal(buildEvent({ hook_event_name: "PreToolUse", tool_name: "SendMessage", tool_input: { to: "a" } }, { pid: 1, name: null }, at), null);
  assert.equal(buildEvent({ hook_event_name: "PostToolUse", tool_name: "SendMessage", tool_input: {} }, { pid: 1, name: "n" }, at), null);
  assert.equal(buildEvent({ hook_event_name: "PostToolUse", tool_name: "SendMessage" }, { pid: 1, name: "n" }, at), null);
  assert.equal(buildEvent({ hook_event_name: "Stop", cwd: "/x" }, { pid: null, name: null }, at), null);
  assert.equal(buildEvent({ hook_event_name: "Stop", cwd: "/x" }, { pid: 1.5, name: null }, at), null);
});

test("every event buildEvent produces passes the schema", () => {
  const identity = { pid: 29904, name: "listings-bc" };
  const inputs = [
    { hook_event_name: "SessionStart", cwd: "/x" },
    { hook_event_name: "UserPromptSubmit", cwd: "/x" },
    { hook_event_name: "Notification", notification_type: "permission_prompt", cwd: "/x" },
    { hook_event_name: "Stop", cwd: "/x" },
    { hook_event_name: "SessionEnd", cwd: "/x" },
    { hook_event_name: "PostToolUse", tool_name: "SendMessage", tool_input: { to: "a" } },
  ];
  for (const input of inputs) assert.equal(validateEvent(buildEvent(input, identity, at)).ok, true, input.hook_event_name);
  assert.equal(validateEvent(buildEvent(inputs[5], { pid: 1, name: null }, at)).ok, true);
});

test("appendEvent creates the directory, appends one JSON line, and returns false on failure", (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  const file = join(path, "nested", "events.jsonl");
  assert.equal(appendEvent(file, { a: 1 }), true);
  assert.equal(appendEvent(file, { b: 2 }), true);
  assert.equal(readFileSync(file, "utf8"), '{"a":1}\n{"b":2}\n');
  assert.equal(appendEvent("/nonexistent-root/e.jsonl", { a: 1 }), false);
});

test("the hook script exits 0 silently for every input and writes only to CC_DASHBOARD_EVENTS", (t) => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  const file = join(path, "events.jsonl");
  const run = (input, eventsPath = file) => {
    const result = { stdout: "", stderr: "", status: 0 };
    try {
      result.stdout = execFileSync(process.execPath, [HOOK], { input, env: { ...process.env, CC_DASHBOARD_EVENTS: eventsPath }, stdio: ["pipe", "pipe", "pipe"] }).toString();
    } catch (error) {
      result.status = error.status;
      result.stderr = String(error.stderr);
    }
    return result;
  };
  const waiting = JSON.stringify({ session_id: "unknown-sid", hook_event_name: "Notification", notification_type: "permission_prompt", cwd: "/a/path_finder" });
  const message = JSON.stringify({ session_id: "unknown-sid", hook_event_name: "PostToolUse", tool_name: "SendMessage", cwd: "/x", tool_input: { to: "listings-bc", message: "hi", notify_when_idle: true } });
  for (const input of [waiting, message, "garbage", "", JSON.stringify({ session_id: "u", hook_event_name: "Notification", notification_type: "idle_prompt" })]) {
    assert.deepEqual(run(input), { stdout: "", stderr: "", status: 0 }, input.slice(0, 30));
  }
  const lines = readFileSync(file, "utf8").trim().split("\n").map((line) => JSON.parse(line));
  assert.equal(lines.length, 2);
  assert.deepEqual([lines[0].type, lines[0].state, lines[0].folder, lines[0].session], ["session", "waiting", "path_finder", null]);
  assert.ok(Number.isInteger(lines[0].pid));
  assert.deepEqual([lines[1].type, lines[1].from, lines[1].to, lines[1].text, lines[1].notify_on_idle], ["message", null, "listings-bc", "hi", true]);
  assert.deepEqual(run(waiting, "/nonexistent-root/x/events.jsonl"), { stdout: "", stderr: "", status: 0 });
  assert.equal(existsSync("/nonexistent-root"), false);
});
