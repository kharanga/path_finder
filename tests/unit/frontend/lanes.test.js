import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { boardLayout, tracePath, traceCorridors, assignLanes, laneOptions, laneOffset, laneSlot, traceKey, LANE } from "../../../frontend/layout.js";
import { createState, applySnapshot, applyEvent, liveSessions, sessionByName } from "../../../frontend/state.js";
import { routesSharingSegments, segmentCrossesBox } from "../../helpers/geometry.js";

const fixture = (name) => JSON.parse(readFileSync(new URL(`../../../frontend/fixtures/${name}.json`, import.meta.url), "utf8"));
const loaded = (name, replay = true) => {
  const fx = fixture(name);
  const state = createState();
  applySnapshot(state, fx.snapshot, 0);
  if (replay) for (const step of fx.events) applyEvent(state, step.event, step.data, 0);
  return state;
};
const pairsFromMessages = (state, boxes) => {
  const keys = [];
  const ends = new Map();
  for (const message of state.messages) {
    const from = sessionByName(state, message.from);
    const to = sessionByName(state, message.to);
    if (!from || !to || from.pid === to.pid || !boxes.has(from.pid) || !boxes.has(to.pid)) continue;
    const key = traceKey(from.pid, to.pid);
    if (ends.has(key)) continue;
    keys.push(key);
    ends.set(key, [boxes.get(from.pid), boxes.get(to.pid)]);
  }
  return { keys, ends };
};
const routed = (state, { portrait = false, limit = Infinity } = {}) => {
  const boxes = boardLayout(liveSessions(state), { portrait }).capsules;
  const byString = new Map([...boxes.values()].map((box) => [String(box.pid), box]));
  const { keys, ends } = pairsFromMessages(state, boxes);
  const used = keys.slice(0, limit);
  const assignment = assignLanes(used, { columnOf: (pid) => byString.get(pid)?.index ?? pid, corridorsOf: (key) => traceCorridors(...ends.get(key)) });
  const routes = new Map(used.map((key) => [key, tracePath(...ends.get(key), laneOptions(assignment, key, ...ends.get(key)))]));
  return { routes, assignment, boxes: [...boxes.values()], keys: used, ends };
};
const crossings = (routes, boxes) => {
  let count = 0;
  for (const [key, route] of routes) {
    const endpoints = key.split("|");
    for (let i = 1; i < route.points.length; i += 1) {
      for (const box of boxes) {
        if (endpoints.includes(String(box.pid))) continue;
        if (segmentCrossesBox(route.points[i - 1], route.points[i], box)) count += 1;
      }
    }
  }
  return count;
};
const shared = (routes) => routesSharingSegments(new Map([...routes].map(([key, route]) => [key, route.points])));

test("LANE constants and laneOffset alternate sides from the center", () => {
  assert.deepEqual(LANE, { gap: 6, pinGap: 20 });
  assert.deepEqual([0, 1, 2, 3, 4, 5].map((i) => laneOffset(i)), [0, 6, -6, 12, -12, 18]);
  assert.deepEqual([1, 2].map((i) => laneOffset(i, 10)), [10, -10]);
  assert.equal(laneOffset(-1), 0);
});

test("laneSlot alternates outward at the gap, then interleaves at half and quarter steps, so earlier slots never depend on later lanes", () => {
  assert.deepEqual(Array.from({ length: 13 }, (_, i) => laneSlot(i, 6, 32)), [0, 6, -6, 12, -12, 18, -18, 24, -24, 30, -30, 1.5, -1.5]);
  assert.deepEqual(Array.from({ length: 12 }, (_, i) => laneSlot(i, 20, 100)), [0, 20, -20, 40, -40, 60, -60, 80, -80, 5, -5, 15]);
  assert.deepEqual(Array.from({ length: 5 }, (_, i) => laneSlot(i, 6, 12.2)), [0, 6, -6, 1.5, -1.5]);
  assert.equal(new Set(Array.from({ length: 21 }, (_, i) => laneSlot(i, 20, 100))).size, 21);
  for (let count = 1; count <= 21; count += 1) {
    const slots = Array.from({ length: count }, (_, i) => laneSlot(i, 20, 100));
    assert.deepEqual(slots.slice(0, count - 1), Array.from({ length: count - 1 }, (_, i) => laneSlot(i, 20, 100)), `prefix stable at ${count}`);
    assert.ok(slots.every((v) => Math.abs(v) <= 98));
  }
  assert.equal(laneSlot(0, 6, 0), 0);
  assert.equal(laneSlot(7, 6, 0), 0);
});

test("traceCorridors names the gap for same and adjacent lines and gap, column, gap for far routes", () => {
  const layout = boardLayout(liveSessions(loaded("few", false)));
  const [a, b, c, d] = [30222, 30333, 29904, 30111].map((pid) => layout.capsules.get(pid));
  assert.deepEqual(traceCorridors(a, b), ["gap:1"]);
  assert.deepEqual(traceCorridors(c, a), ["gap:0"]);
  assert.deepEqual(traceCorridors(c, d), ["gap:0", "col:1", "gap:2"]);
  assert.deepEqual(traceCorridors(d, c), ["gap:2", "col:1", "gap:0"]);
  assert.throws(() => traceCorridors(null, a), TypeError);
});

test("assignLanes numbers pairs in order, counts lanes per corridor and pins per column, and ignores duplicates", () => {
  const first = assignLanes(["1|2", "1|3", "2|3", "1|2"]);
  assert.deepEqual([...first.lanes], [["1|2", 0], ["1|3", 1], ["2|3", 2]]);
  assert.deepEqual(first.pins.get("1|3"), { 1: 1, 3: 0 });
  assert.deepEqual(first.pins.get("2|3"), { 2: 1, 3: 1 });
  assert.deepEqual(assignLanes(["1|2", "3|4"], { columnOf: () => "c" }).pins.get("3|4"), { 3: 2, 4: 3 });
  const corridors = assignLanes(["1|2", "1|3", "2|3"], { corridorsOf: (key) => (key === "2|3" ? ["gap:1"] : ["gap:0"]) });
  assert.deepEqual([...corridors.corridorLanes], [["1|2", { "gap:0": 0 }], ["1|3", { "gap:0": 1 }], ["2|3", { "gap:1": 0 }]]);
  assert.deepEqual([...corridors.perCorridor], [["gap:0", 2], ["gap:1", 1]]);
  assert.deepEqual(assignLanes([]).lanes.size, 0);
});

test("assignLanes is deterministic and never changes earlier assignments when pairs are added", () => {
  const keys = ["1|2", "1|3", "2|3", "1|4", "3|4", "2|4"];
  const a = assignLanes(keys, { corridorsOf: () => ["gap:0"] });
  const b = assignLanes(keys, { corridorsOf: () => ["gap:0"] });
  assert.deepEqual([...a.lanes], [...b.lanes]);
  assert.deepEqual([...a.pins], [...b.pins]);
  for (let n = 1; n < keys.length; n += 1) {
    const prefix = assignLanes(keys.slice(0, n), { corridorsOf: () => ["gap:0"] });
    for (const key of keys.slice(0, n)) {
      assert.equal(prefix.lanes.get(key), a.lanes.get(key));
      assert.deepEqual(prefix.pins.get(key), a.pins.get(key));
      assert.deepEqual(prefix.corridorLanes.get(key), a.corridorLanes.get(key));
    }
  }
});

test("a fan-in of three into one capsule yields three separate routes into distinct pins with no shared segments", () => {
  const state = loaded("fanin");
  for (const portrait of [false, true]) {
    const { routes, assignment, boxes, keys } = routed(state, { portrait });
    const destination = String(sessionByName(state, "path-finder-0d").pid);
    const intoDestination = keys.filter((key) => key.split("|").includes(destination));
    assert.equal(intoDestination.length, 4);
    const pins = intoDestination.map((key) => assignment.pins.get(key)[destination]);
    assert.equal(new Set(pins).size, pins.length);
    const endX = intoDestination.map((key) => { const points = routes.get(key).points; const end = key.endsWith(`|${destination}`) || key.startsWith(`${destination}|`) ? points : points; return end.at(-1).x; });
    assert.equal(new Set(endX).size, endX.length);
    assert.deepEqual(shared(routes), []);
    assert.equal(crossings(routes, boxes), 0);
  }
});

test("every fixture's message pairs route with no shared segments and no capsule crossings in both orientations", () => {
  for (const name of ["few", "messages", "rename", "removed", "many", "fanin", "generated-many", "generated-mid", "generated-fast"]) {
    const state = loaded(name);
    for (const portrait of [false, true]) {
      const { routes, boxes } = routed(state, { portrait });
      assert.deepEqual(shared(routes), [], `${name} ${portrait ? "portrait" : "landscape"}`);
      assert.equal(crossings(routes, boxes), 0, `${name} ${portrait ? "portrait" : "landscape"}`);
    }
  }
});

test("routes are deterministic and adding a pair on the fan-in board leaves the earlier paths byte-identical", () => {
  const state = loaded("fanin");
  const full = routed(state);
  const again = routed(state);
  for (const key of full.keys) assert.equal(again.routes.get(key).d, full.routes.get(key).d);
  for (let n = 1; n < full.keys.length; n += 1) {
    const prefix = routed(state, { limit: n });
    for (const key of prefix.keys) assert.equal(prefix.routes.get(key).d, full.routes.get(key).d, `pair ${key} moved after ${full.keys.length - n} more pairs`);
  }
});

test("adding pairs on the 15-session generator board leaves every earlier path byte-identical in both orientations", () => {
  for (const name of ["generated-many", "generated-mid", "generated-fast", "messages", "rename"]) {
    const state = loaded(name);
    for (const portrait of [false, true]) {
      const full = routed(state, { portrait });
      for (let n = 1; n < full.keys.length; n += 1) {
        const prefix = routed(state, { portrait, limit: n });
        for (const key of prefix.keys) assert.equal(prefix.routes.get(key).d, full.routes.get(key).d, `${name} ${portrait ? "portrait" : "landscape"}: pair ${key} moved after ${full.keys.length - n} more pairs`);
      }
    }
  }
});

test("laneOptions shifts every corridor a route uses and both pins, and tracePath applies them", () => {
  const layout = boardLayout(liveSessions(loaded("few", false)));
  const [a, b, c, d] = [30222, 30333, 29904, 30111].map((pid) => layout.capsules.get(pid));
  const assignment = assignLanes(["29904|30111", "30222|30333", "29904|30222"], { columnOf: (pid) => layout.capsules.get(Number(pid)).index, corridorsOf: (key) => { const [p, q] = key.split("|").map(Number); return traceCorridors(layout.capsules.get(p), layout.capsules.get(q)); } });
  const options = laneOptions(assignment, "29904|30111", c, d);
  assert.deepEqual(Object.keys(options.shifts).sort(), ["col:1", "gap:0", "gap:2"]);
  assert.equal(options.fromPinShift, 0);
  assert.equal(options.toPinShift, 20);
  const second = laneOptions(assignment, "29904|30222", c, a);
  assert.equal(second.shifts["gap:0"], 6);
  assert.equal(second.fromPinShift, 40);
  assert.equal(second.toPinShift, -40);
  assert.deepEqual(assignment.pins.get("29904|30222"), { 29904: 3, 30222: 4 });
  const shifted = tracePath(a, b, { laneShift: 6, fromPinShift: 20, toPinShift: -20 }).points;
  assert.deepEqual(shifted, [{ x: 360, y: 468 }, { x: 360, y: 506 }, { x: 576, y: 506 }, { x: 576, y: 468 }]);
  assert.deepEqual(tracePath(c, d, { shifts: { "gap:0": 6, "col:1": -6, "gap:2": 12 } }).points, [{ x: 340, y: 348 }, { x: 340, y: 386 }, { x: 462, y: 386 }, { x: 462, y: 632 }, { x: 340, y: 632 }, { x: 340, y: 652 }]);
});
