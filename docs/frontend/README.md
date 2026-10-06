# frontend docs

Owner: frontend-builder.

One markdown file per module in `frontend/`:

- `state.md`: snapshot and event reducer (`frontend/state.js`).
- `layout.md`: ring placement keyed by folder (`frontend/layout.js`).
- `connect.md`: SSE connection with fixture fallback (`frontend/connect.js`).
- `render.md`: bodies, labels, empty ring (`frontend/render.js`).
- `timeline.md`: event recording, state at an instant, scrubber strip (`frontend/timeline.js`).
- `panel.md`: message detail panel (`frontend/panel.js`).
- `app.md`: page bootstrap (`frontend/app.js`, `frontend/index.html`).

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
| `generated-many` | W4 output: 15 sessions built up from an empty snapshot over ~160 s, includes `waiting`, a rename, two deaths via `liveness`, a message to a name that never appears. Regenerate with the commands in `docs/webhook/fake-generator.md` |
| `generated-mid` | W4 output: 8 sessions with a populated snapshot (mid-run connect), ~95 s of events |
| `many` | 15 sessions across 8 folders, same-folder siblings, a 30-character name, then a restart: one session ends by `liveness` and a new PID appears in the same folder |

Fixture file shape:

```json
{
  "snapshot": { "sessions": [], "messages": [] },
  "events": [ { "delayMs": 1500, "event": "session", "data": { "...": "a §3 event" } } ]
}
```

`snapshot` matches the SSE snapshot in `docs/overview.md`. Each entry in `events` is replayed through the same path as a live SSE event, `delayMs` after the previous entry. `event` is `session`, `message`, or `liveness`.
