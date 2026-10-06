import { test } from "node:test";
import assert from "node:assert/strict";
import { writeFileSync, appendFileSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { basename } from "node:path";
import { fileURLToPath } from "node:url";
import { findClaudeAncestorPid, lookupSessionRegistryByPid } from "../../webhook/hooks/dashboard-hook.js";
import { makeTmpDir } from "../helpers/tmp-dir.js";
const R = fileURLToPath(new URL("../..", import.meta.url)).replace(/\/$/, "");
const tmp = makeTmpDir("docs-examples-webhook-");
const T = tmp.path;
process.on("exit", tmp.cleanup);
const ME = findClaudeAncestorPid();
const MINE = ME === null ? null : lookupSessionRegistryByPid(ME);
const SESSION_ONLY = new Set(["hook registry", "hook ancestor", "hook main cli", "hook registry by pid", "declare cli"]);
const skipReason = (name) => (SESSION_ONLY.has(name) && !MINE ? "needs a Claude Code session with a registry entry" : false);
const J = JSON.stringify;
const check = (name, fn) => test(name, { skip: skipReason(name) }, fn);
const checkAsync = (name, fn) => test(name, { skip: skipReason(name) }, fn);

const schema = await import(`${R}/webhook/schema.js`);
check("schema validate ok session", () => assert.deepEqual(schema.validateEvent({ ts: "2026-10-05T21:40:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "started", role: null }), { ok: true, errors: [] }));
check("schema validate ok message", () => assert.deepEqual(schema.validateEvent({ ts: "2026-10-05T21:40:05Z", type: "message", from: "listings-bc", to: "tag-analyzer-63", text: "L16 is ready, look at it", notify_on_idle: true }), { ok: true, errors: [] }));
check("schema validate errors", () => assert.deepEqual(schema.validateEvent({ ts: "bad", type: "session", session: 1, folder: "x", pid: 0, state: "sleeping", role: null, extra: 1 }), { ok: false, errors: ["ts must be an ISO 8601 string", "session must be a string or null", "pid must be a positive integer", "state must be one of started, busy, waiting, idle, ended, removed", "unknown field extra"] }));
check("schema validate nope", () => assert.deepEqual(schema.validateEvent("nope"), { ok: false, errors: ["event must be an object"] }));
check("schema parse", () => assert.deepEqual(schema.parseEventLine('{"ts":"2026-10-05T21:40:00Z","type":"session","session":null,"folder":"listings","pid":29904,"state":"busy","role":null}'), { ts: "2026-10-05T21:40:00Z", type: "session", session: null, folder: "listings", pid: 29904, state: "busy", role: null }));
check("schema parse nulls", () => { assert.equal(schema.parseEventLine("not json"), null); assert.equal(schema.parseEventLine(""), null); assert.equal(schema.parseEventLine('{"ts":"bad"}'), null); });
check("schema states", () => assert.deepEqual(schema.SESSION_STATES, ["started", "busy", "waiting", "idle", "ended", "removed"]));

const st = await import(`${R}/webhook/state.js`);
check("state create", () => { const s = st.createState(2); assert.equal(s.sessions.size, 0); assert.deepEqual(s.messages, []); assert.equal(s.messageLimit, 2); });
const state = st.createState(2);
st.applyEvent(state, { ts: "2026-10-05T21:40:00Z", type: "session", session: null, folder: "listings", pid: 29904, state: "started", role: null });
st.applyEvent(state, { ts: "2026-10-05T21:40:01Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "busy", role: null });
const stored = st.applyEvent(state, { ts: "2026-10-05T21:40:02Z", type: "session", session: null, folder: "listings", pid: 29904, state: "idle", role: null });
check("state merge", () => assert.equal(J(stored), '{"ts":"2026-10-05T21:40:02Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"idle","role":null}'));
for (const i of [0, 1, 2]) st.applyEvent(state, { ts: `2026-10-05T21:41:0${i}Z`, type: "message", from: "a", to: "b", text: `m${i}`, notify_on_idle: false });
check("state cap", () => assert.deepEqual(state.messages.map((m) => m.text), ["m1", "m2"]));
check("state findByName", () => { assert.equal(st.findSessionByName(state, "listings-bc").pid, 29904); assert.equal(st.findSessionByName(state, "nobody"), undefined); });
check("state snapshot", () => assert.equal(J(st.snapshot(state)), '{"sessions":[{"ts":"2026-10-05T21:40:02Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"idle","role":null}],"messages":[{"ts":"2026-10-05T21:41:01Z","type":"message","from":"a","to":"b","text":"m1","notify_on_idle":false},{"ts":"2026-10-05T21:41:02Z","type":"message","from":"a","to":"b","text":"m2","notify_on_idle":false}]}'));

const lv = await import(`${R}/webhook/liveness.js`);
check("liveness pid", () => { assert.equal(lv.isPidAlive(process.pid), true); assert.equal(lv.isPidAlive(2147483646), false); });
check("liveness socket", () => assert.equal(lv.hasSocket(1, "/tmp/definitely-missing-dir"), false));
mkdirSync(`${T}/registry-example`, { recursive: true });
writeFileSync(`${T}/registry-example/4242.json`, '{"pid":4242,"name":"listings-bc","status":"busy","statusUpdatedAt":1791266113437}');
check("liveness registry", () => { assert.equal(J(lv.readRegistryStatus(4242, `${T}/registry-example`)), '{"status":"busy","name":"listings-bc","statusUpdatedAt":1791266113437}'); assert.equal(lv.readRegistryStatus(1, `${T}/registry-example`), null); });
const ls = st.createState(); st.applyEvent(ls, { ts: "2026-10-05T21:40:02Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: null });
const now = new Date("2026-10-05T21:45:00Z");
check("liveness dead", () => { assert.equal(J(lv.findDeadSessions(ls, now, () => false)), '[{"ts":"2026-10-05T21:45:00.000Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"ended","role":null}]'); assert.deepEqual(lv.findDeadSessions(ls, now, () => true), []); });
check("liveness corrections", () => {
  assert.equal(J(lv.findStatusCorrections(ls, now, () => ({ status: "busy", name: "listings-bc", statusUpdatedAt: Date.parse("2026-10-05T21:44:00Z") }))), '[{"ts":"2026-10-05T21:45:00.000Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"busy","role":null}]');
  assert.deepEqual(lv.findStatusCorrections(ls, now, () => ({ status: "busy", name: "listings-bc", statusUpdatedAt: Date.parse("2026-10-05T21:39:00Z") })), []);
  assert.deepEqual(lv.findStatusCorrections(ls, now, () => ({ status: "idle", name: "listings-bc", statusUpdatedAt: Date.parse("2026-10-05T21:44:00Z") })), []);
  assert.deepEqual(lv.findStatusCorrections(ls, now, () => null), []);
  const anon = st.createState(); st.applyEvent(anon, { ts: "2026-10-05T21:40:00Z", type: "session", session: null, folder: "x", pid: 5, state: "busy", role: null });
  assert.equal(J(lv.findStatusCorrections(anon, now, () => ({ status: "busy", name: "x-9f", statusUpdatedAt: null }))), '[{"ts":"2026-10-05T21:45:00.000Z","type":"session","session":"x-9f","folder":"x","pid":5,"state":"busy","role":null}]');
});

const tl = await import(`${R}/webhook/tail.js`);
const tf = `${T}/tail-example.jsonl`;
check("tail readNewLines", () => {
  writeFileSync(tf, "a\nb\npartial"); let r = tl.readNewLines(tf, 0);
  assert.deepEqual([r.lines, r.carry, r.offset, r.truncated, r.missing], [["a", "b"], "partial", 11, false, false]);
  appendFileSync(tf, "-done\nc\n"); r = tl.readNewLines(tf, r.offset, r.carry); assert.deepEqual([r.lines, r.carry, r.offset], [["partial-done", "c"], "", 19]);
  writeFileSync(tf, "z\n"); r = tl.readNewLines(tf, r.offset, r.carry); assert.deepEqual([r.lines, r.truncated, r.offset], [["z"], true, 2]);
  assert.equal(tl.readNewLines(`${T}/does-not-exist.jsonl`, 0).missing, true);
});
await checkAsync("tail tailFile", async () => {
  writeFileSync(tf, "one\n"); const seen = [];
  const stop = tl.tailFile(tf, (l) => seen.push(l), { pollMs: 50, onReplayComplete: () => seen.push("<replayed>") });
  appendFileSync(tf, "two\n"); await new Promise((r) => setTimeout(r, 150)); stop();
  assert.deepEqual(seen, ["one", "<replayed>", "two"]);
});

const sv = await import(`${R}/webhook/server.js`);
check("server parseArgs", () => { assert.equal(J(sv.parseArgs(["--events", "/tmp/e", "--port", "5000", "--liveness-interval", "0", "--demo"], { port: 1, demo: false })), '{"port":5000,"demo":true,"eventsPath":"/tmp/e","livenessIntervalMs":0}'); assert.throws(() => sv.parseArgs(["--bogus"]), /unknown flag --bogus/); });
check("server sseFrame", () => assert.equal(sv.sseFrame("session", { a: 1 }), 'event: session\ndata: {"a":1}\n\n'));
const dir = `${R}/frontend`;
check("server resolveStatic", () => {
  assert.equal(sv.resolveStaticFile(dir, "/").contentType, "text/html; charset=utf-8"); assert.equal(sv.resolveStaticFile(dir, "/").filePath.endsWith("/frontend/index.html"), true);
  assert.equal(sv.resolveStaticFile(dir, "/app.js").contentType, "text/javascript; charset=utf-8"); assert.equal(sv.resolveStaticFile(dir, "/orbit.css").contentType, "text/css; charset=utf-8");
  assert.equal(sv.resolveStaticFile(dir, "/fixtures/few.json").contentType, "application/json; charset=utf-8");
  for (const p of ["/../CLAUDE.md", "/%2e%2e/CLAUDE.md", "/fixtures", "/nope.js", "/%E0%A4%A"]) assert.equal(sv.resolveStaticFile(dir, p), null, p);
});
check("server createHub", () => {
  const hub = sv.createHub({ isAlive: () => true, readStatus: () => null });
  assert.equal(hub.ingestLine('{"ts":"2026-10-05T21:40:00Z","type":"session","session":"a-1","folder":"a","pid":1,"state":"busy","role":null}').state, "busy");
  assert.equal(hub.ingestLine("not json"), null); assert.equal(hub.ingestLine(""), null);
  assert.equal(J(hub.stats), '{"linesRead":3,"malformedLines":1,"eventsApplied":1,"livenessEnded":0,"statusCorrections":0,"removals":0}');
  const frames = []; const remove = hub.addClient({ write: (f) => frames.push(f) });
  hub.ingestLine('{"ts":"2026-10-05T21:40:05Z","type":"message","from":"a-1","to":"b","text":"hi","notify_on_idle":true}');
  assert.deepEqual(frames.map((f) => f.split("\n")[0]), ["event: snapshot", "event: message"]); remove();
  assert.equal(J(hub.runLivenessCheck(new Date("2026-10-05T21:45:00Z"))), '{"ended":[],"corrections":[]}');
});
await checkAsync("server startServer", async () => {
  const ef = `${T}/server-example.jsonl`;
  writeFileSync(ef, '{"ts":"2026-10-05T21:40:00Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"started","role":null}\nnot json\n');
  const { server, hub, stop } = await sv.startServer({ eventsPath: ef, port: 0, livenessIntervalMs: 0 });
  try {
  const port = server.address().port;
  const stats = await fetch(`http://127.0.0.1:${port}/snapshot`).then((r) => r.json()).then((d) => d.stats);
  assert.equal(J(stats), '{"linesRead":2,"malformedLines":1,"eventsApplied":1,"livenessEnded":0,"statusCorrections":0,"removals":0}');
  assert.equal(hub.state.sessions.get(29904).state, "started");
  const root = await fetch(`http://127.0.0.1:${port}/`); assert.equal(root.status, 200); assert.equal(root.headers.get("content-type"), "text/html; charset=utf-8");
  const css = await fetch(`http://127.0.0.1:${port}/orbit.css`); assert.equal(css.headers.get("content-type"), "text/css; charset=utf-8");
  const post = await fetch(`http://127.0.0.1:${port}/`, { method: "POST" }); assert.equal(post.status, 405);
  const sse = await fetch(`http://127.0.0.1:${port}/events`); const reader = sse.body.getReader(); const { value } = await reader.read(); const text = new TextDecoder().decode(value);
  assert.equal(text, ': connected\n\nevent: snapshot\ndata: {"sessions":[{"ts":"2026-10-05T21:40:00Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"started","role":null}],"messages":[]}\n\n');
  await reader.cancel(); } finally {
    await stop();
  }
});

const fk = await import(`${R}/webhook/fake.js`);
check("fake createRandom", () => { assert.equal(fk.createRandom(42).hex2(), "99"); const r = fk.createRandom(42); assert.equal(r.int(1, 40), 25); assert.equal(r.hex2(), "72"); });
check("fake parseArgs", () => { assert.deepEqual(fk.parseArgs(["--fixture", "/tmp/f.json", "--sessions", "8"]), { out: null, fixture: "/tmp/f.json", speed: 1, sessions: 8, seed: 42, instant: true, durationSeconds: 60, snapshotUntilSeconds: 0, startTime: null }); assert.throws(() => fk.parseArgs([]), /--out <path> or --fixture <path> is required/); });
check("fake createGenerator", () => {
  const written = []; const g = fk.createGenerator({ instant: true, seed: 1 }, { write: (e) => written.push(e), now: () => new Date("2026-10-05T21:40:00Z") });
  const s = g.startSession("listings"); g.advance(1000); g.setState(s, "busy");
  assert.deepEqual(written.map((e) => [e.atMs, e.event, e.data.state]), [[0, "session", "started"], [1000, "session", "busy"]]);
});
await checkAsync("fake runScenario zero", async () => { const o = fk.parseArgs(["--fixture", "/tmp/x.json", "--sessions", "0"]); const g = fk.createGenerator(o, { write: () => {} }); await fk.runScenario(g, o); assert.equal(g.entries.length, 0); });
check("fake buildFixture", () => {
  const es = [{ atMs: 3000, event: "session", data: { ts: "2026-10-05T21:40:03.000Z", type: "session", session: "a-01", folder: "a", pid: 1, state: "started", role: null } }, { atMs: 5000, event: "session", data: { ts: "2026-10-05T21:40:05.000Z", type: "session", session: "a-01", folder: "a", pid: 1, state: "busy", role: null } }];
  const f = fk.buildFixture(es, 4); assert.equal(f.snapshot.sessions[0].state, "started"); assert.deepEqual(f.snapshot.messages, []); assert.equal(f.events.length, 1); assert.equal(f.events[0].delayMs, 1000); assert.equal(f.events[0].data.state, "busy");
  assert.equal(fk.buildFixture(es, 4, 4).events[0].delayMs, 250);
});
check("fake command fixture", () => {
  execFileSync(process.execPath, [`${R}/webhook/fake.js`, "--fixture", `${T}/fx.json`, "--start-time", "2026-10-05T21:40:00Z"]);
  const f = JSON.parse(readFileSync(`${T}/fx.json`, "utf8")); const ev = f.events;
  assert.equal(f.snapshot.sessions.length, 0); assert.equal(ev.length, 134);
  assert.equal(ev.filter((e) => e.event === "liveness").length, 2); assert.equal(ev.filter((e) => e.data.type === "message" && e.data.from === null).length, 1);
  assert.equal(ev.filter((e) => e.data.type === "message" && e.data.to === "ghost-session-00").length, 1); assert.equal(ev.filter((e) => e.data.notify_on_idle === true).length, 7);
  assert.equal(new Set(ev.filter((e) => e.data.type === "session" && e.data.session).map((e) => e.data.session)).size, 18);
  assert.equal(J(ev[0]), '{"delayMs":3000,"event":"session","data":{"ts":"2026-10-05T21:40:03.000Z","type":"session","session":"listings-72","folder":"listings","pid":70025,"state":"started","role":null}}');
  execFileSync(process.execPath, [`${R}/webhook/fake.js`, "--fixture", `${T}/fx2.json`, "--start-time", "2026-10-05T21:40:00Z"]); assert.equal(readFileSync(`${T}/fx.json`, "utf8"), readFileSync(`${T}/fx2.json`, "utf8"));
  execFileSync(process.execPath, [`${R}/webhook/fake.js`, "--fixture", `${T}/fast.json`, "--speed", "10", "--start-time", "2026-10-05T21:40:00Z"]);
  const fast = JSON.parse(readFileSync(`${T}/fast.json`, "utf8")); assert.equal(fast.events.reduce((a, e) => a + e.delayMs, 0) / 1000, 17.15); assert.equal(ev.reduce((a, e) => a + e.delayMs, 0) / 1000, 171.5);
});
check("fake command raw", () => {
  execFileSync(process.execPath, [`${R}/webhook/fake.js`, "--out", `${T}/raw.jsonl`, "--instant"]);
  const lines = readFileSync(`${T}/raw.jsonl`, "utf8").trim().split("\n"); assert.equal(lines.length, 132); assert.equal(lines.filter((l) => !schema.parseEventLine(l)).length, 0);
});

const cr = await import(`${R}/webhook/hooks/capture-raw.js`);
check("capture describeShape", () => { assert.deepEqual(cr.describeShape({ prompt: "hello", tool_input: { to: "x", notify_when_idle: true } }), { prompt: "string(5)", tool_input: { to: "string(1)", notify_when_idle: "boolean" } }); assert.deepEqual(cr.describeShape([1, 2, 3]), ["array(3)"]); });
check("capture redact", () => {
  const r = cr.redactHookInput({ session_id: "test-123", hook_event_name: "PostToolUse", cwd: "/tmp/x", tool_name: "SendMessage", tool_input: { to: "listings-bc", message: "hello there", notify_when_idle: true }, tool_response: { ok: true } });
  assert.deepEqual(r.kept, { session_id: "test-123", hook_event_name: "PostToolUse", cwd: "/tmp/x", tool_name: "SendMessage", tool_input: { to: "listings-bc", notify_when_idle: true } });
  assert.deepEqual(r.shape, { session_id: "string(8)", hook_event_name: "string(11)", cwd: "string(6)", tool_name: "string(11)", tool_input: { to: "string(11)", message: "string(11)", notify_when_idle: "boolean" }, tool_response: { ok: "boolean" } });
  assert.deepEqual(Object.keys(cr.redactHookInput("str")), ["shape"]); assert.deepEqual(Object.keys(cr.redactHookInput(null)), ["shape"]);
});
check("capture buildRawRecord", () => assert.deepEqual(cr.buildRawRecord("not json", [], new Date("2026-10-05T21:40:00Z")).input, { unparseable: true, length: 8 }));
check("capture appendRaw", () => assert.equal(cr.appendRaw("/nonexistent-root/raw.jsonl", { a: 1 }), false));
check("capture ancestorChain", () => { const c = cr.ancestorChain(); assert.ok(c.length >= 1); assert.ok(c.some((a) => /claude/.test(a.command))); });
check("capture main cli", () => {
  const out = execFileSync(process.execPath, [`${R}/webhook/hooks/capture-raw.js`, `${T}/raw-test.jsonl`], { input: '{"session_id":"test-123","hook_event_name":"Stop","cwd":"/tmp/x","stop_hook_active":false}' });
  assert.equal(out.toString(), ""); const rec = JSON.parse(readFileSync(`${T}/raw-test.jsonl`, "utf8").trim().split("\n").pop());
  assert.deepEqual(rec.input.kept, { session_id: "test-123", hook_event_name: "Stop", cwd: "/tmp/x", stop_hook_active: false });
});

const hk = await import(`${R}/webhook/hooks/dashboard-hook.js`);
check("hook stateForHook", () => { assert.equal(hk.stateForHook({ hook_event_name: "Notification", notification_type: "permission_prompt" }), "waiting"); assert.equal(hk.stateForHook({ hook_event_name: "Notification", notification_type: "idle_prompt" }), null); assert.equal(hk.stateForHook({ hook_event_name: "PreToolUse" }), null); });
check("hook registry", () => { assert.equal(hk.lookupSessionRegistry("nope"), null); assert.equal(hk.lookupSessionRegistry("x", "/nonexistent"), null); const mine = hk.lookupSessionRegistry(MINE.sessionId); assert.equal(J(mine), J({ pid: ME, name: MINE.name })); });
check("hook ancestor", () => assert.equal(hk.findClaudeAncestorPid(), ME));
check("hook resolveSession", () => assert.equal(J(hk.resolveSession({ session_id: "nope" }, { findPid: () => 4242 })), '{"pid":4242,"name":null}'));
check("hook buildEvent", () => {
  assert.equal(J(hk.buildEvent({ hook_event_name: "Stop", cwd: "/Users/k/listings" }, { pid: 29904, name: "listings-bc" }, new Date("2026-10-05T21:40:00Z"))), '{"ts":"2026-10-05T21:40:00.000Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"idle","role":null}');
  assert.equal(J(hk.buildEvent({ hook_event_name: "PostToolUse", tool_name: "SendMessage", cwd: "/x", tool_input: { to: "tag-analyzer-63", message: "L16 is ready, look at it", notify_when_idle: true } }, { pid: 29904, name: "listings-bc" }, new Date("2026-10-05T21:40:05Z"))), '{"ts":"2026-10-05T21:40:05.000Z","type":"message","from":"listings-bc","to":"tag-analyzer-63","text":"L16 is ready, look at it","notify_on_idle":true}');
  assert.equal(hk.buildEvent({ hook_event_name: "PostToolUse", tool_name: "Bash", cwd: "/x" }, { pid: 1, name: null }), null); assert.equal(hk.buildEvent({ hook_event_name: "Stop", cwd: "/x" }, { pid: null, name: null }), null);
});
check("hook appendEvent", () => assert.equal(hk.appendEvent("/nonexistent-root/e.jsonl", { a: 1 }), false));
check("hook main cli", () => {
  const ef = `${T}/hook-test/events.jsonl`; rmSync(`${T}/hook-test`, { recursive: true, force: true });
  const env = { ...process.env, CC_DASHBOARD_EVENTS: ef };
  const o1 = execFileSync(process.execPath, [`${R}/webhook/hooks/dashboard-hook.js`], { input: J({ session_id: MINE.sessionId, hook_event_name: "Notification", cwd: MINE.cwd, message: "x", notification_type: "permission_prompt" }), env });
  const o2 = execFileSync(process.execPath, [`${R}/webhook/hooks/dashboard-hook.js`], { input: "garbage", env });
  assert.equal(o1.toString() + o2.toString(), ""); const lines = readFileSync(ef, "utf8").trim().split("\n"); assert.equal(lines.length, 1);
  const e = JSON.parse(lines[0]); assert.deepEqual([e.type, e.session, e.folder, e.pid, e.state, e.role], ["session", MINE.name, basename(MINE.cwd), ME, "waiting", null]);
});

check("hook registry by pid", () => { assert.equal(hk.readSessionRegistry("/nonexistent").length, 0); assert.equal(hk.lookupSessionRegistryByPid(1), null); assert.equal(hk.lookupSessionRegistryByPid(ME).name, MINE.name); });
check("server parseArgs port", () => assert.throws(() => sv.parseArgs(["--port"]), /--port needs a non-negative number/));

check("fake rename", () => { const f = JSON.parse(readFileSync(`${T}/fx.json`, "utf8")); const byPid = {}; for (const e of f.events) if (e.data.type === "session" && e.data.session) (byPid[e.data.pid] ??= new Set()).add(e.data.session); const renamed = Object.values(byPid).filter((names) => names.size > 1); assert.equal(renamed.length, 1); assert.ok(renamed[0].has(fk.RENAMED_NAME)); });

const dr = await import(`${R}/webhook/declare-role.js`);
check("declare parseRole", () => { assert.equal(dr.parseRole(["  manager "]), "manager"); assert.throws(() => dr.parseRole([]), /usage/); assert.throws(() => dr.parseRole(["bad/role!"]), /usage/); });
check("declare resolve", () => {
  assert.equal(J(dr.resolveCallingSession({ findPid: () => 1, lookup: () => ({ pid: 1, name: "x-1", cwd: "/a/b/listings", status: "idle" }) })), '{"pid":1,"name":"x-1","cwd":"/a/b/listings","folder":"listings","state":"idle"}');
  assert.equal(J(dr.resolveCallingSession({ findPid: () => 1, lookup: () => ({ pid: 1, name: null, cwd: null, status: "weird" }) })), '{"pid":1,"name":null,"cwd":null,"folder":"","state":"busy"}');
  assert.throws(() => dr.resolveCallingSession({ findPid: () => null }), /no claude process found above this one/);
  assert.throws(() => dr.resolveCallingSession({ findPid: () => 999999, lookup: () => null }), /no registry entry for claude pid 999999/);
});
check("declare buildRoleEvent", () => assert.equal(J(dr.buildRoleEvent({ pid: 29904, name: "listings-bc", folder: "listings", state: "idle" }, "validator", new Date("2026-10-05T21:40:00Z"))), '{"ts":"2026-10-05T21:40:00.000Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"idle","role":"validator"}'));
check("declare saveRole / hook readSavedRole", () => {
  const rp = `${T}/roles-example.json`; rmSync(rp, { force: true });
  assert.equal(dr.saveRole(rp, "/a/b", "manager"), true); assert.equal(dr.saveRole(rp, "/c", "validator"), true);
  assert.equal(readFileSync(rp, "utf8").trim().replace(/\s/g, ""), '{"/a/b":"manager","/c":"validator"}');
  assert.equal(dr.saveRole("/nonexistent-root/r.json", "/a", "x"), false); assert.equal(dr.saveRole(rp, "", "x"), false);
  assert.equal(hk.readSavedRole("/a/b", rp), "manager"); assert.equal(hk.readSavedRole("/zzz", rp), null); assert.equal(hk.readSavedRole("/a/b", "/nonexistent.json"), null);
  assert.equal(hk.buildEvent({ hook_event_name: "SessionStart", cwd: "/a/b" }, { pid: 7, name: "b-01", role: "manager" }, new Date("2026-10-05T21:40:00Z")).role, "manager");
});
check("declare cli", () => {
  const ef = `${T}/role/events.jsonl`; rmSync(`${T}/role`, { recursive: true, force: true }); const env = { ...process.env, CC_DASHBOARD_EVENTS: ef, CC_DASHBOARD_ROLES: `${T}/role/roles.json` };
  assert.equal(execFileSync(process.execPath, [`${R}/webhook/declare-role.js`, "webhook-builder"], { env }).toString(), "");
  const e = JSON.parse(readFileSync(ef, "utf8").trim()); assert.deepEqual([e.type, e.session, e.pid, e.role], ["session", MINE.name, ME, "webhook-builder"]); assert.ok(schema.validateEvent(e).ok);
  assert.equal(JSON.parse(readFileSync(`${T}/role/roles.json`, "utf8"))[MINE.cwd], "webhook-builder");
  let code = 0, err = ""; try { execFileSync(process.execPath, [`${R}/webhook/declare-role.js`], { env, stdio: ["ignore", "pipe", "pipe"] }); } catch (x) { code = x.status; err = x.stderr.toString(); }
  assert.equal(code, 1); assert.match(err, /^usage: declare-role.js <role>/); assert.equal(err.trim().split("\n").length, 1);
  code = 0; try { execFileSync(process.execPath, [`${R}/webhook/declare-role.js`, "manager"], { env: { ...env, CC_DASHBOARD_EVENTS: "/nonexistent-root/e.jsonl" }, stdio: ["ignore", "pipe", "pipe"] }); } catch (x) { code = x.status; err = x.stderr.toString(); }
  assert.equal(code, 1); assert.equal(err, "declare-role: cannot write /nonexistent-root/e.jsonl\n");
});
