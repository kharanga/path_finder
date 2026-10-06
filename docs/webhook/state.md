# state.js

The in-memory reducer. Turns the event stream into the latest session per PID plus a capped list of recent messages, and produces the SSE snapshot. Used by the server and by the fake generator's snapshot fold. Pure: no I/O.

## DEFAULT_MESSAGE_LIMIT

Constant `500`, how many recent messages a state keeps.

## createState(messageLimit = DEFAULT_MESSAGE_LIMIT)

What it does: creates an empty state.

Inputs: `messageLimit` (positive integer).

Output: `{sessions: Map, messages: [], messageLimit}`. `sessions` is keyed by PID.

Errors: none.

Example:

```js
import { createState } from "./webhook/state.js";
const state = createState(2);
// state.sessions.size 0, state.messages [], state.messageLimit 2
```

## applyEvent(state, event)

What it does: mutates the state with one valid event. A `session` event replaces the entry for its PID, keeping the previous non-null `session` name, `folder`, and `role` when the new event carries null or empty values. A `message` event is appended and the list is trimmed from the front to `messageLimit`.

Inputs:

- `state`: from `createState`.
- `event`: a validated §3 event.

Output: the merged session object that is now stored, or the message event itself. This is what the server broadcasts.

Errors: none thrown. Invalid events are the caller's responsibility; the server filters them with `parseEventLine` first.

Example:

```js
import { createState, applyEvent } from "./webhook/state.js";
const state = createState(2);
applyEvent(state, { ts: "2026-10-05T21:40:00Z", type: "session", session: null, folder: "listings", pid: 29904, state: "started", role: null });
applyEvent(state, { ts: "2026-10-05T21:40:01Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "busy", role: null });
const stored = applyEvent(state, { ts: "2026-10-05T21:40:02Z", type: "session", session: null, folder: "listings", pid: 29904, state: "idle", role: null });
// stored {"ts":"2026-10-05T21:40:02Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"idle","role":null}
applyEvent(state, { ts: "2026-10-05T21:41:00Z", type: "message", from: "a", to: "b", text: "m0", notify_on_idle: false });
applyEvent(state, { ts: "2026-10-05T21:41:01Z", type: "message", from: "a", to: "b", text: "m1", notify_on_idle: false });
applyEvent(state, { ts: "2026-10-05T21:41:02Z", type: "message", from: "a", to: "b", text: "m2", notify_on_idle: false });
// state.messages.map((m) => m.text) ["m1", "m2"]
```

## isLive(session)

What it does: tells whether a session object is on the board.

Inputs: `session` (object with `state`).

Output: `false` for `ended` and `removed`, `true` for every other state.

Errors: none.

Example: `isLive({ state: "busy" })` is `true`; `isLive({ state: "removed" })` is `false`.

## liveSessions(state)

What it does: lists the sessions that are neither ended nor removed.

Inputs: `state`.

Output: array sorted by `ts` ascending.

Errors: none.

Example: with PID 1 `idle`, PID 2 `ended`, PID 3 `removed`, `liveSessions(state).map((s) => s.pid)` is `[1]`.

## findSessionByName(state, name)

What it does: looks a session up by display name, preferring a live one, then an ended one. Removed sessions are never returned.

Inputs: `state`; `name` (string).

Output: the session object, or `undefined`.

Errors: none.

Example, continuing from the state above:

```js
findSessionByName(state, "listings-bc").pid // 29904
findSessionByName(state, "nobody")          // undefined
```

## snapshot(state)

What it does: builds the payload for the SSE `snapshot` event.

Inputs: `state`.

Output: `{sessions, messages}`. `sessions` is an array of the stored session objects except those in state `removed`, sorted by `ts` ascending; `ended` sessions stay so the page can fade them. `messages` is a copy of the retained messages, oldest first.

A removed session stays in `state.sessions`, so any later event for its PID replaces the entry and it reappears in the next snapshot. With PID 1 `idle`, PID 2 `ended`, PID 3 `removed`, `snapshot(state).sessions.map((s) => s.pid)` is `[1, 2]`; after a `busy` event for PID 3 it is `[1, 2, 3]`.

Errors: none.

Example, continuing from the state above:

```js
snapshot(state)
// {"sessions":[{"ts":"2026-10-05T21:40:02Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"idle","role":null}],"messages":[{"ts":"2026-10-05T21:41:01Z","type":"message","from":"a","to":"b","text":"m1","notify_on_idle":false},{"ts":"2026-10-05T21:41:02Z","type":"message","from":"a","to":"b","text":"m2","notify_on_idle":false}]}
```
