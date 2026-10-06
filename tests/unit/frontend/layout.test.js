import { test } from "node:test";
import assert from "node:assert/strict";
import { ringPositions, labelSide, labelPlacement, messageCurve, truncateLabel } from "../../../frontend/layout.js";

const ring = { cx: 500, cy: 500, radius: 360 };
const near = (actual, expected, tolerance = 0.01) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} vs ${expected}`);

test("ringPositions spaces sessions evenly from the top clockwise, grouped by folder then label", () => {
  const sessions = [
    { pid: 30444, session: "scratch-7a", folder: "scratch" },
    { pid: 30333, session: "path-finder-e5", folder: "path_finder" },
    { pid: 29904, session: "listings-bc", folder: "listings" },
    { pid: 30222, session: "path-finder-18", folder: "path_finder" },
  ];
  const positions = ringPositions(sessions, ring);
  assert.deepEqual([...positions.entries()].map(([pid, p]) => [pid, Math.round(p.x), Math.round(p.y)]), [[29904, 500, 140], [30222, 860, 500], [30333, 500, 860], [30444, 140, 500]]);
  near(positions.get(29904).angle, -Math.PI / 2);
  assert.deepEqual(sessions.map((s) => s.pid), [30444, 30333, 29904, 30222]);
});

test("ringPositions handles zero and one session and unnamed sessions sort by pid", () => {
  assert.equal(ringPositions([], ring).size, 0);
  const single = ringPositions([{ pid: 1, session: "a-1", folder: "a" }], ring).get(1);
  assert.deepEqual([Math.round(single.x), Math.round(single.y)], [500, 140]);
  const order = [...ringPositions([{ pid: 20, session: null, folder: "a" }, { pid: 3, session: null, folder: "a" }], ring).keys()];
  assert.deepEqual(order, [20, 3]);
});

test("ringPositions keeps every body on the ring for 1 to 15 sessions with no shared positions", () => {
  for (let count = 1; count <= 15; count += 1) {
    const sessions = Array.from({ length: count }, (_, i) => ({ pid: i, session: `s-${String(i).padStart(2, "0")}`, folder: `f${i % 4}` }));
    const positions = ringPositions(sessions, ring);
    assert.equal(positions.size, count);
    const seen = new Set();
    for (const p of positions.values()) {
      near(Math.hypot(p.x - 500, p.y - 500), 360, 1e-6);
      const key = `${p.x.toFixed(3)},${p.y.toFixed(3)}`;
      assert.ok(!seen.has(key));
      seen.add(key);
    }
  }
});

test("ringPositions is independent of arrival order", () => {
  const a = [{ pid: 1, session: "x-1", folder: "x" }, { pid: 2, session: "y-1", folder: "y" }];
  const b = [a[1], a[0]];
  assert.deepEqual([...ringPositions(a, ring)], [...ringPositions(b, ring)]);
});

test("labelSide picks top, bottom, right, or left by angle", () => {
  assert.equal(labelSide(-Math.PI / 2), "top");
  assert.equal(labelSide(Math.PI / 2), "bottom");
  assert.equal(labelSide(0), "right");
  assert.equal(labelSide(Math.PI), "left");
  assert.equal(labelSide(-Math.PI / 2 + 0.19), "top");
  assert.equal(labelSide(-Math.PI / 2 + 0.21), "right");
  assert.equal(labelSide(Math.PI / 2 + 0.21), "left");
});

test("labelPlacement puts text outward and stacks a second line only with a role", () => {
  const options = { bodyRadius: 18, lineHeight: 22 };
  const check = (actual, expected) => {
    assert.equal(actual.anchor, expected.anchor);
    for (const key of ["x", "nameY", "roleY"]) near(actual[key], expected[key]);
  };
  check(labelPlacement(0, { ...options, hasRole: false }), { anchor: "start", x: 32, nameY: 7.7, roleY: 7.7 });
  check(labelPlacement(0, { ...options, hasRole: true }), { anchor: "start", x: 32, nameY: -3.3, roleY: 18.7 });
  check(labelPlacement(Math.PI, { ...options, hasRole: true }), { anchor: "end", x: -32, nameY: -3.3, roleY: 18.7 });
  check(labelPlacement(-Math.PI / 2, { ...options, hasRole: true }), { anchor: "middle", x: 0, nameY: -58, roleY: -36 });
  check(labelPlacement(-Math.PI / 2, { ...options, hasRole: false }), { anchor: "middle", x: 0, nameY: -36, roleY: -36 });
  check(labelPlacement(Math.PI / 2, { ...options, hasRole: false }), { anchor: "middle", x: 0, nameY: 54, roleY: 76 });
});

test("labels never overlap for 1 to 15 bodies with the longest names and roles", () => {
  const maxWidth = 24 * 22 * 0.55;
  for (let count = 1; count <= 15; count += 1) {
    const sessions = Array.from({ length: count }, (_, i) => ({ pid: i, session: "x".repeat(24), folder: `f${String(i).padStart(2, "0")}` }));
    const boxes = [...ringPositions(sessions, { cx: 680, cy: 500, radius: 340 }).values()].map((p) => {
      const placement = labelPlacement(p.angle, { bodyRadius: 18, lineHeight: 22, hasRole: true });
      const x0 = placement.anchor === "start" ? p.x + placement.x : placement.anchor === "end" ? p.x + placement.x - maxWidth : p.x - maxWidth / 2;
      return { x0, x1: x0 + maxWidth, y0: p.y + placement.nameY - 22, y1: p.y + placement.roleY };
    });
    for (let i = 0; i < boxes.length; i += 1) {
      for (let j = i + 1; j < boxes.length; j += 1) {
        const a = boxes[i];
        const b = boxes[j];
        assert.ok(!(a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1), `overlap at ${count} bodies`);
      }
      assert.ok(boxes[i].x0 >= 0 && boxes[i].x1 <= 1360, `label outside the 1360 viewBox at ${count} bodies`);
    }
  }
});

test("messageCurve bows toward the center with a side offset, mirrors on reversal, and reports length", () => {
  const curve = messageCurve({ x: 680, y: 160 }, { x: 1020, y: 500 }, { x: 680, y: 500 });
  assert.equal(curve.d, "M 680 160 Q 728.2 451.8 1020 500");
  assert.equal(Math.round(curve.length), 519);
  near(curve.control.x, 728.2157, 0.001);
  near(curve.control.y, 451.7843, 0.001);
  const reverse = messageCurve({ x: 1020, y: 500 }, { x: 680, y: 160 }, { x: 680, y: 500 });
  near(reverse.control.x, 784.7843, 0.001);
  near(reverse.control.y, 395.2157, 0.001);
  const straight = messageCurve({ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 50, y: 0 }, { bow: 0, sideOffset: 0 });
  assert.deepEqual(straight.control, { x: 50, y: 0 });
  near(straight.length, 100, 1e-9);
  const degenerate = messageCurve({ x: 1, y: 1 }, { x: 1, y: 1 }, { x: 680, y: 500 });
  assert.ok(degenerate.d.startsWith("M 1 1 Q"));
  assert.ok(Number.isFinite(degenerate.length));
});

test("truncateLabel cuts to maxChars with an ellipsis and leaves short labels alone", () => {
  assert.equal(truncateLabel("add-semantic-similarity-scores-4a", 24), "add-semantic-similarity…");
  assert.equal(truncateLabel("listings-bc", 24), "listings-bc");
  assert.equal(truncateLabel("abcdefghij", 5), "abcd…");
  assert.equal(truncateLabel("ab", 1), "a…");
  assert.equal(truncateLabel("", 5), "");
  assert.equal(truncateLabel("abcde", 5), "abcde");
});
