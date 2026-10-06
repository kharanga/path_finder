# server.js

The dashboard server. Replays `events.jsonl`, tails it, keeps in-memory state through `state.js`, runs the liveness and registry checks from `liveness.js`, serves the page, and streams Server-Sent Events. Related modules have their own files: `tail.md`, `state.md`, `liveness.md`, `schema.md`.

Run: `node webhook/server.js [flags]`. Prints `dashboard at http://127.0.0.1:4747/`, the events file in use, a warning when the frontend directory has no `index.html`, and the replay count. Ctrl-C stops it cleanly.

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

What it does: serves `<frontend>/index.html`.

Inputs: none.

Output: 200 with `Content-Type: text/html; charset=utf-8` and `Cache-Control: no-store`.

Errors: 404 `frontend not found at <dir>` when the file is missing.

Example: `curl -s -o /dev/null -w '%{http_code} %{content_type}\n' http://127.0.0.1:4747/` prints `200 text/html; charset=utf-8`.

### GET /<path>

What it does: serves any other path as a static file under the frontend directory.

Inputs: the URL path, percent-encoded.

Output: 200 with the content type for `.html`, `.js`, `.mjs`, `.css`, `.json`, `.svg`, `.png`, `.ico`, `.woff2`, `.txt`, otherwise `application/octet-stream`. HEAD returns headers only.

Errors: 404 `not found` for paths that resolve outside the directory, directories, and missing files. 405 for methods other than GET and HEAD.

Example:

```
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' http://127.0.0.1:4747/orbit.css          # 200 text/css; charset=utf-8
curl -s -o /dev/null -w '%{http_code}\n' --path-as-is http://127.0.0.1:4747/../CLAUDE.md          # 404
curl -s -o /dev/null -w '%{http_code}\n' --path-as-is http://127.0.0.1:4747/%2e%2e/CLAUDE.md      # 404
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:4747/                           # 405
```

### GET /events

What it does: the SSE stream.

Inputs: none.

Output: `Content-Type: text/event-stream`, `Cache-Control: no-store`. A comment `: connected`, then `event: snapshot` with `{"sessions":[...],"messages":[...]}`, then `event: session`, `event: message`, and `event: liveness` frames as they happen, and a `: ping` comment every 15 seconds. Registry status corrections arrive as `event: session`.

Errors: none; the connection simply closes when the server stops.

Example, with a file holding one `started` line for PID 29904:

```
curl -s -N -m 1 http://127.0.0.1:4747/events
: connected

event: snapshot
data: {"sessions":[{"ts":"2026-10-05T21:40:00Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"started","role":null}],"messages":[]}
```

### POST /sessions/<pid>/remove

What it does: removes a session from the board. Appends a `session` event with state `removed` carrying the PID's current name, folder, and role to the events file, applies it, and broadcasts it as `event: session` exactly once (the tailer recognizes the line it just wrote and does not broadcast it again).

Inputs: `pid` in the path, decimal integer.

Output: 204 with no body.

Errors: 404 `unknown pid` when no event for that PID has been seen; 405 with `Allow: POST` for other methods on this path.

Example, with PID 29904 known:

```
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:4747/sessions/29904/remove   # 204
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:4747/sessions/4242/remove    # 404
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:4747/sessions/29904/remove           # 405
```

After the first call `/snapshot` no longer lists 29904, the last line of the events file is the `removed` event, and a server restarted on that file still omits it. Any later event for 29904 (a hook writing `busy`, say) brings it back.

### GET /snapshot

What it does: debug view of the current state. In the contract since W5.

Inputs: none.

Output: 200 JSON `{sessions, messages, stats}` where `stats` is `{linesRead, malformedLines, eventsApplied, livenessEnded, statusCorrections, removals}`.

Errors: none.

Example: right after starting on a file with two valid lines and two malformed ones, `curl -s http://127.0.0.1:4747/snapshot | python3 -c "import json,sys; print(json.load(sys.stdin)['stats'])"` prints `{'linesRead': 4, 'malformedLines': 2, 'eventsApplied': 2, 'livenessEnded': 0, 'statusCorrections': 0, 'removals': 0}` (with the liveness interval disabled or both PIDs alive).

## DEFAULTS

Constant object with the defaults in the flag table plus `heartbeatMs: 15000` and `messageLimit: 500`.

## CONTENT_TYPES

Constant map from lowercase extension to content type, the ten entries listed under `GET /<path>`.

## parseArgs(argv, defaults = DEFAULTS)

What it does: turns CLI flags into an options object.

Inputs: `argv` (string[]) without the node and script entries; `defaults` (object) to start from.

Output: a copy of `defaults` with `eventsPath`, `frontendDir`, `sessionsDir`, `port`, `host`, `livenessIntervalMs`, `pollMs`, `demo` overridden by the flags present.

Errors: throws `Error("unknown flag <flag>")`, `Error("<flag> needs a non-negative number")` for `--port`, `--liveness-interval`, `--poll` without a usable value, and `Error("<flag> needs a value")` for a path or host flag without one.

Example:

```js
import { parseArgs } from "./webhook/server.js";
parseArgs(["--events", "/tmp/e", "--port", "5000", "--liveness-interval", "0", "--demo"], { port: 1, demo: false })
// {"port":5000,"demo":true,"eventsPath":"/tmp/e","livenessIntervalMs":0}
parseArgs(["--bogus"]) // throws Error: unknown flag --bogus
parseArgs(["--port"])  // throws Error: --port needs a non-negative number
```

## sseFrame(eventName, payload)

What it does: formats one SSE frame.

Inputs: `eventName` (string); `payload` (any JSON value).

Output: the string `event: <name>\ndata: <json>\n\n`.

Errors: none.

Example: `sseFrame("session", { a: 1 })` is `"event: session\ndata: {\"a\":1}\n\n"`.

## resolveStaticFile(frontendDir, urlPath)

What it does: maps a URL path to a regular file inside the frontend directory and picks its content type.

Inputs: `frontendDir` (string); `urlPath` (string, the percent-encoded URL pathname, `/` means `index.html`).

Output: `{filePath, contentType}` or `null`.

Errors: none thrown. Traversal outside the directory, directories, missing files, undecodable paths, and symlinks inside the directory that point outside it all give `null`. The returned `filePath` is the real path.

Example, with the repo's `frontend/` as `dir`:

```js
import { resolveStaticFile } from "./webhook/server.js";
resolveStaticFile(dir, "/").contentType               // "text/html; charset=utf-8"
resolveStaticFile(dir, "/").filePath.endsWith("/frontend/index.html") // true
resolveStaticFile(dir, "/app.js").contentType         // "text/javascript; charset=utf-8"
resolveStaticFile(dir, "/orbit.css").contentType      // "text/css; charset=utf-8"
resolveStaticFile(dir, "/fixtures/few.json").contentType // "application/json; charset=utf-8"
resolveStaticFile(dir, "/../CLAUDE.md")               // null
resolveStaticFile(dir, "/%2e%2e/CLAUDE.md")           // null
resolveStaticFile(dir, "/fixtures")                   // null (directory)
resolveStaticFile(dir, "/nope.js")                    // null
resolveStaticFile(dir, "/%E0%A4%A")                   // null (bad encoding)
// with `ln -s /etc/hosts <dir>/escape.txt`: resolveStaticFile(dir, "/escape.txt") is null
```

## createHub(options = {})

What it does: builds the in-memory core shared by the tailer, the liveness timer, and HTTP clients.

Inputs: `options` (object): `messageLimit` (number), `sessionsDir` (string), and for tests `isAlive(pid)` and `readStatus(pid)` replacing the real checks.

Output: `{state, clients, stats, ingestLine, runLivenessCheck, addClient, broadcast}`.

- `ingestLine(line, {replaying = false})`: parses and applies one line, returns the applied event or `null` when malformed, broadcasts unless replaying. A line that `removeSession` wrote moments ago is recognized and returns the stored session without applying or broadcasting again.
- `removeSession(pid, now = new Date())`: appends, applies, and broadcasts a `removed` event for a known PID and returns it; returns `null` for an unknown PID and writes nothing.
- `runLivenessCheck(now = new Date())`: applies and broadcasts dead-PID `ended` events as `liveness` and registry corrections as `session`; returns `{ended, corrections}`.
- `addClient(response)`: registers an object with `write(string)`, writes the snapshot frame immediately, returns a function that removes the client.
- `broadcast(eventName, payload)`: writes one frame to every client.
- `stats`: `{linesRead, malformedLines, eventsApplied, livenessEnded, statusCorrections, removals}`.

Errors: none thrown.

Example:

```js
import { createHub } from "./webhook/server.js";
const hub = createHub({ isAlive: () => true, readStatus: () => null });
hub.ingestLine('{"ts":"2026-10-05T21:40:00Z","type":"session","session":"a-1","folder":"a","pid":1,"state":"busy","role":null}').state // "busy"
hub.ingestLine("not json") // null
hub.ingestLine("")         // null, blank lines are not counted as malformed
hub.stats                  // {"linesRead":3,"malformedLines":1,"eventsApplied":1,"livenessEnded":0,"statusCorrections":0,"removals":0}
hub.removeSession(99)      // null, unknown pid
const frames = [];
const remove = hub.addClient({ write: (frame) => frames.push(frame) });
hub.ingestLine('{"ts":"2026-10-05T21:40:05Z","type":"message","from":"a-1","to":"b","text":"hi","notify_on_idle":true}');
frames.map((frame) => frame.split("\n")[0]) // ["event: snapshot", "event: message"]
remove();
hub.runLivenessCheck(new Date("2026-10-05T21:45:00Z")) // {"ended":[],"corrections":[]} because isAlive is always true
```

## handleRequest(hub, options, request, response)

What it does: the HTTP handler behind the endpoints above.

Inputs: `hub` from `createHub`; `options` with `frontendDir` and `heartbeatMs`; Node `IncomingMessage` and `ServerResponse`.

Output: none, writes the response.

Errors: none thrown; bad paths become 404, bad methods 405.

Example: see Endpoints.

## startDemoGenerator(extraArgs = [])

What it does: spawns `fake.js --out <tempdir>/events.jsonl` as a child with placeholder processes.

Inputs: `extraArgs` (string[]) appended to the generator command line.

Output: `{eventsPath, child}`.

Errors: none thrown; a failing child simply writes nothing.

Example: `node webhook/server.js --demo` prints an events file under the OS temp dir and within twelve seconds `/snapshot` lists at least two sessions. Ctrl-C leaves no `sleep 86400` processes behind.

## startServer(overrides = {})

What it does: wires everything together: replay, tail, liveness timer, HTTP listener.

Inputs: `overrides` (object) merged over `DEFAULTS`. `port: 0` picks a free port, readable from `server.address().port`.

Output: Promise of `{server, hub, options, stop}`. `stop()` returns a Promise that stops tailing, clears the timer, ends SSE clients, kills the demo child, and closes the listener.

Errors: rejects with the listen error, for example `EADDRINUSE`.

Example:

```js
import { writeFileSync } from "node:fs";
import { startServer } from "./webhook/server.js";
writeFileSync("/tmp/server-example.jsonl", '{"ts":"2026-10-05T21:40:00Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"started","role":null}\nnot json\n');
const { server, hub, stop } = await startServer({ eventsPath: "/tmp/server-example.jsonl", port: 0, livenessIntervalMs: 0 });
const port = server.address().port;
const stats = await fetch(`http://127.0.0.1:${port}/snapshot`).then((r) => r.json()).then((d) => d.stats);
// stats {"linesRead":2,"malformedLines":1,"eventsApplied":1,"livenessEnded":0,"statusCorrections":0,"removals":0}
// hub.state.sessions.get(29904).state "started"
await stop();
```
