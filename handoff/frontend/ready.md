# Ready: F1 static page skeleton

## Done

`frontend/` now holds the page with no build step:

- `index.html`: top bar with status badge, `<svg id="orbit">`, loads `app.js` as an ES module.
- `orbit.css`: all styles, dark palette, state colors via `data-state`.
- `app.js`: `start()` wires connect → state → render.
- `connect.js`: `connect()` opens `EventSource("/events")`, handles `snapshot`, `session`, `message`, `liveness`. Falls back to `fixtures/empty.json` when the endpoint is absent. `?fixture=<name>` forces `fixtures/<name>.json`.
- `state.js`: reducer keyed by PID. `applySnapshot`, `applyEvent`, `liveSessions`, `sessionByName`, `sessionLabel`. Pure, runs in Node.
- `layout.js`: `ringPositions()` evenly spaced, grouped by folder. `labelSide()`. Pure.
- `render.js`: `createRenderer(svg)` returns `draw(state)`. Empty ring with "No sessions running", one body per live session with name and optional role.
- `fixtures/empty.json`, `fixtures/few.json` (5 sessions, 1 message, then 4 timed events incl. a `liveness` end and a PID-only session getting its name).

Docs: `docs/frontend/README.md`, `state.md`, `layout.md`, `connect.md`, `render.md`, `app.md`.

SPEC.md §8.2 F1 marked `[~] path-finder-18`.

## How to test

From the repo root:

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

1. Open `http://127.0.0.1:8787/`. Acceptance check: status badge says `fixture`, dashed ring, centered "No sessions running". `/events` is 404 on this server, which exercises the fallback path.
2. Open `http://127.0.0.1:8787/?fixture=few`. Five bodies with labels. `tag-analyzer-63` and `path-finder-e5` are yellow (busy) and show roles underneath. `pid 30444` is light blue (started). Within ~7 s: `listings-bc` turns yellow, `pid 30444` becomes `scratch-7a`, `tag-analyzer-63` leaves the ring.
3. Browser console has no errors.
4. Pure modules in Node (for V3 later):

```
cd frontend && node --input-type=module -e '
import { createState, applySnapshot, liveSessions, sessionLabel } from "./state.js";
import { ringPositions } from "./layout.js";
import fs from "node:fs";
const s = applySnapshot(createState(), JSON.parse(fs.readFileSync("fixtures/few.json","utf8")).snapshot);
console.log(liveSessions(s).map(sessionLabel));
console.log(ringPositions(liveSessions(s), {cx:500,cy:500,radius:360}).size);'
```

Expected: the five labels sorted by folder then name, and `5`.

Every example in `docs/frontend/*.md` is meant to be runnable as written (browser examples need the page loaded with the named fixture).

## Requests

1. **Contract (docs/overview.md §Server to page contract):** the page uses ES modules and a stylesheet, so the server must serve the whole `frontend/` folder as static files, not only `GET /` → `index.html`. Proposed wording: "`GET /` serves `frontend/index.html`; any other path not starting with `/events` is served from `frontend/` as a static file." Request to webhook-builder via manager.
2. **W4 fixture format:** it would help if the fake generator could also emit the fixture shape in `docs/frontend/README.md` (`{snapshot, events:[{delayMs,event,data}]}`) in addition to a raw `events.jsonl`, so the page can be driven without the server. Optional, I can also write a tiny converter in `frontend/` if preferred.

## Blocked

Nothing.
