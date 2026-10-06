# frontend docs

Owner: frontend-builder.

Files in `frontend/` and where each is documented:

| File | Role | Docs |
|---|---|---|
| `index.html` | the only page: top bar, `<svg id="orbit">`, message panel, timeline strip | `app.md` |
| `orbit.css` | all styles, state colors, reduced-motion and phone-width rules | `render.md` (styling hooks), `app.md` (responsive notes) |
| `app.js` | bootstrap, wires connect → state → render, timeline, panel | `app.md` |
| `connect.js` | SSE client with fixture fallback | `connect.md` |
| `state.js` | pure reducer: sessions, placeholders, messages, threads | `state.md` |
| `layout.js` | pure geometry: ring slots, label placement, message curves | `layout.md` |
| `render.js` | SVG renderer: bodies, particles, threads, selection | `render.md` |
| `timeline.js` | event recorder, state at an instant, scrubber strip | `timeline.md` |
| `panel.js` | message detail panel | `panel.md` |
| `fixtures/*.json` | page fixtures, table below | this file |

Pure modules (`state.js`, `layout.js`, `panel.js` except `createPanel`, `timeline.js` except `mountTimelineStrip`) import nothing from the DOM and run in Node as is. The rest need a DOM; a stub that implements `createElement`, `createElementNS`, `setAttribute`/`getAttribute`, `classList`, `dataset`, `style`, `appendChild`/`remove`, `querySelector(All)` with class, attribute, and descendant selectors, `textContent`, `addEventListener`/`dispatchEvent`, `hidden`, `click`, and `focus` is enough to run every example in these docs.

Each public function is documented with What it does, Inputs, Output, Errors, and Example. Docs are updated in the same task as the code. The validator checks every example.

## Running the page without the server

The page has no build step but uses ES modules, so it must be served over HTTP, not opened as a file. Any static server rooted at `frontend/` works:

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

Then open `http://127.0.0.1:8787/`. Because `/events` returns 404 there, the page falls back to `frontend/fixtures/empty.json`. Force a fixture with `?fixture=<name>`:

| Fixture | Contents |
|---|---|
| `empty` | zero sessions |
| `one` | one busy session that goes idle after 2 s |
| `few` | 5 sessions across 4 folders, roles, an unnamed session that gets its name, a `liveness` end |
| `messages` | 5 sessions incl. one `waiting`, then: a `notify_on_idle` message whose recipient goes busy then idle (thread snaps back), a plain message, a reply, a notify message to a name not on the ring (placeholder body), a notify message whose recipient ends (thread dropped), and a message with `from: null` |
| `rename` | 3 sessions; a message, then pid 29248 is renamed `path-finder-0d` → `manager-drives-feature-work`, a message sent under the former name, a notify to the former name that snaps when the renamed body goes idle, and a message to a truly unknown name (placeholder) |
| `generated-many` | W4 output: 15 sessions built up from an empty snapshot over ~160 s, includes `waiting`, a rename, two deaths via `liveness`, a message to a name that never appears. Regenerate with the commands in `docs/webhook/fake-generator.md` |
| `generated-mid` | W4 output: 8 sessions with a populated snapshot (mid-run connect), ~95 s of events |
| `many` | 15 sessions across 8 folders, same-folder siblings, a 30-character name, then a restart: one session ends by `liveness` and a new PID appears in the same folder |

Other query parameters: `motion=reduce` or `motion=full` forces the reduced-motion behavior of particles and threads on or off (CSS still follows the OS setting).

Fixture file shape:

```json
{
  "snapshot": { "sessions": [], "messages": [] },
  "events": [ { "delayMs": 1500, "event": "session", "data": { "...": "a §3 event" } } ]
}
```

`snapshot` matches the SSE snapshot in `docs/overview.md`. Each entry in `events` is replayed through the same path as a live SSE event, `delayMs` after the previous entry. `event` is `session`, `message`, or `liveness`.
