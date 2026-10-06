# layout.js

Pure geometry. Decides where each session sits on the ring.

## ringPositions(sessions, { cx, cy, radius })

What it does: sorts sessions by folder, then by display name (or PID when unnamed), and spaces them evenly around a circle starting at the top and going clockwise. Grouping by folder keeps same-folder sessions adjacent. Because ordering depends only on folder and name, a restarted session with the same folder lands in the same group. F2 will refine the position so it survives restarts with a new name.

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

Output: `"right"` when the body is on the right half, `"left"` on the left half, `"center"` when it is within about 11° of the top or bottom.

Errors: none.

Example:

```js
labelSide(-Math.PI / 2) // "center"
labelSide(0)            // "right"
labelSide(Math.PI)      // "left"
```
