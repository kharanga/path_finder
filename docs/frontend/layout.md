# layout.js

Pure geometry. Decides where each session sits on the ring and where its labels go. No DOM.

## ringPositions(sessions, { cx, cy, radius })

What it does: sorts sessions by folder, then by display name (or PID when unnamed), and spaces them evenly around a circle starting at the top and going clockwise. Grouping by folder keeps same-folder sessions adjacent. Ordering depends only on folder and name, never on arrival order, so a reload gives the same picture, and a restarted session (new PID, new name, same folder) returns to its folder's group. With one session per folder its spot is identical after a restart.

Inputs:
- `sessions` (Session[]): usually `liveSessions(state)`. The input array is not mutated.
- `cx`, `cy` (number): ring center in SVG user units.
- `radius` (number): ring radius.

Output: `Map<pid, { x, y, angle }>`. `angle` is in radians, `-π/2` at the top.

Errors: none. An empty array yields an empty map.

Example:

```js
const sessions = [
  { pid: 29904, session: "listings-bc", folder: "listings" },
  { pid: 30222, session: "path-finder-18", folder: "path_finder" },
  { pid: 30333, session: "path-finder-e5", folder: "path_finder" },
  { pid: 30444, session: "scratch-7a", folder: "scratch" },
];
const positions = ringPositions(sessions, { cx: 500, cy: 500, radius: 360 });
[...positions.entries()].map(([pid, p]) => [pid, Math.round(p.x), Math.round(p.y)])
// [[29904, 500, 140], [30222, 860, 500], [30333, 500, 860], [30444, 140, 500]]
ringPositions([], { cx: 500, cy: 500, radius: 360 }).size // 0
```

## labelSide(angle)

What it does: picks which side of a body its label goes on so the text points away from the ring center.

Inputs: `angle` (number, radians) from `ringPositions`.

Output: `"right"` on the right half, `"left"` on the left half, `"top"` or `"bottom"` when the body is within about 11.5° of the vertical axis (`|cos(angle)| < 0.2`).

Errors: none.

Example:

```js
labelSide(-Math.PI / 2) // "top"
labelSide(Math.PI / 2)  // "bottom"
labelSide(0)            // "right"
labelSide(Math.PI)      // "left"
```

## labelPlacement(angle, { bodyRadius, lineHeight, hasRole })

What it does: returns the text anchor and the x and y offsets, relative to the body center, for the name line and the role line. Side labels hang off the outer side of the body and are vertically centered (two lines when a role exists). Top labels stack above the body, bottom labels below, so neither line ever crosses the body circle. With 15 evenly spaced bodies on a radius-340 ring the neighbors are about 142 units apart along the arc, which is more than two lines of 22-unit text, so labels do not overlap.

Inputs:
- `angle` (number, radians).
- `bodyRadius` (number): body circle radius.
- `lineHeight` (number): font size of the name line in user units.
- `hasRole` (boolean): whether a second line will be drawn.

Output: `{ anchor, x, nameY, roleY }` where `anchor` is an SVG `text-anchor` value.

Errors: none.

Example:

```js
labelPlacement(0, { bodyRadius: 18, lineHeight: 22, hasRole: false })
// { anchor: "start", x: 32, nameY: 7.7, roleY: 7.7 }
labelPlacement(0, { bodyRadius: 18, lineHeight: 22, hasRole: true })
// { anchor: "start", x: 32, nameY: -3.3, roleY: 18.7 }
labelPlacement(-Math.PI / 2, { bodyRadius: 18, lineHeight: 22, hasRole: true })
// { anchor: "middle", x: 0, nameY: -58, roleY: -36 }
labelPlacement(Math.PI / 2, { bodyRadius: 18, lineHeight: 22, hasRole: false })
// { anchor: "middle", x: 0, nameY: 54, roleY: 76 }
```

Values are computed with floating point; compare with a tolerance of 0.01.

## messageCurve(from, to, center, { bow, sideOffset })

What it does: builds the quadratic Bézier path a message particle follows and a `notify_on_idle` thread is drawn along. The control point is the midpoint of the chord pulled toward the ring center by `bow` (0.55 by default) and pushed `sideOffset` units (40 by default) to one side, so curves between opposite bodies do not pass exactly through the center and two bodies exchanging messages get mirrored arcs. Coordinates in the path string are rounded to one decimal.

Inputs:
- `from`, `to` (`{ x, y }`): endpoints, usually body positions.
- `center` (`{ x, y }`): ring center.
- `bow` (number, optional): 0 keeps the control point on the chord, 1 puts it at the center.
- `sideOffset` (number, optional): perpendicular push in user units.

Output: `{ d, control, length }`. `d` is the SVG path (`M x y Q cx cy x y`), `control` the control point, `length` the arc length approximated with 24 segments, used for stroke-dash drawing and snapping.

Errors: none. Coincident endpoints yield a degenerate path of length about 0 with the control point pushed toward the center.

Example:

```js
const curve = messageCurve({ x: 680, y: 160 }, { x: 1020, y: 500 }, { x: 680, y: 500 });
curve.d               // "M 680 160 Q 728.2 451.8 1020 500"
Math.round(curve.length) // 519
curve.control         // { x: 728.2157…, y: 451.7842… }
```

## truncateLabel(label, maxChars)

What it does: cuts a label that is longer than `maxChars` and appends an ellipsis so the result is exactly `maxChars` characters. The full name stays available in the body's tooltip.

Inputs: `label` (string), `maxChars` (number, at least 2).

Output: string.

Errors: none.

Example:

```js
truncateLabel("add-semantic-similarity-scores-4a", 24) // "add-semantic-similarity…"
truncateLabel("listings-bc", 24)                       // "listings-bc"
truncateLabel("abcdefghij", 5)                         // "abcd…"
truncateLabel("ab", 1)                                 // "a…"
```
