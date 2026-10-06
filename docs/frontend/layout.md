# layout.js

Pure geometry for the Circuit board. No DOM, runs in Node. Exports two constant objects and five functions.

Constants: `BOARD = { width: 1360, height: 1000, marginX: 60, marginTop: 70, marginBottom: 70, labelWidth: 170 }` (the viewBox and the space reserved on the left for folder labels) and `CAPSULE = { width: 220, height: 56, gapX: 36, rowGap: 64, cornerRadius: 14 }`.

A capsule box is `{ pid, folder, x, y, width, height, cx, cy, line, index, pitch }`: top-left corner, size, center, which line of the board it sits on (0 at the top), its position in that line, and the vertical distance between lines in this layout (used to keep trace channels inside the gaps).

## boardLayout(sessions, { width, height })

What it does: groups sessions into one row per folder (folders compared with `_` and `-` equal, sorted alphabetically), orders each row by `firstSeen` then name so a capsule keeps its slot while live and newcomers append at the end (placeholders, which have no `firstSeen`, go last), wraps a row onto further lines when it has more capsules than fit (`perLine = floor((width - 2·marginX - labelWidth + gapX) / (capsule width + gapX))`, 4 at the default width), spaces the lines evenly (pitch at most `height + rowGap` of a capsule, compressed when many lines must fit) and centers the stack vertically.

Inputs:
- `sessions` (Session[]): usually `liveSessions(state)`. Not mutated.
- `width`, `height` (number, optional): board size in user units, default `BOARD.width` × `BOARD.height`.

Output: `{ capsules: Map<pid, box>, rows: [{ folder, label, x, y, cy }], lineCount, perLine }`. `rows` has one entry per folder at its first line, for the row label.

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

With `many.json` (15 sessions, 8 folders): 8 lines, every folder on one line; `add-semantic-similarity-scores` is the first row.

## tracePath(from, to, { cornerRadius })

What it does: routes an orthogonal trace between two boxes so that it never crosses another capsule. Same line: down from the sender's bottom edge to a channel below the line (22 units, or half the gap to the next line when lines are packed), across, and up into the recipient's bottom edge. Adjacent lines: out of the facing edge, to the channel midway between the two lines, across, and into the facing edge of the recipient; vertically aligned boxes get a straight run. Lines further apart: out of the facing edge into the channel next to the sender's line, across to a vertical bus in the column gap right of the rightmost of the two capsules, along the bus to the channel next to the recipient's line, across, and in. Corners are rounded with quadratic curves of `cornerRadius` (12 by default, reduced when a segment is too short).

Inputs: `from`, `to` (capsule boxes), `cornerRadius` (number, optional).

Output: `{ d, points, length }`. `d` is the SVG path (coordinates rounded to one decimal), `points` the unrounded corner points, `length` the path length accounting for the rounded corners.

Errors: throws `TypeError` if either box is missing.

Example, boxes from the `few.json` layout above (`a` = pid 30222, `b` = pid 30333 on the same line, `c` = pid 29904 on the line above `a` with the same center x):

```js
tracePath(a, b).d
// "M 340 468 L 340 479 Q 340 490 351 490 L 585 490 Q 596 490 596 479 L 596 468"
tracePath(a, b).points
// [{ x: 340, y: 468 }, { x: 340, y: 490 }, { x: 596, y: 490 }, { x: 596, y: 468 }]
Math.round(tracePath(a, b).length)   // 290
tracePath(c, a).d                    // "M 340 348 L 340 412", straight down
Math.round(tracePath(c, a).length)   // 64
// d = pid 30111 (tag-analyzer, line 3, same column as c): two lines apart, so the route uses the bus in the gap right of column 0
tracePath(c, d).points.length        // 6
tracePath(c, d).points[2].x          // 468, the gap between column 0 and column 1
```

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

What it does: returns a zero-width box at the left edge of the given box's line, just right of the folder label. The renderer uses it as the origin of a pulse whose sender is unknown (`from: null`) and as the destination when only the sender is known.

Inputs: `nearBox` (capsule box).

Output: a box with `width` 0, `cx` equal to `BOARD.marginX + BOARD.labelWidth - CAPSULE.gapX` (194), same `y`, `height`, `cy`, and `line` as `nearBox`, `pid` null, `index` -1.

Errors: throws `TypeError` if `nearBox` is missing.

Example:

```js
edgeBox(a).cx    // 194
edgeBox(a).line  // 1
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
