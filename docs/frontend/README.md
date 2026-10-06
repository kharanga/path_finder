# frontend docs

Owner: frontend-builder.

Files in `frontend/` and where each is documented:

| File | Role | Docs |
|---|---|---|
| `index.html` | the only page: top bar, `<svg id="orbit">` (the board; the v1 element id is kept as an identifier), message panel, timeline strip | `app.md` |
| `orbit.css` | all styles (v1 file name kept), state colors, reduced-motion and phone-width rules | `render.md` (styling hooks), `app.md` (responsive notes) |
| `app.js` | bootstrap, wires connect → state → render, timeline, panel | `app.md` |
| `connect.js` | SSE client with fixture fallback | `connect.md` |
| `state.js` | pure reducer: sessions, placeholders, messages, threads | `state.md` |
| `layout.js` | pure geometry: folder rows, capsule boxes, orthogonal traces | `layout.md` |
| `render.js` | SVG renderer: capsules, traces, charges, pulses, selection | `render.md` |
| `timeline.js` | event recorder, state at an instant, scrubber strip | `timeline.md` |
| `panel.js` | message detail panel | `panel.md` |
| `editor.js` | session removal editor: Edit toggle, confirmation, `POST /sessions/<pid>/remove` | `editor.md` |
| `fixtures/*.json` | page fixtures, table below | this file |

Pure modules (`state.js`, `layout.js`, `panel.js` except `createPanel`, `timeline.js` except `mountTimelineStrip`, `editor.js` except `createEditor`) import nothing from the DOM and run in Node as is. The rest need a DOM; a stub that implements `createElement`, `createElementNS`, `setAttribute`/`getAttribute`, `classList`, `dataset`, `style`, `appendChild`/`remove`, `querySelector(All)` with class, attribute, and descendant selectors, `textContent`, `addEventListener`/`dispatchEvent`, `hidden`, `click`, and `focus` is enough to run every example in these docs.

Each public function is documented with What it does, Inputs, Output, Errors, and Example. Docs are updated in the same task as the code. The validator checks every example.

## Running the page without the server

The page has no build step but uses ES modules, so it must be served over HTTP, not opened as a file. Any static server rooted at `frontend/` works:

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

Then open `http://127.0.0.1:8787/`. Because `/events` returns 404 there, the page falls back to `frontend/fixtures/empty.json`, and the Edit toggle stays disabled with the hint "Removal needs the server. Fixture mode has none." For the editor, run the real server (`node webhook/server.js --demo --port 4848` gives a safe sandbox with its own temp events file; the default port 4747 may be the user's live dashboard). Force a fixture with `?fixture=<name>`:

| Fixture | Contents |
|---|---|
| `empty` | zero sessions |
| `one` | one busy session that goes idle after 2 s |
| `few` | 5 sessions across 4 folders, roles, an unnamed session that gets its name, a `liveness` end |
| `messages` | 5 sessions incl. one `waiting`, then: a `notify_on_idle` message whose recipient goes busy then idle (charge drains back), a plain message, a reply, a notify message to a name not on the board (placeholder capsule), a notify message whose recipient ends (charge dropped), and a message with `from: null` |
| `removed` | 4 sessions and one historical message (a faint trace); `listings-bc` ends (footprint), `path-finder-e5` is `removed` (gone at once, no footprint), a message from it reinstates it as idle, then it turns busy and sends a message |
| `fanin` | 5 sessions; three sources message `path-finder-0d` with notify, its row neighbor messages it too, and one source messages the neighbor so two traces share a corridor; then the manager goes idle and the three charges drain |
| `rename` | 3 sessions; a message, then pid 29248 is renamed `path-finder-0d` → `manager-drives-feature-work`, a message sent under the former name, a notify to the former name whose charge drains when the renamed capsule goes idle, and a message to a truly unknown name (placeholder) |
| `generated-many` | generator output: 15 sessions built up from an empty snapshot over ~160 s, includes `waiting`, a mid-run rename of one PID to `manager-drives-feature-work`, two deaths via `liveness`, a `from: null` message, a message to a name that never appears. Regenerate with the commands in `docs/webhook/fake-generator.md` |
| `generated-mid` | generator output: 8 sessions with a populated snapshot (mid-run connect), ~95 s of events, same scenarios |
| `generated-fast` | the 15-session run at `--speed 10`: 16 s total, rename at ~8 s. `node webhook/fake.js --fixture frontend/fixtures/generated-fast.json --speed 10 --start-time 2026-10-05T21:40:00Z` |
| `many` | 15 sessions across 8 folders (8 rows), same-folder siblings, a 33-character name, then a restart: one session ends by `liveness` and a new PID appears in the same folder row |

Other query parameters: `motion=reduce` or `motion=full` forces the reduced-motion behavior of pulses and charges on or off (CSS still follows the OS setting).

Fixture file shape:

```json
{
  "snapshot": { "sessions": [], "messages": [] },
  "events": [ { "delayMs": 1500, "event": "session", "data": { "...": "a §3 event" } } ]
}
```

`snapshot` matches the SSE snapshot in `docs/overview.md`. Each entry in `events` is replayed through the same path as a live SSE event, `delayMs` after the previous entry. `event` is `session`, `message`, or `liveness`.
