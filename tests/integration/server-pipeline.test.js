import { test } from "node:test";
import assert from "node:assert/strict";
import { appendFileSync, writeFileSync, readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { startServer } from "../../webhook/server.js";
import { parseArgs, createGenerator, runScenario } from "../../webhook/fake.js";
import { parseEventLine } from "../../webhook/schema.js";
import { findClaudeAncestorPid } from "../../webhook/hooks/dashboard-hook.js";
import { createState as createPageState, applySnapshot, applyEvent, sessionByName, liveSessions } from "../../frontend/state.js";
import { makeTmpDir } from "../helpers/tmp-dir.js";
import { connectSse } from "../helpers/sse-client.js";

const DECLARE_ROLE = fileURLToPath(new URL("../../webhook/declare-role.js", import.meta.url));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const line = (event) => `${JSON.stringify(event)}\n`;
const sessionEvent = (overrides) => ({ ts: "2026-10-05T21:40:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "busy", role: null, ...overrides });

const generated = async (extra = []) => {
  const options = parseArgs(["--out", "/unused", "--instant", "--start-time", "2026-10-05T21:40:00Z", ...extra]);
  const entries = [];
  const generator = createGenerator(options, { write: (entry) => entries.push(entry), noChildren: true });
  await runScenario(generator, options);
  return entries.filter((entry) => entry.event !== "liveness").map((entry) => entry.data);
};

const serverOn = async (t, eventsPath, overrides = {}) => {
  const started = await startServer({ eventsPath, port: 0, host: "127.0.0.1", livenessIntervalMs: 0, pollMs: 20, ...overrides });
  t.after(() => started.stop());
  const base = `http://127.0.0.1:${started.server.address().port}`;
  const snapshot = async () => (await fetch(`${base}/snapshot`)).json();
  const client = () => {
    const sse = connectSse(`${base}/events`);
    t.after(() => sse.close());
    return sse;
  };
  return { ...started, base, snapshot, client };
};

const tempEvents = (t, content = "") => {
  const { path, cleanup } = makeTmpDir();
  t.after(cleanup);
  const eventsPath = join(path, "events.jsonl");
  writeFileSync(eventsPath, content);
  return { dir: path, eventsPath };
};

test("generator output replays into the server and a connected client receives a correct snapshot and live frames", async (t) => {
  const events = await generated(["--sessions", "6", "--duration", "10"]);
  const head = events.slice(0, 20);
  const tail = events.slice(20, 30);
  const { eventsPath } = tempEvents(t, head.map(line).join(""));
  const { hub, snapshot, client } = await serverOn(t, eventsPath);
  assert.equal(hub.stats.eventsApplied, 20);
  const page = createPageState();
  const sse = client();
  await sse.waitFor((frames) => frames.some((f) => f.event === "snapshot"));
  const snapshotFrame = sse.frames.find((f) => f.event === "snapshot");
  applySnapshot(page, snapshotFrame.data, 0);
  assert.equal(page.sessions.size, new Set(head.filter((e) => e.type === "session").map((e) => e.pid)).size);
  appendFileSync(eventsPath, tail.map(line).join(""));
  await sse.waitFor((frames) => frames.filter((f) => f.event === "session" || f.event === "message").length === tail.length);
  const live = sse.frames.filter((f) => f.event === "session" || f.event === "message");
  assert.deepEqual(live.map((f) => f.event), tail.map((e) => e.type));
  for (const frame of live) applyEvent(page, frame.event, frame.data, 0);
  const expected = (await snapshot()).sessions.map((s) => [s.pid, s.state, s.session]).sort();
  const actual = [...page.sessions.values()].map((s) => [s.pid, s.state, s.session]).sort();
  assert.deepEqual(actual, expected);
  assert.equal(hub.stats.eventsApplied, 30);
});

test("a client connecting mid-run gets the state so far, and malformed lines are skipped and counted", async (t) => {
  const { eventsPath } = tempEvents(t, line(sessionEvent()) + "not json\n");
  const { hub, snapshot, client } = await serverOn(t, eventsPath);
  assert.deepEqual([hub.stats.linesRead, hub.stats.malformedLines, hub.stats.eventsApplied], [2, 1, 1]);
  appendFileSync(eventsPath, line({ ts: "2026-10-05T21:40:05Z", type: "message", from: "listings-bc", to: "tag-analyzer-63", text: "L16", notify_on_idle: true }) + '{"ts":"bad"}\n\n');
  await sleep(80);
  const mid = await snapshot();
  assert.deepEqual(mid.sessions.map((s) => [s.pid, s.state]), [[29904, "busy"]]);
  assert.deepEqual(mid.messages.map((m) => m.text), ["L16"]);
  assert.deepEqual([mid.stats.linesRead, mid.stats.malformedLines, mid.stats.eventsApplied], [5, 2, 2]);
  const late = client();
  await late.waitFor((frames) => frames.some((f) => f.event === "snapshot"));
  const frame = late.frames.find((f) => f.event === "snapshot");
  assert.deepEqual(frame.data.messages.map((m) => m.text), ["L16"]);
  assert.equal(frame.data.sessions[0].state, "busy");
  appendFileSync(eventsPath, line(sessionEvent({ ts: "2026-10-05T21:41:00Z", state: "idle" })));
  await late.waitFor((frames) => frames.some((f) => f.event === "session"));
  assert.equal(late.frames.at(-1).data.state, "idle");
});

test("liveness with a mocked pid check marks dead sessions ended within one interval and corrects state from a mocked registry", async (t) => {
  const { eventsPath } = tempEvents(t, line(sessionEvent({ pid: 1, session: "a-1", folder: "a" })) + line(sessionEvent({ pid: 2, session: null, folder: "b", state: "idle" })));
  const alive = new Set([1, 2]);
  const registry = new Map();
  const { snapshot, client } = await serverOn(t, eventsPath, {
    livenessIntervalMs: 30,
    isAlive: (pid) => alive.has(pid),
    readStatus: (pid) => registry.get(pid) ?? null,
  });
  const sse = client();
  await sse.waitFor((frames) => frames.some((f) => f.event === "snapshot"));
  alive.delete(1);
  await sse.waitFor((frames) => frames.some((f) => f.event === "liveness"));
  const ended = sse.frames.find((f) => f.event === "liveness").data;
  assert.deepEqual([ended.pid, ended.state, ended.session], [1, "ended", "a-1"]);
  registry.set(2, { status: "busy", name: "b-2", statusUpdatedAt: Date.now() });
  await sse.waitFor((frames) => frames.some((f) => f.event === "session" && f.data.pid === 2));
  const corrected = sse.frames.find((f) => f.event === "session" && f.data.pid === 2).data;
  assert.deepEqual([corrected.session, corrected.state], ["b-2", "busy"]);
  const snap = await snapshot();
  assert.deepEqual(snap.sessions.map((s) => [s.pid, s.state, s.session]).sort(), [[1, "ended", "a-1"], [2, "busy", "b-2"]]);
  assert.equal(snap.stats.livenessEnded, 1);
  assert.equal(snap.stats.statusCorrections, 1);
  const page = createPageState();
  applySnapshot(page, sse.frames[1].data, 0);
  for (const frame of sse.frames.slice(2)) applyEvent(page, frame.event, frame.data, 0);
  assert.deepEqual(liveSessions(page).map((s) => s.pid), [2]);
});

test("the generator's rename scenario streams through the server and the page keeps the former name resolvable", async (t) => {
  const events = await generated();
  const namesByPid = new Map();
  for (const e of events) if (e.type === "session" && e.session) namesByPid.set(e.pid, [...new Set([...(namesByPid.get(e.pid) ?? []), e.session])]);
  const [renamedPid, names] = [...namesByPid.entries()].find(([, list]) => list.length >= 2);
  const renameIndex = events.findIndex((e) => e.type === "session" && e.pid === renamedPid && e.session === names[1]);
  const { eventsPath } = tempEvents(t, events.slice(0, renameIndex).map(line).join(""));
  const { snapshot, client } = await serverOn(t, eventsPath);
  const sse = client();
  await sse.waitFor((frames) => frames.some((f) => f.event === "snapshot"));
  const page = createPageState();
  applySnapshot(page, sse.frames.find((f) => f.event === "snapshot").data, 0);
  assert.equal(page.sessions.get(renamedPid).session, names[0]);
  const rest = events.slice(renameIndex);
  appendFileSync(eventsPath, rest.map(line).join(""));
  await sse.waitFor((frames) => frames.filter((f) => f.event === "session" || f.event === "message").length === rest.length, 5000);
  for (const frame of sse.frames.filter((f) => f.event === "session" || f.event === "message")) applyEvent(page, frame.event, frame.data, 0);
  const renamed = page.sessions.get(renamedPid);
  assert.equal(renamed.session, names[1]);
  assert.deepEqual(renamed.formerNames, [names[0]]);
  assert.equal(sessionByName(page, names[0]).pid, renamedPid);
  assert.equal(page.placeholders.has(names[0]), false);
  const serverView = (await snapshot()).sessions.find((s) => s.pid === renamedPid);
  assert.equal(serverView.session, names[1]);
});

test("declare-role.js against the temp events file reaches a connected client with the role", async (t) => {
  if (findClaudeAncestorPid() === null) {
    t.skip("needs to run inside a Claude Code session");
    return;
  }
  const { dir, eventsPath } = tempEvents(t);
  const rolesPath = join(dir, "roles.json");
  const { snapshot, client } = await serverOn(t, eventsPath);
  const sse = client();
  await sse.waitFor((frames) => frames.some((f) => f.event === "snapshot"));
  const output = execFileSync(process.execPath, [DECLARE_ROLE, "integration-test"], { env: { ...process.env, CC_DASHBOARD_EVENTS: eventsPath, CC_DASHBOARD_ROLES: rolesPath }, stdio: ["ignore", "pipe", "pipe"] }).toString();
  assert.equal(output, "");
  await sse.waitFor((frames) => frames.some((f) => f.event === "session"));
  const frame = sse.frames.find((f) => f.event === "session").data;
  assert.equal(frame.role, "integration-test");
  assert.ok(Number.isInteger(frame.pid));
  assert.equal(parseEventLine(readFileSync(eventsPath, "utf8").trim()).role, "integration-test");
  assert.equal((await snapshot()).sessions[0].role, "integration-test");
  assert.equal(Object.values(JSON.parse(readFileSync(rolesPath, "utf8")))[0], "integration-test");
});
