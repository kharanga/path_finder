# liveness.js

Detects sessions that died without `SessionEnd` and corrects hook state from Claude Code's session registry. The server runs both checks on one interval. Every function takes its I/O as an injectable argument so tests need no real processes or files.

## SOCKET_DIR

Constant `"/tmp/cc-socks"`. Undocumented Claude Code internal, used only by `hasSocket`.

## DEFAULT_SESSIONS_DIR

Constant `~/.claude/sessions`. Undocumented Claude Code internal holding one `<pid>.json` per live session with `sessionId`, `name`, `cwd`, `status`, `statusUpdatedAt`.

## isPidAlive(pid)

What it does: sends signal 0 to the process.

Inputs: `pid` (integer).

Output: `true` when the process exists (including when it belongs to another user, `EPERM`), `false` otherwise.

Errors: none thrown.

Example:

```js
import { isPidAlive } from "./webhook/liveness.js";
isPidAlive(process.pid) // true
isPidAlive(2147483646)  // false
```

## hasSocket(pid, socketDir = SOCKET_DIR)

What it does: checks whether `<socketDir>/<pid>.sock` exists. Secondary hint only; the server does not use it for decisions.

Inputs: `pid` (integer); `socketDir` (string).

Output: boolean.

Errors: none thrown.

Example: `hasSocket(1, "/tmp/definitely-missing-dir")` is `false`.

## readRegistryStatus(pid, sessionsDir = DEFAULT_SESSIONS_DIR)

What it does: reads `<sessionsDir>/<pid>.json`.

Inputs: `pid` (integer); `sessionsDir` (string).

Output: `{status, name, statusUpdatedAt}` where `status` is a string or null, `name` a string or null, `statusUpdatedAt` a millisecond epoch number or null. Returns `null` when the file is missing or not JSON.

Errors: none thrown.

Example:

```js
import { writeFileSync, mkdirSync } from "node:fs";
import { readRegistryStatus } from "./webhook/liveness.js";
mkdirSync("/tmp/registry-example", { recursive: true });
writeFileSync("/tmp/registry-example/4242.json", '{"pid":4242,"name":"listings-bc","status":"busy","statusUpdatedAt":1791266113437}');
readRegistryStatus(4242, "/tmp/registry-example") // {"status":"busy","name":"listings-bc","statusUpdatedAt":1791266113437}
readRegistryStatus(1, "/tmp/registry-example")    // null
```

## findDeadSessions(state, now = new Date(), isAlive = isPidAlive)

What it does: returns a synthetic `ended` event for every session that is neither `ended` nor `removed` and whose PID is not alive.

Inputs:

- `state`: from `state.js`.
- `now` (Date): timestamp for the synthetic events.
- `isAlive` (function(pid) → boolean): liveness check, injectable.

Output: array of session events, copies of the stored sessions with `state: "ended"` and `ts: now.toISOString()`. Nothing is applied to the state; the caller does that.

Errors: none thrown.

Example:

```js
import { createState, applyEvent } from "./webhook/state.js";
import { findDeadSessions } from "./webhook/liveness.js";
const state = createState();
applyEvent(state, { ts: "2026-10-05T21:40:02Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: null });
const now = new Date("2026-10-05T21:45:00Z");
findDeadSessions(state, now, () => false)
// [{"ts":"2026-10-05T21:45:00.000Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"ended","role":null}]
findDeadSessions(state, now, () => true) // []
```

## findStatusCorrections(state, now = new Date(), readStatus = readRegistryStatus)

What it does: for every session that is neither `ended` nor `removed`, reads the registry entry. When the registry's `statusUpdatedAt` is newer than the session's last hook event `ts` and its `status` is a legal non-ended state different from the hook state, returns a corrective copy with the registry state. Independently, when the stored name is null and the registry has one, the copy carries that name. Registry entries older than the hook event are ignored, which protects against stale files.

Inputs:

- `state`: from `state.js`.
- `now` (Date): timestamp for the corrective events.
- `readStatus` (function(pid) → `{status, name, statusUpdatedAt}` or null): injectable registry reader.

Output: array of corrective session events, not yet applied.

Errors: none thrown.

Example, continuing with the `state` and `now` from above:

```js
import { findStatusCorrections } from "./webhook/liveness.js";
findStatusCorrections(state, now, () => ({ status: "busy", name: "listings-bc", statusUpdatedAt: Date.parse("2026-10-05T21:44:00Z") }))
// [{"ts":"2026-10-05T21:45:00.000Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"busy","role":null}]
findStatusCorrections(state, now, () => ({ status: "busy", name: "listings-bc", statusUpdatedAt: Date.parse("2026-10-05T21:39:00Z") })) // [] (registry older than the hook event)
findStatusCorrections(state, now, () => ({ status: "idle", name: "listings-bc", statusUpdatedAt: Date.parse("2026-10-05T21:44:00Z") })) // [] (agrees)
findStatusCorrections(state, now, () => null) // [] (no registry entry)

const anonymous = createState();
applyEvent(anonymous, { ts: "2026-10-05T21:40:00Z", type: "session", session: null, folder: "x", pid: 5, state: "busy", role: null });
findStatusCorrections(anonymous, now, () => ({ status: "busy", name: "x-9f", statusUpdatedAt: null }))
// [{"ts":"2026-10-05T21:45:00.000Z","type":"session","session":"x-9f","folder":"x","pid":5,"state":"busy","role":null}]
```
