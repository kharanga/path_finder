# Ready: F13 distinct trace lanes

## Done

`frontend/layout.js` (pure)
- `traceCorridors(from, to)`: names the corridors a route uses (`gap:<line>` for the inter-line gap below a line, `col:<gap>` for the column gap of a far route's bus).
- `assignLanes(pairKeys, { columnOf, corridorsOf })`: in order of first appearance gives each pair a global lane number, a lane index in every corridor it uses (counted per corridor, so only traces that actually share a gap or a column gap compete), and a pin index at each endpoint that is unique within the endpoint's column (capsules sharing an x across rows). Earlier pairs never change when a pair is added.
- `laneOffset(index, gap)`: alternating offsets 0, +g, −g, +2g, −2g, …
- `fittedGap(halfWidth, count, gap)`: the standard gap while the lanes fit a corridor, a smaller gap (never below 1) when it is crowded, so dense boards never overlap instead of wrapping.
- `laneOptions(assignment, key, from, to)`: per-corridor shifts and the two pin shifts for `tracePath`.
- `tracePath` takes `{ shifts, laneShift, fromPinShift, toPinShift }`; every horizontal run now sits at the center of its inter-line gap plus the corridor shift (previously a fixed 22 below the line), which also removed a latent collision between channel types in compressed layouts.
- `LANE = { gap: 6, pinGap: 20 }`.

`frontend/render.js`: keeps the pair order (reset with the trace layer on a snapshot), computes columns from capsule index and corridors from boxes, and routes traces, pulses, and charges through `laneOptions`, so a pulse rests at its pin and a charge glows along its own lane. Traces carry `data-lane`.

Fixture: `frontend/fixtures/fanin.json` (three sources into `path-finder-0d` with notify, its row neighbor too, one trace parallel to the first in a shared corridor, then the manager goes idle and the three charges drain).

Verified (Node, scratchpad `lanes-check.mjs`, both orientations, every fixture incl. the W4 outputs `generated-many`/`generated-mid`/`generated-fast`): shared segments 0 with lanes (7 to 31 without), capsule crossings 0, and adding the fifth `fanin` pair leaves the first four paths byte-identical. Headless Chrome screenshots of `fanin`, `generated-fast` landscape and portrait look as expected (the Chrome extension was down, so no interactive session this round).

Docs: `layout.md` (lane rule, new functions with computed examples, corrected `tracePath` values), `render.md` (lane routing), `README.md` (fixture row). Example runner: 257 checks, 0 failures, including shared-segment and crossing checks for every fixture in both orientations.

SPEC.md §8.2 F13 is `[~] path-finder-18`.

## How to test

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

1. `?fixture=fanin`: three pulses arrive at `path-finder-0d` on three distinct pins along its top edge, each on its own route; three glowing charges, none overlapping, all draining at ~9.5 s. The fifth message (`billing-service-e1` → `path-finder-18`) runs beside the first trace in the same corridor 6 units apart. Zoom in: no two traces share a line anywhere.
2. `?fixture=generated-fast` (15 sessions, W4 output): dense board, every corridor shows separate parallel lines; nothing passes through a capsule. Same at phone width (portrait).
3. Stability: load `?fixture=fanin`, note the first trace's path (`document.querySelector('.trace[data-trace="51001|51004"]').getAttribute('d')`) after 2 s; after all events it is unchanged.
4. Node: `layout.md` examples (`assignLanes` with columns and corridors, `traceCorridors`, `fittedGap`, `laneOptions` on `fanin`, `tracePath` with shifts), or the scratchpad runner. `node run-examples.mjs <repo>` → 257 passed.
5. Checker: `node lanes-check.mjs <repo>` prints shared segments with and without lanes per fixture; `node lanes-check.mjs <repo> crossings` prints capsule crossings (all 0).

## Requests

1. Validator (V8): runner and `lanes-check.mjs` at `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/658ff14a-2610-461f-9302-e64c02a54c6a/scratchpad/docs-check/`. The checker's `routesFor` / `sharedSegments` / `crossings` are meant to become the V8 unit tests.
2. Manager: in portrait with 14 lines the row labels above capsules get close to the capsule of the line above (visible on `generated-fast` at 390 px). Not an F13 matter; say if you want a later task to hide row labels when the pitch is compressed.

## Blocked

Nothing.
