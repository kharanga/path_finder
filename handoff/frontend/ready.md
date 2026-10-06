# Ready: F13 distinct trace lanes (round 2)

## Done

Round 2, review failure 1 (crowded columns shifted earlier pins): `fittedGap` is gone. Lane and pin positions now come from `laneSlot(index, gap, halfWidth)`: the first lanes alternate outward at the standard gap, later ones interleave at half steps (then quarter steps) between the existing ones, so a slot never depends on how many later lanes exist. Verified with a new prefix-stability check: routing every prefix of the pair list on every fixture in both orientations moves 0 earlier routes (the validator's case, `generated-many` with 13 pins in column 0, included), still with 0 shared segments and 0 crossings. Manager decision 2026-10-06: keep this fix; the acceptance stands as originally written with no limitation to document. Round 2 touched `frontend/layout.js`, `docs/frontend/layout.md`, and one phrase in `docs/frontend/render.md` (lane positions never change once assigned); no other code changed.

Final `layout.js` exports: `BOARD`, `BOARD_PORTRAIT`, `CAPSULE`, `LANE`, `boardFor`, `boardLayout`, `tracePath`, `traceCorridors`, `assignLanes`, `laneOffset`, `laneSlot`, `laneOptions`, `traceKey`, `edgeBox`, `truncateLabel`.

`layout.md` examples for `laneSlot`: `Array.from({ length: 13 }, (_, i) => laneSlot(i, 6, 32))` → `[0, 6, -6, 12, -12, 18, -18, 24, -24, 30, -30, 1.5, -1.5]`; `Array.from({ length: 12 }, (_, i) => laneSlot(i, 20, 100))` → `[0, 20, -20, 40, -40, 60, -60, 80, -80, 5, -5, 15]`; `Array.from({ length: 5 }, (_, i) => laneSlot(i, 6, 12.2))` → `[0, 6, -6, 1.5, -1.5]`; 21 pins at gap 20 in half-width 100 are all distinct.

`frontend/layout.js` (pure)
- `traceCorridors(from, to)`: names the corridors a route uses (`gap:<line>` for the inter-line gap below a line, `col:<gap>` for the column gap of a far route's bus).
- `assignLanes(pairKeys, { columnOf, corridorsOf })`: in order of first appearance gives each pair a global lane number, a lane index in every corridor it uses (counted per corridor, so only traces that actually share a gap or a column gap compete), and a pin index at each endpoint that is unique within the endpoint's column (capsules sharing an x across rows). Earlier pairs never change when a pair is added.
- `laneOffset(index, gap)`: alternating offsets 0, +g, −g, +2g, −2g, …
- `laneSlot(index, gap, halfWidth)`: fixed interleaved slots, see round 2 above.
- `laneOptions(assignment, key, from, to)`: per-corridor shifts and the two pin shifts for `tracePath`.
- `tracePath` takes `{ shifts, laneShift, fromPinShift, toPinShift }`; every horizontal run now sits at the center of its inter-line gap plus the corridor shift (previously a fixed 22 below the line), which also removed a latent collision between channel types in compressed layouts.
- `LANE = { gap: 6, pinGap: 20 }`.

`frontend/render.js`: keeps the pair order (reset with the trace layer on a snapshot), computes columns from capsule index and corridors from boxes, and routes traces, pulses, and charges through `laneOptions`, so a pulse rests at its pin and a charge glows along its own lane. Traces carry `data-lane`.

Fixture: `frontend/fixtures/fanin.json` (three sources into `path-finder-0d` with notify, its row neighbor too, one trace parallel to the first in a shared corridor, then the manager goes idle and the three charges drain).

Verified (Node, scratchpad `lanes-check.mjs`, both orientations, every fixture incl. the W4 outputs `generated-many`/`generated-mid`/`generated-fast`): shared segments 0 with lanes (7 to 31 without), capsule crossings 0, routes moved by later pairs 0 for every prefix of every fixture's pair list. Headless Chrome screenshots of `fanin`, `generated-fast` landscape and portrait look as expected (the Chrome extension was down, so no interactive session this round).

Docs: `layout.md` (lane rule, new functions with computed examples, corrected `tracePath` values), `render.md` (lane routing), `README.md` (fixture row). Example runner: 275 checks, 0 failures, including shared-segment, crossing, and prefix-stability checks for every fixture in both orientations.

SPEC.md §8.2 F13 is `[~] path-finder-18`.

## How to test

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

1. `?fixture=fanin`: three pulses arrive at `path-finder-0d` on three distinct pins along its top edge, each on its own route; three glowing charges, none overlapping, all draining at ~9.5 s. The fifth message (`billing-service-e1` → `path-finder-18`) runs beside the first trace in the same corridor 6 units apart. Zoom in: no two traces share a line anywhere.
2. `?fixture=generated-fast` (15 sessions, W4 output): dense board, every corridor shows separate parallel lines; nothing passes through a capsule. Same at phone width (portrait).
3. Stability: load `?fixture=fanin`, note the first trace's path (`document.querySelector('.trace[data-trace="51001|51004"]').getAttribute('d')`) after 2 s; after all events it is unchanged.
4. Node: `layout.md` examples (`assignLanes` with columns and corridors, `traceCorridors`, `laneSlot`, `laneOptions` on `fanin`, `tracePath` with shifts), or the scratchpad runner. `node run-examples.mjs <repo>` → 275 passed.
5. Checker: `node lanes-check.mjs <repo>` prints shared segments with and without lanes per fixture; `node lanes-check.mjs <repo> crossings` prints capsule crossings (all 0); `node lanes-check.mjs <repo> stability` prints routes moved by later pairs (all 0).

## Requests

1. Validator (V8): runner and `lanes-check.mjs` at `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/658ff14a-2610-461f-9302-e64c02a54c6a/scratchpad/docs-check/`. The checker's `routesFor` / `sharedSegments` / `crossings` / `prefixStable` are meant to become the V8 unit tests.
2. Manager: in portrait with 14 lines the row labels above capsules get close to the capsule of the line above (visible on `generated-fast` at 390 px). Not an F13 matter; say if you want a later task to hide row labels when the pitch is compressed.

## Blocked

Nothing.
