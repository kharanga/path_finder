# state.js

Pure reducer. Holds every session keyed by PID and the message history. No DOM access, so it runs in Node for tests.

The state object:

```js
{ sessions: Map<number, Session>, messages: Message[], threads: Thread[], lastEventTs: string | null, snapshotSeq: number }
```

`Session` is `{ pid, session, folder, role, state, ts, firstSeen }`. `state` is one of `started`, `busy`, `waiting`, `idle`, `ended`. `Message` is `{ ts, from, to, text, notify_on_idle }`. `Thread` is `{ id, from, to, ts, status, resolvedTs }` where `id` is the index of the message in `messages` and `status` is `waiting`, `snapped`, or `dropped`. `snapshotSeq` counts snapshots so the renderer can tell a rebuild from incremental growth.

## createState()

What it does: returns an empty state.

Inputs: none.

Output: `{ sessions: new Map(), messages: [], threads: [], lastEventTs: null, snapshotSeq: 0 }`.

Errors: none.

Example:

```js
createState().sessions.size // 0
```

## applySnapshot(state, snapshot)

What it does: discards current sessions, messages, and threads, increments `snapshotSeq`, and rebuilds from a server snapshot. Snapshot messages with `notify_on_idle` create threads too, so a page that connects mid-wait still shows the thread.

Inputs:
- `state` (object): the state to overwrite in place.
- `snapshot` (object): `{ sessions: [...], messages: [...] }` per `docs/overview.md`. Missing arrays are treated as empty. `null` snapshot is treated as empty.

Output: the same `state` object, mutated.

Errors: none. Malformed entries (session without numeric `pid`, message without string `from` and `to`) are skipped.

Example:

```js
const state = createState();
applySnapshot(state, {
  sessions: [{ ts: "2026-10-05T21:40:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: null }],
  messages: [{ ts: "2026-10-05T21:40:05Z", type: "message", from: "listings-bc", to: "tag-analyzer-63", text: "L16 is ready", notify_on_idle: true }]
});
state.sessions.get(29904).state // "idle"
state.messages.length           // 1
state.threads                   // [{ id: 0, from: "listings-bc", to: "tag-analyzer-63", ts: "2026-10-05T21:40:05Z", status: "waiting", resolvedTs: null }]
state.snapshotSeq               // 1
state.lastEventTs               // "2026-10-05T21:40:05Z"
```

## applyEvent(state, eventName, data)

What it does: routes one incremental SSE event to the matching reducer.

Inputs:
- `state` (object).
- `eventName` (string): `"session"`, `"liveness"` (both handled as session events), or `"message"`. Anything else is ignored.
- `data` (object): the parsed event payload.

Output: the same `state`, mutated.

Errors: none.

Example:

```js
applyEvent(state, "liveness", { ts: "2026-10-05T21:46:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "ended", role: null });
state.sessions.get(29904).state // "ended"
```

## applySessionEvent(state, event)

What it does: upserts the session with `event.pid`. Fields that are `null` or missing in the event keep the previously known value, so a later event with `session: null` does not erase a known name. `firstSeen` is the `ts` of the first event for that PID. Before storing, it resolves threads addressed to this session's name: an `idle` event marks every waiting thread to that name `snapped`, an `ended` event marks them `dropped`, and `busy`, `waiting`, or `started` leave them waiting. At most 50 finished threads are kept; older finished ones are pruned.

Inputs:
- `state` (object).
- `event` (object): a `session` event. Requires numeric `pid`; otherwise the event is ignored.

Output: the same `state`.

Errors: none.

Example:

```js
applySessionEvent(state, { ts: "2026-10-05T21:43:00Z", type: "session", session: null, folder: "scratch", pid: 30444, state: "started", role: null });
applySessionEvent(state, { ts: "2026-10-05T21:45:00Z", type: "session", session: "scratch-7a", folder: "scratch", pid: 30444, state: "idle", role: null });
state.sessions.get(30444) // { pid: 30444, session: "scratch-7a", folder: "scratch", role: null, state: "idle", ts: "2026-10-05T21:45:00Z", firstSeen: "2026-10-05T21:43:00Z" }
```

Thread resolution, with `frontend/fixtures/messages.json` applied and its events replayed in order through `applyEvent`:

```js
// after event 1 (message path-finder-18 → path-finder-e5, notify_on_idle)
state.threads.map(t => `${t.id}:${t.to}:${t.status}`) // ["1:path-finder-e5:waiting"]
// after event 2 (path-finder-e5 busy): unchanged, still waiting
// after event 5 (path-finder-e5 idle)
state.threads.map(t => `${t.id}:${t.to}:${t.status}`) // ["1:path-finder-e5:snapped"]
// after all 9 events
state.threads.map(t => `${t.id}:${t.to}:${t.status}`) // ["1:path-finder-e5:snapped", "4:nobody-99:waiting", "5:listings-bc:dropped"]
```

## applyMessageEvent(state, event)

What it does: appends a message to `state.messages`, oldest first. When `notify_on_idle` is true it also appends a `waiting` thread whose `id` is the message index.

Inputs:
- `state` (object).
- `event` (object): a `message` event. Requires string `from` and `to`; otherwise ignored. Missing `text` becomes `""`, missing `notify_on_idle` becomes `false`.

Output: the same `state`.

Errors: none.

Example:

```js
applyMessageEvent(state, { ts: "2026-10-05T21:44:05Z", type: "message", from: "path-finder-e5", to: "path-finder-18", text: "F1 spec updated" });
state.messages.at(-1) // { ts: "2026-10-05T21:44:05Z", from: "path-finder-e5", to: "path-finder-18", text: "F1 spec updated", notify_on_idle: false }
```

## waitingThreads(state)

What it does: returns the threads whose recipient has not yet gone idle or ended.

Inputs: `state` (object).

Output: `Thread[]`, in creation order.

Errors: none.

Example, after all events of `messages.json`:

```js
waitingThreads(state).map(t => t.to) // ["nobody-99"]
```

## liveSessions(state)

What it does: returns sessions in state `started`, `busy`, `waiting`, or `idle`, sorted by folder then label. Ended sessions are excluded.

Inputs: `state` (object).

Output: `Session[]`.

Errors: none.

Example, with the `frontend/fixtures/few.json` snapshot loaded:

```js
liveSessions(state).map(sessionLabel)
// ["listings-bc", "path-finder-18", "path-finder-e5", "pid 30444", "tag-analyzer-63"]
```

## sessionByName(state, name)

What it does: finds the session whose display name equals `name`.

Inputs: `state` (object), `name` (string).

Output: the `Session`, or `undefined`.

Errors: none.

Example:

```js
sessionByName(state, "scratch-7a")?.pid // 30444
sessionByName(state, "nobody")          // undefined
```

## sessionLabel(session)

What it does: returns the text drawn next to a body.

Inputs: `session` (Session).

Output: the display name, or `"pid <pid>"` while the name is still unknown.

Errors: none.

Example:

```js
sessionLabel({ pid: 30444, session: null })        // "pid 30444"
sessionLabel({ pid: 30444, session: "scratch-7a" }) // "scratch-7a"
```
