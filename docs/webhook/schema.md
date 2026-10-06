# schema.js

Validation for the §3 event schema. Used by the server to drop malformed lines and by the fake generator to refuse to write an invalid event. The hook does not import it; the hook stays dependency-free so it starts fast.

## SESSION_STATES

Constant array `["started", "busy", "waiting", "idle", "ended", "removed"]`, the only legal values of `state`. `removed` is written by the server on `POST /sessions/<pid>/remove`, never by hooks.

## NOT_LIVE_STATES

Constant array `["ended", "removed"]`, the states that take a session off the board. Used by `state.js` and `liveness.js`.

## validateEvent(event)

What it does: checks one event against the schema, including unknown fields.

Inputs: `event` (any value).

Output: `{ok: boolean, errors: string[]}`. `errors` is empty when `ok` is true.

Errors: none thrown.

Example:

```js
validateEvent({ ts: "2026-10-05T21:40:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "started", role: null })
// { ok: true, errors: [] }

validateEvent({ ts: "2026-10-05T21:40:05Z", type: "message", from: "listings-bc", to: "tag-analyzer-63", text: "L16 is ready, look at it", notify_on_idle: true })
// { ok: true, errors: [] }

validateEvent({ ts: "bad", type: "session", session: 1, folder: "x", pid: 0, state: "sleeping", role: null, extra: 1 })
// { ok: false, errors: ["ts must be an ISO 8601 string", "session must be a string or null", "pid must be a positive integer", "state must be one of started, busy, waiting, idle, ended, removed", "unknown field extra"] }

validateEvent("nope")
// { ok: false, errors: ["event must be an object"] }
```

## parseEventLine(line)

What it does: parses one line of `events.jsonl` and validates it.

Inputs: `line` (string).

Output: the event object, or `null` for blank, non-JSON, or invalid lines.

Errors: none thrown.

Example:

```js
parseEventLine('{"ts":"2026-10-05T21:40:00Z","type":"session","session":null,"folder":"listings","pid":29904,"state":"busy","role":null}')
// { ts: "2026-10-05T21:40:00Z", type: "session", session: null, folder: "listings", pid: 29904, state: "busy", role: null }

parseEventLine("not json")   // null
parseEventLine("")           // null
parseEventLine('{"ts":"bad"}') // null
```
