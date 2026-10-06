import { test } from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";
import { homedir } from "node:os";
import { createRandom, parseArgs, createGenerator, runScenario, buildFixture, FOLDERS, GHOST_RECIPIENT, REAL_EVENTS_PATH } from "../../../webhook/fake.js";
import { validateEvent } from "../../../webhook/schema.js";

const instantOptions = (extra = []) => parseArgs(["--fixture", "/tmp/unused.json", "--start-time", "2026-10-05T21:40:00Z", ...extra]);
const recorded = async (options) => {
  const entries = [];
  const generator = createGenerator(options, { write: (entry) => entries.push(entry), noChildren: true });
  await runScenario(generator, options);
  return entries;
};

test("createRandom is deterministic per seed and stays in range", () => {
  const a = createRandom(42);
  const b = createRandom(42);
  assert.deepEqual([a.next(), a.int(1, 40), a.hex2(), a.pick(["x", "y", "z"])], [b.next(), b.int(1, 40), b.hex2(), b.pick(["x", "y", "z"])]);
  assert.equal(createRandom(42).int(1, 40), 25);
  const c = createRandom(7);
  for (let i = 0; i < 500; i += 1) {
    const value = c.next();
    assert.ok(value >= 0 && value < 1);
    const integer = c.int(3, 5);
    assert.ok(integer >= 3 && integer <= 5);
    assert.match(c.hex2(), /^[0-9a-f]{2}$/);
  }
  assert.notEqual(createRandom(1).next(), createRandom(2).next());
});

test("parseArgs builds options and forces instant mode for fixtures", () => {
  assert.deepEqual(parseArgs(["--fixture", "/tmp/f.json", "--sessions", "8"]), { out: null, fixture: "/tmp/f.json", speed: 1, sessions: 8, seed: 42, instant: true, durationSeconds: 60, snapshotUntilSeconds: 0, startTime: null });
  const live = parseArgs(["--out", "/tmp/e.jsonl", "--speed", "3", "--seed", "9", "--duration", "5", "--snapshot-until", "2", "--start-time", "2026-10-05T21:40:00Z"]);
  assert.deepEqual([live.instant, live.durationSeconds, live.speed, live.seed, live.snapshotUntilSeconds, live.startTime], [false, 5, 3, 9, 2, "2026-10-05T21:40:00Z"]);
  assert.equal(parseArgs(["--out", "/tmp/e.jsonl", "--instant"]).durationSeconds, 60);
});

test("parseArgs refuses bad combinations and the real events file", () => {
  assert.throws(() => parseArgs([]), /--out <path> or --fixture <path> is required/);
  assert.throws(() => parseArgs(["--out", "/a", "--fixture", "/b"]), /either --out or --fixture/);
  assert.throws(() => parseArgs(["--out", REAL_EVENTS_PATH]), /refusing to write to the real events file/);
  assert.throws(() => parseArgs(["--out", join(homedir(), ".claude", "dashboard", "..", "dashboard", "events.jsonl")]), /refusing/);
  assert.throws(() => parseArgs(["--out", "/a", "--speed", "0"]), /--speed must be a positive number/);
  assert.throws(() => parseArgs(["--out", "/a", "--speed", "x"]), /--speed must be a positive number/);
  assert.throws(() => parseArgs(["--fixture", "/a", "--start-time", "nope"]), /--start-time must be ISO 8601/);
  assert.throws(() => parseArgs(["--fixture", "/a", "--bogus"]), /unknown flag --bogus/);
});

test("createGenerator records validated events through the injected writer with a virtual clock", () => {
  const written = [];
  const generator = createGenerator({ instant: true, seed: 1 }, { write: (entry) => written.push(entry), now: () => new Date("2026-10-05T21:40:00Z") });
  const session = generator.startSession("listings");
  generator.advance(1000);
  generator.setState(session, "busy");
  generator.sendMessage(session, GHOST_RECIPIENT, true);
  assert.deepEqual(written.map((entry) => [entry.atMs, entry.event, entry.data.state ?? entry.data.to]), [[0, "session", "started"], [1000, "session", "busy"], [1000, "message", GHOST_RECIPIENT]]);
  assert.equal(written[0].data.ts, "2026-10-05T21:40:00.000Z");
  assert.equal(written[1].data.ts, "2026-10-05T21:40:01.000Z");
  assert.match(session.name, /^listings-[0-9a-f]{2}$/);
  assert.ok(session.pid > 70000);
  assert.throws(() => generator.emit({ type: "session" }), /invalid fake event/);
});

test("createGenerator handles anonymous sessions, naming, ending, silent death, and liveness entries", () => {
  const written = [];
  const generator = createGenerator({ instant: true, seed: 3 }, { write: (entry) => written.push(entry), now: () => new Date("2026-10-05T21:40:00Z") });
  const anonymous = generator.startSession("scratch", { anonymous: true });
  assert.equal(anonymous.name, null);
  assert.equal(generator.sendMessage(anonymous, generator.startSession("a"), false).from, null);
  generator.nameSession(anonymous);
  assert.match(anonymous.name, /^scratch-[0-9a-f]{2}$/);
  assert.equal(generator.live().length, 2);
  generator.endSession(anonymous);
  assert.equal(generator.live().length, 1);
  const dying = generator.live()[0];
  generator.killSilently(dying);
  assert.equal(generator.live().length, 0);
  const liveness = generator.emitLiveness(dying);
  assert.deepEqual([liveness.event, liveness.data.state, liveness.data.pid], ["liveness", "ended", dying.pid]);
  assert.equal(written.filter((entry) => entry.event === "liveness").length, 1);
  for (const entry of written) assert.equal(validateEvent(entry.data).ok, true);
});

test("runScenario with zero sessions records nothing and with the default seed matches the documented counts", async () => {
  assert.equal((await recorded(instantOptions(["--sessions", "0"]))).length, 0);
  const entries = await recorded(instantOptions());
  assert.equal(entries.length, 124);
  const kinds = entries.reduce((acc, entry) => ({ ...acc, [entry.event]: (acc[entry.event] ?? 0) + 1 }), {});
  assert.deepEqual(kinds, { session: 103, message: 19, liveness: 2 });
  const states = entries.filter((e) => e.data.type === "session").map((e) => e.data.state);
  assert.equal(states.filter((s) => s === "started").length, 17);
  assert.equal(states.filter((s) => s === "waiting").length, 1);
  assert.equal(states.filter((s) => s === "ended").length, 3);
  assert.equal(entries.filter((e) => e.data.notify_on_idle === true).length, 6);
  assert.equal(entries.filter((e) => e.data.type === "message" && e.data.from === null).length, 1);
  assert.equal(entries.filter((e) => e.data.type === "message" && e.data.to === GHOST_RECIPIENT).length, 1);
  assert.deepEqual(entries[0], { atMs: 3000, event: "session", data: { ts: "2026-10-05T21:40:03.000Z", type: "session", session: "listings-72", folder: "listings", pid: 70025, state: "started", role: null } });
  for (const entry of entries) assert.equal(validateEvent(entry.data).ok, true);
  assert.equal(FOLDERS.length, 15);
});

test("runScenario is byte-identical across runs with the same seed and start time", async () => {
  assert.deepEqual(await recorded(instantOptions(["--sessions", "5"])), await recorded(instantOptions(["--sessions", "5"])));
  assert.notDeepEqual(await recorded(instantOptions(["--sessions", "5"])), await recorded(instantOptions(["--sessions", "5", "--seed", "1"])));
});

test("buildFixture folds entries up to the cutoff into the snapshot and scales later delays by speed", () => {
  const entries = [
    { atMs: 3000, event: "session", data: { ts: "2026-10-05T21:40:03.000Z", type: "session", session: "a-01", folder: "a", pid: 1, state: "started", role: null } },
    { atMs: 5000, event: "session", data: { ts: "2026-10-05T21:40:05.000Z", type: "session", session: "a-01", folder: "a", pid: 1, state: "busy", role: null } },
    { atMs: 9000, event: "message", data: { ts: "2026-10-05T21:40:09.000Z", type: "message", from: "a-01", to: "b", text: "m", notify_on_idle: false } },
  ];
  const fixture = buildFixture(entries, 4);
  assert.deepEqual(fixture.snapshot.sessions.map((s) => s.state), ["started"]);
  assert.deepEqual(fixture.events.map((e) => [e.delayMs, e.event]), [[1000, "session"], [4000, "message"]]);
  assert.deepEqual(buildFixture(entries, 4, 4).events.map((e) => e.delayMs), [250, 1000]);
  assert.deepEqual(buildFixture(entries, 10), { snapshot: { sessions: [{ ...entries[1].data }], messages: [entries[2].data] }, events: [] });
  assert.deepEqual(buildFixture([]), { snapshot: { sessions: [], messages: [] }, events: [] });
});
