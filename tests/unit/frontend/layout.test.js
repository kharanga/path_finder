import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { boardLayout, boardFor, tracePath, traceKey, edgeBox, truncateLabel, BOARD, BOARD_PORTRAIT, CAPSULE } from "../../../frontend/layout.js";
import { boxesOverlap as overlaps, segmentCrossesBox } from "../../helpers/geometry.js";
import { createState, applySnapshot, applyEvent, liveSessions } from "../../../frontend/state.js";

const fixture = (name) => JSON.parse(readFileSync(new URL(`../../../frontend/fixtures/${name}.json`, import.meta.url), "utf8"));
const liveFrom = (name, replay = false) => {
  const fx = fixture(name);
  const state = createState();
  applySnapshot(state, fx.snapshot, 0);
  if (replay) for (const step of fx.events) applyEvent(state, step.event, step.data, 0);
  return liveSessions(state);
};
const session = (pid, folder, index = pid) => ({ pid, session: `${folder}-${String(index).padStart(2, "0")}`, folder, state: "idle", firstSeen: `2026-10-06T00:00:${String(index).padStart(2, "0")}Z` });
const insideBoard = (box) => box.x >= 0 && box.y >= 0 && box.x + box.width <= BOARD.width && box.y + box.height <= BOARD.height;

test("BOARD and CAPSULE constants carry the documented geometry", () => {
  for (const [key, value] of Object.entries({ width: 1360, height: 1000, marginX: 60, marginTop: 70, marginBottom: 70, labelWidth: 170 })) assert.equal(BOARD[key], value, key);
  for (const [key, value] of Object.entries({ width: 220, height: 56, gapX: 36, rowGap: 64, cornerRadius: 14 })) assert.equal(CAPSULE[key], value, key);
});

test("boardLayout on few.json matches the documented rows, lines, and capsule box", () => {
  const layout = boardLayout(liveFrom("few"));
  assert.equal(layout.capsules.size, 5);
  assert.deepEqual(layout.rows.map((r) => r.folder), ["listings", "path_finder", "scratch", "tag-analyzer"]);
  assert.equal(layout.lineCount, 4);
  assert.equal(layout.perLine, 4);
  const a = layout.capsules.get(30222);
  assert.deepEqual([a.x, a.y, a.cx, a.cy, a.line, a.index], [230, 412, 340, 440, 1, 0]);
  assert.equal(layout.capsules.get(30333).index, 1);
  assert.equal(layout.capsules.get(30333).line, 1);
  assert.deepEqual([a.width, a.height], [CAPSULE.width, CAPSULE.height]);
  assert.equal(layout.rows[1].cy, a.cy);
  assert.equal(layout.rows[1].x, BOARD.marginX);
});

test("boardLayout with no sessions gives nothing", () => {
  assert.deepEqual([boardLayout([]).capsules.size, boardLayout([]).rows.length, boardLayout([]).lineCount], [0, 0, 0]);
});

test("boardLayout groups folders with _ and - as one row, sorts rows, and orders a row by firstSeen then label", () => {
  const sessions = [
    { pid: 3, session: "zed-03", folder: "zed", firstSeen: "2026-10-06T00:00:03Z" },
    { pid: 2, session: "path-finder-02", folder: "path_finder", firstSeen: "2026-10-06T00:00:09Z" },
    { pid: 1, session: "path-finder-01", folder: "path-finder", firstSeen: "2026-10-06T00:00:05Z" },
    { pid: "placeholder:path-finder-zz", session: "path-finder-zz", folder: "path-finder", firstSeen: null },
    { pid: 4, session: "alpha-04", folder: "alpha", firstSeen: "2026-10-06T00:00:01Z" },
  ];
  const layout = boardLayout(sessions);
  assert.deepEqual(layout.rows.map((r) => r.folder), ["alpha", "path_finder", "zed"]);
  assert.equal(layout.lineCount, 3);
  const line1 = [1, 2, "placeholder:path-finder-zz"].map((pid) => layout.capsules.get(pid));
  assert.deepEqual(line1.map((b) => b.line), [1, 1, 1]);
  assert.deepEqual(line1.map((b) => b.index), [0, 1, 2]);
});

test("boardLayout keeps a capsule's slot when newer sessions join and wraps at perLine", () => {
  const first = boardLayout([session(1, "listings"), session(2, "listings"), session(3, "listings")]).capsules.get(2);
  const later = boardLayout([session(9, "listings"), session(1, "listings"), session(2, "listings"), session(3, "listings")]).capsules.get(2);
  assert.deepEqual([first.index, first.x, first.line], [later.index, later.x, later.line]);
  const six = boardLayout(Array.from({ length: 6 }, (_, i) => session(i + 1, "listings")));
  assert.equal(six.perLine, 4);
  assert.equal(six.lineCount, 2);
  assert.equal(six.rows.length, 1);
  assert.deepEqual([six.capsules.get(4).line, six.capsules.get(5).line, six.capsules.get(5).index], [0, 1, 0]);
  assert.equal(boardLayout([session(1, "a")], { width: 500 }).perLine, 1);
});

test("boardLayout compresses line pitch to fit many lines and keeps every box inside the board", () => {
  const many = boardLayout(Array.from({ length: 12 }, (_, i) => session(i + 1, `f${String(i).padStart(2, "0")}`)));
  assert.equal(many.lineCount, 12);
  const pitch = many.capsules.get(1).pitch;
  assert.ok(pitch < CAPSULE.height + CAPSULE.rowGap);
  assert.ok(pitch > CAPSULE.height);
  for (const box of many.capsules.values()) assert.ok(insideBoard(box));
  const one = boardLayout([session(1, "a")]);
  assert.equal(one.capsules.get(1).pitch, CAPSULE.height + CAPSULE.rowGap);
});

test("capsules never overlap and traces never cross a capsule for 1, 5, 15 sessions and the generator fixtures", () => {
  for (const [name, replay] of [["one", false], ["few", false], ["many", false], ["generated-many", true], ["generated-mid", true]]) {
    const boxes = [...boardLayout(liveFrom(name, replay)).capsules.values()];
    for (let i = 0; i < boxes.length; i += 1) {
      assert.ok(insideBoard(boxes[i]), `${name}: box outside board`);
      for (let j = i + 1; j < boxes.length; j += 1) assert.ok(!overlaps(boxes[i], boxes[j]), `${name}: capsules overlap`);
    }
    for (const from of boxes) {
      for (const to of boxes) {
        if (from === to) continue;
        const { points } = tracePath(from, to);
        for (let k = 1; k < points.length; k += 1) {
          for (const other of boxes) {
            if (other === from || other === to) continue;
            assert.ok(!segmentCrossesBox(points[k - 1], points[k], other), `${name}: trace ${from.pid}->${to.pid} crosses ${other.pid}`);
          }
        }
      }
    }
  }
});

test("tracePath routes on the same line through a channel below, with the documented path and length", () => {
  const layout = boardLayout(liveFrom("few"));
  const a = layout.capsules.get(30222);
  const b = layout.capsules.get(30333);
  const route = tracePath(a, b);
  assert.equal(route.d, "M 340 468 L 340 488 Q 340 500 352 500 L 584 500 Q 596 500 596 488 L 596 468");
  assert.deepEqual(route.points, [{ x: 340, y: 468 }, { x: 340, y: 500 }, { x: 596, y: 500 }, { x: 596, y: 468 }]);
  assert.equal(Math.round(route.length), 310);
  assert.equal(tracePath(b, a).points[0].x, 596);
});

test("tracePath goes straight between vertically aligned adjacent lines and uses the bus for lines further apart", () => {
  const layout = boardLayout(liveFrom("few"));
  const a = layout.capsules.get(30222);
  const c = layout.capsules.get(29904);
  const d = layout.capsules.get(30111);
  assert.equal(tracePath(c, a).d, "M 340 348 L 340 412");
  assert.equal(Math.round(tracePath(c, a).length), 64);
  const far = tracePath(c, d);
  assert.equal(far.points.length, 6);
  assert.equal(far.points[2].x, 468);
  assert.equal(far.points[1].x, c.cx);
  assert.equal(far.points.at(-1).y, d.y);
  assert.ok(far.points.every((p, i, all) => i === 0 || p.x === all[i - 1].x || p.y === all[i - 1].y), "every segment is horizontal or vertical");
});

test("tracePath to an adjacent line with a horizontal offset uses the midway channel", () => {
  const from = { x: 230, y: 100, width: 220, height: 56, cx: 340, cy: 128, line: 0, index: 0, pitch: 120 };
  const to = { x: 486, y: 220, width: 220, height: 56, cx: 596, cy: 248, line: 1, index: 1, pitch: 120 };
  const route = tracePath(from, to);
  assert.deepEqual(route.points, [{ x: 340, y: 156 }, { x: 340, y: 188 }, { x: 596, y: 188 }, { x: 596, y: 220 }]);
  assert.ok(route.d.includes(" Q "));
  assert.equal(tracePath(from, to, { cornerRadius: 0 }).d.includes(" Q "), true);
  assert.throws(() => tracePath(null, to), TypeError);
});

test("traceKey is order independent and edgeBox sits at the row edge", () => {
  assert.equal(traceKey(30333, 30222), "30222|30333");
  assert.equal(traceKey(30222, 30333), "30222|30333");
  assert.equal(traceKey("placeholder:x", 5), "5|placeholder:x");
  const a = boardLayout(liveFrom("few")).capsules.get(30222);
  const edge = edgeBox(a);
  assert.deepEqual([edge.cx, edge.x, edge.width, edge.line, edge.index, edge.pid], [194, 194, 0, 1, -1, null]);
  assert.deepEqual([edge.y, edge.cy, edge.height, edge.folder], [a.y, a.cy, a.height, a.folder]);
  assert.throws(() => edgeBox(undefined), TypeError);
});

test("truncateLabel cuts at maxChars with an ellipsis", () => {
  assert.equal(truncateLabel("add-semantic-similarity-scores-4a", 21), "add-semantic-similar…");
  assert.equal(truncateLabel("listings-bc", 21), "listings-bc");
  assert.equal(truncateLabel("abcdefghij", 5), "abcd…");
  assert.equal(truncateLabel("ab", 1), "a…");
  assert.equal(truncateLabel("", 5), "");
});

test("boardFor picks the portrait constants and portrait layouts put two per line with labels above rows", () => {
  assert.equal(boardFor(false), BOARD);
  assert.equal(boardFor(true), BOARD_PORTRAIT);
  assert.deepEqual([BOARD_PORTRAIT.width, BOARD_PORTRAIT.height, BOARD_PORTRAIT.labelWidth, BOARD_PORTRAIT.labelAbove], [760, 1100, 0, 30]);
  const layout = boardLayout(liveFrom("many"), { portrait: true });
  assert.equal(layout.perLine, 2);
  assert.equal(layout.board.portrait, true);
  assert.equal(layout.rows.length, 8);
  assert.ok(layout.lineCount >= 10);
  for (const row of layout.rows) {
    const first = [...layout.capsules.values()].find((box) => box.folder === row.folder && box.index === 0);
    assert.ok(row.labelY < first.y, "label sits above the row");
    assert.equal(row.labelX, first.x);
  }
  const landscape = boardLayout(liveFrom("many"));
  assert.ok(landscape.rows.every((row) => row.labelX < BOARD.marginX + BOARD.labelWidth));
});

test("portrait capsules never overlap, stay inside the portrait board, and traces never cross a capsule", () => {
  for (const [name, replay] of [["few", false], ["many", false], ["generated-many", true]]) {
    const layout = boardLayout(liveFrom(name, replay), { portrait: true });
    const boxes = [...layout.capsules.values()];
    for (let i = 0; i < boxes.length; i += 1) {
      const box = boxes[i];
      assert.ok(box.x >= 0 && box.y >= 0 && box.x + box.width <= BOARD_PORTRAIT.width && box.y + box.height <= BOARD_PORTRAIT.height, `${name}: outside portrait board`);
      for (let j = i + 1; j < boxes.length; j += 1) assert.ok(!overlaps(box, boxes[j]), `${name}: overlap`);
    }
    for (const from of boxes) {
      for (const to of boxes) {
        if (from === to) continue;
        const { points } = tracePath(from, to);
        for (let k = 1; k < points.length; k += 1) {
          for (const other of boxes) {
            if (other === from || other === to) continue;
            assert.ok(!segmentCrossesBox(points[k - 1], points[k], other), `${name}: portrait trace ${from.pid}->${to.pid} crosses ${other.pid}`);
          }
        }
      }
    }
    assert.equal(edgeBox(boxes[0]).cx, boxes[0].columnOrigin - CAPSULE.gapX);
  }
});

