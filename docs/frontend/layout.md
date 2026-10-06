# layout.js

Pure geometry for the Circuit board. No DOM, runs in Node. Exports four constant objects and eleven functions.

Constants: `BOARD = { width: 1360, height: 1000, marginX: 60, marginTop: 70, marginBottom: 70, labelWidth: 170, labelAbove: 0 }` (landscape: the viewBox and the space reserved on the left for folder labels), `BOARD_PORTRAIT = { width: 760, height: 1100, marginX: 60, marginTop: 60, marginBottom: 60, labelWidth: 0, labelAbove: 30 }` (phone: labels above each row), `CAPSULE = { width: 220, height: 56, gapX: 36, rowGap: 64, cornerRadius: 14 }`, and `LANE = { gap: 6, pinGap: 20 }` (standard distance between parallel lanes in a corridor, and between pins on a capsule edge; later lanes interleave at half steps when a corridor is crowded, see `laneSlot`).

A capsule box is `{ pid, folder, x, y, width, height, cx, cy, line, index, pitch, columnOrigin }`: top-left corner, size, center, which line of the board it sits on (0 at the top), its position in that line, the vertical distance between lines in this layout (used to keep trace channels inside the gaps), and the x where column 0 starts (used to find column gaps and the row edge).

## boardFor(portrait)

What it does: picks the board constants for an orientation.

Inputs: `portrait` (boolean).

Output: `BOARD_PORTRAIT` when true, `BOARD` otherwise.

Errors: none.

Example:

```js
boardFor(false).width // 1360
boardFor(true).width  // 760
```

## boardLayout(sessions, { portrait, width, height })

What it does: groups sessions into one row per folder (folders compared with `_` and `-` equal, sorted alphabetically), orders each row by `firstSeen` then name so a capsule keeps its slot while live and newcomers append at the end (placeholders, which have no `firstSeen`, go last), wraps a row onto further lines when it has more capsules than fit (`perLine = floor((width - 2·marginX - labelWidth + gapX) / (capsule width + gapX))`: 4 in landscape, 2 in portrait), spaces the lines evenly (pitch at most capsule height plus `labelAbove` plus `rowGap`, compressed when many lines must fit) and centers the stack vertically. In portrait the folder label goes above the first capsule of its row instead of to the left.

Inputs:
- `sessions` (Session[]): usually `liveSessions(state)`. Not mutated.
- `portrait` (boolean, optional, default false): selects `BOARD_PORTRAIT`.
- `width`, `height` (number, optional): override the board size in user units.

Output: `{ capsules: Map<pid, box>, rows: [{ folder, label, x, y, cy, labelX, labelY, anchor }], lineCount, perLine, board: { width, height, portrait } }`. `rows` has one entry per folder at its first line; `labelX`/`labelY` is where the label text is anchored (`anchor` is an SVG `text-anchor` value).

Errors: none. An empty array yields an empty map, no rows, `lineCount` 0.

Example, with the `frontend/fixtures/few.json` snapshot:

```js
const layout = boardLayout(liveSessions(state));
layout.capsules.size                       // 5
layout.rows.map(r => r.folder)             // ["listings", "path_finder", "scratch", "tag-analyzer"]
layout.lineCount                           // 4
layout.perLine                             // 4
const a = layout.capsules.get(30222);      // path-finder-18, first in the path_finder row
[a.x, a.y, a.cx, a.cy, a.line, a.index]    // [230, 412, 340, 440, 1, 0]
layout.capsules.get(30333).index           // 1, path-finder-e5 sits to its right
boardLayout([]).capsules.size              // 0
```

With `many.json` (15 sessions, 8 folders): 8 lines, every folder on one line; `add-semantic-similarity-scores` is the first row, its label at `labelX` 60, `labelY` 98 (vertically centered on the capsule). In portrait: `perLine` 2, `lineCount` 10, `board` `{ width: 760, height: 1100, portrait: true }`, every capsule inside the board (right edge at most 536, bottom at most 1040), and the first row's label at `labelX` 60, `labelY` 80, ten units above its capsule at `y` 90.

## tracePath(from, to, { cornerRadius, shifts, laneShift, fromPinShift, toPinShift })

What it does: routes an orthogonal trace between two boxes so that it never crosses another capsule, along the trace's own lanes. Every horizontal run lies in the gap between two lines, at the gap's center plus that corridor's shift (`shifts[corridorId]`, falling back to `laneShift`). Same line: down from the sender's bottom edge into the gap below the line, across, and up into the recipient's bottom edge. Adjacent lines: out of the facing edge into the gap between them, across, and into the facing edge of the recipient; vertically aligned pins get a straight run. Lines further apart: out of the facing edge into the gap next to the sender's line, across to a vertical bus in the column gap right of the rightmost of the two capsules (shifted by that column corridor's shift), along the bus to the gap next to the recipient's line, across, and in. The vertical runs at the two capsules sit at `cx + fromPinShift` and `cx + toPinShift`. Corners are rounded with quadratic curves of `cornerRadius` (12 by default, reduced when a segment is too short).

Lane rule (SPEC §4): with the options from `laneOptions`, no two traces share a segment and no trace crosses a capsule. Horizontals in the same gap differ by their lane in that corridor; verticals at capsules differ by their pin, unique per column; bus verticals sit in column gaps, each on its own lane. Checked over every fixture in both orientations: 0 shared segments and 0 crossings (the same fixtures without lanes have up to 31 shared segments).

Inputs: `from`, `to` (capsule boxes), `cornerRadius` (number, optional), `shifts` (object `{ [corridorId]: number }`, optional, from `laneOptions`), `laneShift` (number, default 0, used for corridors missing from `shifts`), `fromPinShift`, `toPinShift` (number, default 0, added to the x of the vertical run at each capsule).

Output: `{ d, points, length }`. `d` is the SVG path (coordinates rounded to one decimal), `points` the unrounded corner points, `length` the path length accounting for the rounded corners.

Errors: throws `TypeError` if either box is missing.

Example, boxes from the `few.json` layout above (`a` = pid 30222, `b` = pid 30333 on the same line, `c` = pid 29904 on the line above `a` with the same center x):

```js
tracePath(a, b).d
// "M 340 468 L 340 488 Q 340 500 352 500 L 584 500 Q 596 500 596 488 L 596 468"
tracePath(a, b).points
// [{ x: 340, y: 468 }, { x: 340, y: 500 }, { x: 596, y: 500 }, { x: 596, y: 468 }], channel at the gap center 32 below the line
Math.round(tracePath(a, b).length)   // 310
tracePath(a, b, { laneShift: 6, fromPinShift: 20, toPinShift: -20 }).points
// [{ x: 360, y: 468 }, { x: 360, y: 506 }, { x: 576, y: 506 }, { x: 576, y: 468 }]
tracePath(c, d, { shifts: { "gap:0": 6, "col:1": -6, "gap:2": 12 } }).points
// [{ x: 340, y: 348 }, { x: 340, y: 386 }, { x: 462, y: 386 }, { x: 462, y: 632 }, { x: 340, y: 632 }, { x: 340, y: 652 }]
tracePath(c, a).d                    // "M 340 348 L 340 412", straight down
Math.round(tracePath(c, a).length)   // 64
// d = pid 30111 (tag-analyzer, line 3, same column as c): two lines apart, so the route uses the bus in the gap right of column 0
tracePath(c, d).points.length        // 6
tracePath(c, d).points[2].x          // 468, the gap between column 0 and column 1
```

## traceCorridors(from, to)

What it does: names the corridors a trace between two boxes runs through, in travel order. Horizontal runs use the gap below a line, `gap:<line>`; the vertical bus of a far route uses a column gap, `col:<gapIndex>` (gap 1 is between column 0 and column 1).

Inputs: `from`, `to` (capsule boxes).

Output: `string[]` with one id for a same-line or adjacent-line route, three (`gap`, `col`, `gap`) for a far route.

Errors: throws `TypeError` if a box is missing.

Example, boxes from the `few.json` layout (`c` line 0, `a` and `b` line 1, `d` line 3, all in column 0):

```js
traceCorridors(a, b) // ["gap:1"]
traceCorridors(c, a) // ["gap:0"]
traceCorridors(c, d) // ["gap:0", "col:1", "gap:2"]
traceCorridors(d, c) // ["gap:2", "col:1", "gap:0"]
```

## assignLanes(pairKeys, { columnOf, corridorsOf })

What it does: in order of first appearance gives every capsule pair a global lane number (0, 1, 2, …, used only for `data-lane`), a lane index in each corridor it uses (counted per corridor, so only traces sharing a gap or a column gap compete), and a pin index at each endpoint that is unique within the endpoint's column (all capsules sharing an x position across rows). Later keys never change earlier assignments, so adding a pair does not move existing traces. Duplicate keys are ignored.

Inputs:
- `pairKeys` (string[]): `traceKey` values in creation order.
- `columnOf` (function(pidString) → column id, optional): the renderer passes the capsule's `index` in its line; default identity (every capsule its own column).
- `corridorsOf` (function(key) → string[], optional): the renderer passes `traceCorridors` of the two boxes; default none.

Output: `{ lanes: Map<key, laneIndex>, pins: Map<key, { [pid]: pinIndex }>, corridorLanes: Map<key, { [corridorId]: laneIndex }>, columns: Map<pid, columnId>, perColumn: Map<columnId, count>, perCorridor: Map<corridorId, count> }`.

Errors: none.

Example:

```js
const first = assignLanes(["1|2", "1|3", "2|3"]);
[...first.lanes]            // [["1|2", 0], ["1|3", 1], ["2|3", 2]]
first.pins.get("1|3")       // { "1": 1, "3": 0 }   second trace at capsule 1, first at capsule 3
const next = assignLanes(["1|2", "1|3", "2|3", "1|4"]);
next.lanes.get("1|2")       // 0, unchanged
next.pins.get("1|4")        // { "1": 2, "4": 0 }
assignLanes(["1|2", "3|4"], { columnOf: () => "c" }).pins.get("3|4") // { "3": 2, "4": 3 }, pins shared per column
const corridors = assignLanes(["1|2", "1|3", "2|3"], { corridorsOf: (k) => (k === "2|3" ? ["gap:1"] : ["gap:0"]) });
[...corridors.corridorLanes] // [["1|2", { "gap:0": 0 }], ["1|3", { "gap:0": 1 }], ["2|3", { "gap:1": 0 }]]
[...corridors.perCorridor]   // [["gap:0", 2], ["gap:1", 1]]
```

## laneSlot(index, gap, halfWidth)

What it does: places lane number `index` inside a corridor whose free half-width is `halfWidth` (2 units of margin kept). The first lanes alternate outward from the center at the standard `gap` (0, +gap, −gap, +2·gap, …) until the corridor is full; the next lanes interleave at half steps between the existing ones (±gap/2, ±3·gap/2, …), then at quarter steps, and so on. A slot, once assigned, never depends on how many later lanes exist, so existing traces never move; the slots only repeat (two traces share a lane) when the step would fall below 1 unit, which takes 21 lanes in a standard 64-unit gap and 21 pins on a capsule edge.

Inputs: `index` (number ≥ 0), `gap` (number), `halfWidth` (number).

Output: number, the signed offset.

Errors: none.

Example:

```js
Array.from({ length: 13 }, (_, i) => laneSlot(i, 6, 32))
// [0, 6, -6, 12, -12, 18, -18, 24, -24, 30, -30, 1.5, -1.5]   eleven at the full gap, then half steps
Array.from({ length: 12 }, (_, i) => laneSlot(i, 20, 100))
// [0, 20, -20, 40, -40, 60, -60, 80, -80, 5, -5, 15]           pins on a capsule edge
Array.from({ length: 5 }, (_, i) => laneSlot(i, 6, 12.2))
// [0, 6, -6, 1.5, -1.5]                                         a compressed 24-unit gap
new Set(Array.from({ length: 21 }, (_, i) => laneSlot(i, 20, 100))).size // 21, all distinct
```

## laneOffset(index, gap)

What it does: turns a lane or pin index into a signed offset that alternates sides: 0, +gap, −gap, +2·gap, −2·gap, …

Inputs: `index` (number ≥ 0), `gap` (number, default `LANE.gap`).

Output: number.

Errors: none.

Example:

```js
[0, 1, 2, 3, 4, 5].map(i => laneOffset(i))  // [0, 6, -6, 12, -12, 18]
[0, 1, 2].map(i => laneOffset(i, 20))        // [0, 20, -20]
```

## laneOptions(assignment, key, from, to)

What it does: builds the `tracePath` options for one pair: a shift per corridor from its corridor lane (`laneSlot` with `LANE.gap` in half the line gap for `gap:` corridors, half the column gap for `col:` corridors) and the pin shifts at the two endpoints (`laneSlot` with `LANE.pinGap` in the capsule's half-width minus 10). The same geometry results whichever direction a pulse travels, and a pair's options never change when later pairs are added.

Inputs: `assignment` (from `assignLanes`), `key` (string), `from`, `to` (capsule boxes in travel order).

Output: `{ shifts: { [corridorId]: number }, fromPinShift, toPinShift }`.

Errors: none; an unknown key gives empty shifts and zero pins.

Example, `frontend/fixtures/fanin.json` with every pair routed in message order (`columnOf` = capsule index, `corridorsOf` = `traceCorridors`):

```js
keys // ["51001|51004", "51002|51004", "51003|51004", "51004|51005", "51001|51005"]
[...assignment.perColumn]   // [["0", 8], ["1", 2]]   eight trace ends in column 0, two in column 1
[...assignment.perCorridor] // [["gap:0", 2], ["col:1", 2], ["gap:2", 4], ["gap:1", 1], ["gap:3", 1], ["col:2", 1]]
laneOptions(assignment, "51001|51004", billing, manager) // { shifts: { "gap:0": 0, "col:1": 0, "gap:2": 0 }, fromPinShift: 0, toPinShift: 20 }
laneOptions(assignment, "51002|51004", docs, manager)    // { shifts: { "gap:1": 0, "col:1": 6, "gap:2": 6 }, fromPinShift: -20, toPinShift: 40 }
laneOptions(assignment, "51003|51004", infra, manager)   // { shifts: { "gap:2": -6 }, fromPinShift: -40, toPinShift: 60 }
// the three fan-in traces end at x 360, 380, 400 on the manager's top edge; the fifth trace (billing → path-finder-18) shares gap:0 and gap:2 with the first and runs 6 and 12 units beside it
```

Routing only the first four pairs and then all five gives identical paths for the first four. Over every fixture (`fanin`, `generated-many`, `generated-mid`, `generated-fast`, `messages`, `rename`, `removed`, `many`) in both orientations, lanes give 0 shared segments and 0 capsule crossings, against up to 31 shared segments without lanes, and routing every prefix of the pair list moves 0 earlier routes (on `generated-many` column 0 holds 13 pins; the twelfth and thirteenth take half-step slots at ±5 and ±15 while the first eleven stay put).

## traceKey(pidA, pidB)

What it does: returns the order-independent identifier of the trace between two capsules.

Inputs: `pidA`, `pidB` (number or string).

Output: string, the two PIDs as strings sorted and joined with `|`.

Errors: none.

Example:

```js
traceKey(30333, 30222) // "30222|30333"
traceKey(30222, 30333) // "30222|30333"
```

## edgeBox(nearBox)

What it does: returns a zero-width box at the left edge of the given box's line, one gap left of column 0. The renderer uses it as the origin of a pulse whose sender is unknown (`from: null`) and as the destination when only the sender is known.

Inputs: `nearBox` (capsule box).

Output: a box with `width` 0, `cx` equal to `nearBox.columnOrigin - CAPSULE.gapX` (194 in landscape, 24 in portrait), same `y`, `height`, `cy`, `line`, and `columnOrigin` as `nearBox`, `pid` null, `index` -1.

Errors: throws `TypeError` if `nearBox` is missing.

Example:

```js
edgeBox(a).cx    // 194
edgeBox(a).line  // 1
edgeBox(boardLayout(liveSessions(state), { portrait: true }).capsules.get(30222)).cx // 24
```

## truncateLabel(label, maxChars)

What it does: cuts a label that is longer than `maxChars` and appends an ellipsis so the result is exactly `maxChars` characters. The full name stays available in the capsule's tooltip.

Inputs: `label` (string), `maxChars` (number, at least 2).

Output: string.

Errors: none.

Example:

```js
truncateLabel("add-semantic-similarity-scores-4a", 21) // "add-semantic-similar…"
truncateLabel("listings-bc", 21)                       // "listings-bc"
truncateLabel("abcdefghij", 5)                         // "abcd…"
truncateLabel("ab", 1)                                 // "a…"
```

Removed in v2: `ringPositions`, `labelSide`, `labelPlacement`, `messageCurve` (the ring is gone).
