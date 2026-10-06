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

## findSessionByName(state, name)

What it does: looks a session up by display name, preferring one that has not ended.

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

Output: `{sessions, messages}`. `sessions` is an array of the stored session objects sorted by `ts` ascending; `messages` is a copy of the retained messages, oldest first.

Errors: none.

Example, continuing from the state above:

```js
snapshot(state)
// {"sessions":[{"ts":"2026-10-05T21:40:02Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"idle","role":null}],"messages":[{"ts":"2026-10-05T21:41:01Z","type":"message","from":"a","to":"b","text":"m1","notify_on_idle":false},{"ts":"2026-10-05T21:41:02Z","type":"message","from":"a","to":"b","text":"m2","notify_on_idle":false}]}
```
