# connect.js

Feeds the page from the server's SSE stream, or from a local fixture when the server is not there.

## connect({ onSnapshot, onEvent, onStatus, fixtureUrl })

What it does: if the URL has `?fixture=<name>`, loads `./fixtures/<name>.json` and returns. Otherwise opens `EventSource("/events")`. The `snapshot` event goes to `onSnapshot`, and `session`, `message`, and `liveness` events go to `onEvent` with their name. If the stream errors before it ever opened (the endpoint is missing, as with a plain static server), the source is closed and `fixtureUrl` is loaded instead. If it errors after opening, the browser's automatic reconnect is left alone and `onStatus("reconnecting")` is reported.

Inputs:
- `onSnapshot` (function(snapshot)): called once per snapshot.
- `onEvent` (function(name, data)): called per incremental event. `data` is `null` when the payload is not valid JSON.
- `onStatus` (function(status), optional): receives `"live"`, `"reconnecting"`, `"fixture"`, or `"offline"`.
- `fixtureUrl` (string, default `"./fixtures/empty.json"`): fallback fixture.

Output: a function that closes the stream or cancels pending fixture timers.

Errors: none thrown. Network failures surface as `onStatus("offline")` followed by an empty snapshot.

Example, served by `python3 -m http.server` where `/events` is 404:

```js
connect({ onSnapshot: s => console.log("snapshot", s.sessions.length), onStatus: console.log });
// logs: "fixture" then "snapshot 0"
```

## loadFixture(url, { onSnapshot, onEvent, onStatus })

What it does: fetches a fixture file, reports `"fixture"`, delivers `fixture.snapshot`, then schedules each entry of `fixture.events` with `setTimeout`, accumulating `delayMs`. On any failure it reports `"offline"` and delivers an empty snapshot so the page still renders the empty board.

Inputs:
- `url` (string): fixture path.
- callbacks as for `connect`.

Output: a promise resolving to a cancel function that clears the pending timers.

Errors: none thrown; fetch and JSON errors are caught.

Example, with `frontend/fixtures/few.json`:

```js
const events = [];
await loadFixture("./fixtures/few.json", { onSnapshot: s => events.push(["snapshot", s.sessions.length]), onEvent: (n, d) => events.push([n, d.pid ?? d.from]) });
// immediately: events = [["snapshot", 5]]
// after 1.5s:  ["session", 29904]
// after 3.0s:  ["message", "path-finder-e5"]
// after 5.0s:  ["session", 30444]
// after 7.0s:  ["liveness", 30111]
```
