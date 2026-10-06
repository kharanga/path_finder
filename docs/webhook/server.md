# server.js, tail.js, state.js, liveness.js

The dashboard server. Replays `events.jsonl`, tails it, keeps in-memory state, checks liveness, serves the page, and streams Server-Sent Events.

Run: `node webhook/server.js [flags]`. Prints `dashboard at http://127.0.0.1:4747/`, the events file in use, and the replay count. Ctrl-C stops it cleanly.

| Flag | Default | Meaning |
|---|---|---|
| `--events <path>` | `~/.claude/dashboard/events.jsonl` | file to replay and tail |
| `--frontend <dir>` | `frontend/` next to `webhook/` | static root, `index.html` served at `/` |
| `--sessions-dir <dir>` | `~/.claude/sessions` | Claude Code session registry used for status corrections |
| `--port <n>` | 4747 | |
| `--host <addr>` | 127.0.0.1 | never bind wider; nothing leaves the machine |
| `--liveness-interval <ms>` | 5000 | 0 disables the PID check and the registry poll, use with fixtures whose PIDs are fake |
| `--poll <ms>` | 300 | how often the events file is checked for new bytes |
| `--demo` | off | start `fake.js` on a temp file and tail that instead |

## Endpoints

### GET /

Serves `frontend/index.html` with `text/html; charset=utf-8`. 404 with `frontend not found at <dir>` when the file is missing.

### GET /<path>

Any other path is a static file under the frontend directory. Content types: `.html`, `.js`, `.mjs`, `.css`, `.json`, `.svg`, `.png`, `.ico`, `.woff2`, `.txt`; anything else is `application/octet-stream`. Paths that resolve outside the directory, directories, and missing files return 404 `not found`. Methods other than GET and HEAD return 405.

Example: `curl -i http://127.0.0.1:4747/orbit.css` gives `200` with `Content-Type: text/css; charset=utf-8`; `curl --path-as-is -i http://127.0.0.1:4747/../CLAUDE.md` gives `404`.

### GET /events

SSE stream. Headers `text/event-stream`, `Cache-Control: no-store`. The first frame is a comment `: connected`, then `event: snapshot` with `{"sessions":[...],"messages":[...]}`, then `event: session`, `event: message`, and `event: liveness` frames as they happen, plus a `: ping` comment every 15 seconds. Registry status corrections arrive as `event: session`.

Example, with a file holding one `started` line for PID 29904:

```
curl -s -N -m 1 http://127.0.0.1:4747/events
: connected

event: snapshot
data: {"sessions":[{"ts":"2026-10-05T21:40:00Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"started","role":null}],"messages":[]}
```

### GET /snapshot

Debug helper, not part of the page contract. Returns the snapshot plus `stats: {linesRead, malformedLines, eventsApplied, livenessEnded, statusCorrections}` as JSON.

## server.js functions

### parseArgs(argv, defaults = DEFAULTS)

What it does: turns the flags above into an options object.

Inputs: `argv` (string[]); `defaults` (object).

Output: `{eventsPath, frontendDir, sessionsDir, port, host, livenessIntervalMs, pollMs, heartbeatMs, messageLimit, demo}`.

Errors: throws `Error("unknown flag <flag>")`.

Example: `parseArgs(["--events", "/tmp/e", "--port", "5000", "--liveness-interval", "0", "--demo"], { port: 1, demo: false })` returns `{"port":5000,"demo":true,"eventsPath":"/tmp/e","livenessIntervalMs":0}`.

### sseFrame(eventName, payload)

What it does: formats one SSE frame.

Inputs: `eventName` (string); `payload` (JSON value).

Output: string `event: <name>\ndata: <json>\n\n`.

Errors: none.

Example: `sseFrame("session", { a: 1 })` is `"event: session\ndata: {\"a\":1}\n\n"`.

### resolveStaticFile(frontendDir, urlPath)

What it does: maps a URL path to a regular file inside the frontend directory.

Inputs: `frontendDir` (string); `urlPath` (string, the URL pathname, percent-encoded).

Output: `{filePath, contentType}` or `null` for traversal, directories, missing files, or undecodable paths.

Errors: none thrown.

Example: with the repo's `frontend/`, `resolveStaticFile(dir, "/")` gives `index.html` as `text/html; charset=utf-8`; `"/app.js"` gives `text/javascript; charset=utf-8`; `"/../CLAUDE.md"`, `"/%2e%2e/CLAUDE.md"`, `"/fixtures"` (a directory), and `"/nope.js"` all give `null`.

### createHub(options = {})

What it does: builds the in-memory core shared by the tailer, the liveness timer, and HTTP clients. `options.isAlive(pid)` and `options.readStatus(pid)` override the real checks for tests; `options.sessionsDir` sets the registry directory; `options.messageLimit` caps retained messages.

Inputs: `options` (object).

Output: `{state, clients, stats, ingestLine(line, {replaying}), runLivenessCheck(now), addClient(response), broadcast(eventName, payload)}`. `ingestLine` returns the applied event or `null` for a malformed line and broadcasts unless replaying. `runLivenessCheck` returns `{ended, corrections}` after applying and broadcasting them. `addClient` writes the snapshot immediately and returns a remover.

Errors: none thrown.

Example:

```js
const hub = createHub({ isAlive: () => true, readStatus: () => null });
hub.ingestLine('{"ts":"2026-10-05T21:40:00Z","type":"session","session":"a-1","folder":"a","pid":1,"state":"busy","role":null}').state // "busy"
hub.ingestLine("not json") // null
hub.stats // { linesRead: 2, malformedLines: 1, eventsApplied: 1, livenessEnded: 0, statusCorrections: 0 }
const frames = []; hub.addClient({ write: (f) => frames.push(f) });
hub.ingestLine('{"ts":"2026-10-05T21:40:05Z","type":"message","from":"a-1","to":"b","text":"hi","notify_on_idle":true}');
frames.map((f) => f.split("\n")[0]) // ["event: snapshot", "event: message"]
```

### handleRequest(hub, options, request, response)

What it does: the HTTP handler behind the endpoints above.

Inputs: `hub` from `createHub`; `options` with `frontendDir` and `heartbeatMs`; Node `request` and `response`.

Output: none, writes the response.

Errors: none thrown; bad paths become 404, bad methods 405.

Example: see Endpoints.

### startDemoGenerator(extraArgs = [])

What it does: spawns `fake.js --out <temp>/events.jsonl` with placeholder processes.

Inputs: `extraArgs` (string[]) appended to the generator command.

Output: `{eventsPath, child}`.

Errors: none thrown; a failing child simply writes nothing.

Example: `node webhook/server.js --demo` prints an events file under the OS temp dir and within ten seconds `/snapshot` lists several sessions.

### startServer(overrides = {})

What it does: wires everything: replay, tail, liveness timer, HTTP listener.

Inputs: `overrides` (object) merged over `DEFAULTS`.

Output: Promise of `{server, hub, options, stop}`. `stop()` returns a Promise that stops tailing, clears the timer, ends SSE clients, kills the demo child, and closes the server.

Errors: rejects when the port is in use (`EADDRINUSE`).

Example: `const { stop } = await startServer({ eventsPath: "/tmp/e.jsonl", port: 0, livenessIntervalMs: 0 }); await stop();`

## tail.js

### readNewLines(filePath, offset, carry = "")

What it does: reads bytes appended after `offset`, splits complete lines, keeps the partial tail.

Inputs: `filePath` (string); `offset` (integer bytes already consumed); `carry` (string, unfinished line from last call).

Output: `{lines, offset, carry, truncated, missing}`. `truncated` is true when the file shrank (then reading restarts at 0); `missing` is true when the file does not exist.

Errors: none thrown.

Example: a file with `a\nb\npartial` gives `lines ["a","b"]`, `carry "partial"`, `offset 11`. After appending `-done\nc\n`, the next call gives `lines ["partial-done","c"]`, empty carry. Rewriting the file as `z\n` gives `lines ["z"]`, `truncated true`.

### tailFile(filePath, onLine, options = {})

What it does: calls `readNewLines` immediately (replay) and then every `options.pollMs` (default 300). `options.onReplayComplete` fires after the first pass; `options.onTruncate` on shrink; `options.fromStart: false` skips existing content.

Inputs: `filePath` (string); `onLine(line)` (function); `options` (object).

Output: a function that stops the tail.

Errors: none thrown; a missing file is polled until it appears.

Example: `const stop = tailFile("/tmp/e.jsonl", console.log); stop();`

## state.js

### createState(messageLimit = 500)

Output: `{sessions: Map<pid, session>, messages: [], messageLimit}`.

### applyEvent(state, event)

What it does: merges a `session` event into the entry for its PID, keeping an earlier non-null `session` name and `role` when the new event has null, or appends a `message` and trims to `messageLimit`.

Output: the merged session object, or the message.

Example: after `started` with `session: null`, then `busy` with `session: "listings-bc"`, then `idle` with `session: null`, the stored session is `{"session":"listings-bc","state":"idle",...}`. With `messageLimit 2` and three messages `m0, m1, m2`, the snapshot holds `["m1","m2"]`.

### findSessionByName(state, name)

Output: the non-ended session with that name, else any session with that name, else `undefined`.

### snapshot(state)

Output: `{sessions: [...sorted by ts], messages: [...]}`.

## liveness.js

### isPidAlive(pid)

Output: boolean, `process.kill(pid, 0)` with `EPERM` counted alive.

### hasSocket(pid, socketDir = "/tmp/cc-socks")

Output: boolean, secondary hint only.

### readRegistryStatus(pid, sessionsDir = ~/.claude/sessions)

Output: `{status, name, statusUpdatedAt}` from `<pid>.json`, or `null` when missing or malformed.

### findDeadSessions(state, now = new Date(), isAlive = isPidAlive)

Output: array of copies of non-ended sessions whose PID is dead, with `state: "ended"` and `ts: now`.

Example: a state with PID 29904 idle and `isAlive = () => false` gives `[{pid: 29904, state: "ended", ts: "2026-10-05T21:45:00.000Z", ...}]`; with `() => true` it gives `[]`.

### findStatusCorrections(state, now = new Date(), readStatus = readRegistryStatus)

What it does: for each non-ended session, reads the registry; when `statusUpdatedAt` is newer than the session's last hook event and `status` is a legal non-ended state that differs, returns a corrective copy with that state. Also fills a `null` name from the registry.

Output: array of corrective session events.

Example: session idle at 21:40:02, registry `{status: "busy", statusUpdatedAt: 21:44}` gives one correction with `state: "busy"`. Registry at 21:39 (older) gives `[]`. Registry agreeing (`idle`) gives `[]`. A session with `session: null` and registry `name: "x-9f"` gives one correction carrying the name and the unchanged state.
