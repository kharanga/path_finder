# hooks

Scripts in `webhook/hooks/` that Claude Code runs from `~/.claude/settings.json`. Every script reads one JSON object from stdin, writes nothing to stdout or stderr, and exits 0 no matter what happens.

## Raw hook input shape

Claude Code pipes one JSON object to every hook command. Confirmed from the W1 raw log on Claude Code 2.1.291. Fields common to every event:

| Field | Type | Meaning |
|---|---|---|
| `session_id` | string, 36 chars | UUID of the session, same as the transcript file name |
| `transcript_path` | string | path of the session transcript |
| `cwd` | string | folder the session started in |
| `scratchpad_dir` | string | the session's scratch directory |
| `prompt_id` | string, 36 chars | UUID of the current turn |
| `hook_event_name` | string | `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `Notification`, `SessionEnd`, ... |

Event-specific fields:

| Event | Extra fields |
|---|---|
| `SessionStart` | `source`: `startup`, `resume`, `clear`, or `compact` (from the Claude Code docs; not yet observed in the raw log) |
| `UserPromptSubmit` | `permission_mode`, `prompt` |
| `PreToolUse` / `PostToolUse` | `tool_name`, `tool_input`, `tool_response` (post only) |
| `Stop` | `permission_mode`, `effort.level`, `stop_hook_active` (boolean), `last_assistant_message`, `background_tasks` (array), `session_crons` (array) |
| `Notification` | `message`, `notification_type` |
| `SessionEnd` | `reason` (from the Claude Code docs; not yet observed) |

For `tool_name` `SendMessage`, `tool_input` mirrors the tool's parameters: `to` (string), `message` (string), `notify_when_idle` (boolean, optional), `summary` (string, optional). Observed: `{"to":"path-finder-e5","notify_when_idle":true}` kept, with `message` of length 145 and `summary` of length 32 redacted.

Timing facts that shape the real hook: `UserPromptSubmit` fires when a cross-session message is delivered, even mid-turn, so repeated `busy` events are normal. `Stop` fires at every completed turn end but not on user interrupt. Settings changes to hooks applied to running sessions without a restart.

## Mapping a hook to its session

The hook process is a child of `sh`, which is a child of the `claude` process. Walking `ps -o ppid=,comm=` upward finds the session PID. Separately, Claude Code keeps `~/.claude/sessions/<pid>.json` with `sessionId`, `name` (the display name such as `listings-bc`), `cwd`, and `status`. Matching `session_id` against `sessionId` gives both the PID and the display name without a process walk. Both are undocumented internals; the process walk is the fallback.

## dashboard-hook.js

The real hook. One script handles every dashboard event: `SessionStart`, `UserPromptSubmit`, `Notification`, `Stop`, `SessionEnd`, and `PostToolUse` for `SendMessage`. Run as `node webhook/hooks/dashboard-hook.js` with the hook JSON on stdin. Appends one §3 event line to `$CC_DASHBOARD_EVENTS`, default `~/.claude/dashboard/events.jsonl`, creating the directory. Always exits 0 with no stdout or stderr. Measured at about 25 ms per invocation.

Hook to event mapping:

| Hook input | Event |
|---|---|
| `SessionStart` | `session` with state `started` |
| `UserPromptSubmit` | `session` with state `busy` |
| `Notification` with `notification_type` `permission_prompt` | `session` with state `waiting` |
| `Notification` with any other type | nothing |
| `Stop` | `session` with state `idle` |
| `SessionEnd` | `session` with state `ended` |
| `PostToolUse` with `tool_name` `SendMessage` | `message` |
| anything else | nothing |

`role` is always `null` until a role-declaring mechanism exists.

### stateForHook(hookInput)

What it does: returns the session state a hook input maps to.

Inputs: `hookInput` (object) parsed hook JSON with `hook_event_name` and, for `Notification`, `notification_type`.

Output: one of `started`, `busy`, `waiting`, `idle`, `ended`, or `null` when the hook carries no state change.

Errors: none.

Example:

```js
stateForHook({ hook_event_name: "Notification", notification_type: "permission_prompt" }) // "waiting"
stateForHook({ hook_event_name: "Notification", notification_type: "idle_prompt" })       // null
stateForHook({ hook_event_name: "PreToolUse" })                                            // null
```

### lookupSessionRegistry(sessionId, sessionsDir = ~/.claude/sessions)

What it does: scans Claude Code's session registry for the entry whose `sessionId` matches.

Inputs: `sessionId` (string) the hook's `session_id`; `sessionsDir` (string) directory of `<pid>.json` files.

Output: `{pid, name}` with `name` a string or `null`, or `null` when no file matches or the directory is unreadable.

Errors: none thrown. Unreadable or malformed files are skipped.

Example: with this session running, `lookupSessionRegistry("177234a7-b67a-4a0f-bacc-d346355dfd49")` returns `{"pid":52134,"name":"path-finder-37"}`. `lookupSessionRegistry("nope")` and `lookupSessionRegistry("x", "/nonexistent")` both return `null`.

### findClaudeAncestorPid(startPid = process.ppid, maxDepth = 6)

What it does: walks the process tree upward and returns the PID of the nearest process whose command is `claude`.

Inputs: `startPid` (integer); `maxDepth` (integer).

Output: integer PID or `null`.

Errors: none thrown. A failing `ps` returns `null`.

Example: called from any tool or hook under this session it returns `52134`.

### resolveSession(hookInput, options = {})

What it does: resolves `{pid, name}` for the hook, registry first, process walk second.

Inputs: `hookInput` (object) with `session_id`; `options.sessionsDir` (string, optional); `options.findPid` (function, optional, replaces the process walk in tests).

Output: `{pid, name}`. `name` is `null` when only the process walk succeeded. `pid` is `null` when both fail.

Errors: none thrown.

Example: `resolveSession({ session_id: "nope" }, { findPid: () => 4242 })` returns `{"pid":4242,"name":null}`.

### buildEvent(hookInput, identity, now = new Date())

What it does: converts hook input plus resolved identity into a §3 event.

Inputs: `hookInput` (object) parsed hook JSON; `identity` (`{pid, name}`); `now` (Date).

Output: a `session` event, a `message` event, or `null` when the hook is not logged or `identity.pid` is not an integer.

Errors: none thrown.

Example:

```js
buildEvent({ hook_event_name: "Stop", cwd: "/Users/k/listings" }, { pid: 29904, name: "listings-bc" }, new Date("2026-10-05T21:40:00Z"))
// {"ts":"2026-10-05T21:40:00.000Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"idle","role":null}

buildEvent({ hook_event_name: "PostToolUse", tool_name: "SendMessage", cwd: "/x", tool_input: { to: "tag-analyzer-63", message: "L16 is ready, look at it", notify_when_idle: true } }, { pid: 29904, name: "listings-bc" }, new Date("2026-10-05T21:40:05Z"))
// {"ts":"2026-10-05T21:40:05.000Z","type":"message","from":"listings-bc","to":"tag-analyzer-63","text":"L16 is ready, look at it","notify_on_idle":true}

buildEvent({ hook_event_name: "PostToolUse", tool_name: "Bash", cwd: "/x" }, { pid: 1, name: null }) // null
buildEvent({ hook_event_name: "Stop", cwd: "/x" }, { pid: null, name: null })                       // null
```

### appendEvent(eventsPath, event)

What it does: appends `JSON.stringify(event)` plus a newline, creating the parent directory.

Inputs: `eventsPath` (string); `event` (object).

Output: `true` on success, `false` on any failure.

Errors: none thrown.

Example: `appendEvent("/nonexistent-root/e.jsonl", { a: 1 })` returns `false`.

### readStdin()

Same as in `capture-raw.js` below.

### main()

What it does: reads stdin, resolves the session, builds the event, appends it. Swallows every error.

Inputs: hook JSON on stdin; `CC_DASHBOARD_EVENTS` environment variable optionally overrides the output path.

Output: none. Exit code is always 0, nothing on stdout or stderr.

Errors: none.

Example, run inside a Claude Code session so the registry lookup succeeds:

```
export CC_DASHBOARD_EVENTS=/tmp/hook-test/events.jsonl
echo '{"session_id":"<this session id>","hook_event_name":"Notification","cwd":"/Users/khangnguyen/Documents/path_finder","message":"x","notification_type":"permission_prompt"}' | node webhook/hooks/dashboard-hook.js; echo $?
echo 'garbage' | node webhook/hooks/dashboard-hook.js; echo $?
cat /tmp/hook-test/events.jsonl
```

Expected: `0`, `0`, and one line `{"ts":"...","type":"session","session":"path-finder-37","folder":"path_finder","pid":52134,"state":"waiting","role":null}` with the session name and PID of the session running the command. With an unknown `session_id` the line has `"session":null` and the PID of the enclosing `claude` process.

## capture-raw.js

Catch-all used in task W1 only. Appends one redacted record per hook invocation so the real hook can be written from observed shapes.

Run as: `node webhook/hooks/capture-raw.js [log-path]`. The log path defaults to `$CC_DASHBOARD_RAW_LOG`, then `/tmp/cc-dashboard-raw.jsonl`.

Privacy: prompt text, message text, tool responses, and every other value are replaced by their type and length. Only `session_id`, `hook_event_name`, `cwd`, `tool_name`, `source`, `reason`, `stop_hook_active`, `permission_mode`, and for `SendMessage` the `to` and `notify_when_idle` inputs are kept verbatim.

### ancestorChain(startPid = process.ppid, maxDepth = 6)

What it does: walks the process tree upward and returns the ancestors of the hook process.

Inputs: `startPid` (integer) first PID to inspect; `maxDepth` (integer) how many levels to climb.

Output: array of `{pid, ppid, command}` nearest first. Stops early at PID 1 or when `ps` fails.

Errors: none thrown. A failing `ps` ends the chain.

Example: run from a hook under session PID 52134.

```js
ancestorChain(54887)
// [{pid: 54887, ppid: 52134, command: "/bin/zsh"}, {pid: 52134, ppid: 51897, command: "claude"}, ...]
```

### readStdin()

What it does: reads all of stdin synchronously.

Inputs: none.

Output: string, `""` when stdin is a TTY or unreadable.

Errors: none thrown.

Example: `echo '{"a":1}' | node -e '...'` gives `'{"a":1}\n'`.

### describeShape(value)

What it does: replaces every value with a type description.

Inputs: `value` (any JSON value).

Output: `"null"`, `"boolean"`, `"number"`, `"string(<length>)"`, `["array(<length>)"]`, or an object with the same keys and described values.

Errors: none.

Example:

```js
describeShape({ prompt: "hello", tool_input: { to: "x", notify_when_idle: true } })
// { prompt: "string(5)", tool_input: { to: "string(1)", notify_when_idle: "boolean" } }
```

### redactHookInput(input)

What it does: keeps the identifying fields verbatim and the shape of everything else.

Inputs: `input` (parsed hook JSON).

Output: `{kept, shape}`. `kept` holds the whitelisted fields; `shape` is `describeShape(input)`. A non-object input gives `{shape}` only.

Errors: none.

Example:

```js
redactHookInput({ session_id: "test-123", hook_event_name: "PostToolUse", cwd: "/tmp/x", tool_name: "SendMessage", tool_input: { to: "listings-bc", message: "hello there", notify_when_idle: true }, tool_response: { ok: true } })
// kept:  { session_id: "test-123", hook_event_name: "PostToolUse", cwd: "/tmp/x", tool_name: "SendMessage", tool_input: { to: "listings-bc", notify_when_idle: true } }
// shape: { session_id: "string(8)", hook_event_name: "string(11)", cwd: "string(6)", tool_name: "string(11)", tool_input: { to: "string(11)", message: "string(11)", notify_when_idle: "boolean" }, tool_response: { ok: "boolean" } }
```

### buildRawRecord(stdinText, argv, now = new Date())

What it does: assembles the record that is appended to the raw log.

Inputs: `stdinText` (string) the hook's stdin; `argv` (string[]) the script arguments; `now` (Date).

Output: `{captured_at, hook_pid, ancestors, argv, cwd, input}` where `input` is `redactHookInput(parsed stdin)`, or `{unparseable: true, length}` when stdin is not JSON.

Errors: none.

Example: `buildRawRecord('not json', [], new Date("2026-10-05T21:40:00Z")).input` is `{ unparseable: true, length: 8 }`.

### appendRaw(logPath, record)

What it does: appends `JSON.stringify(record)` plus a newline to `logPath`, creating the parent directory.

Inputs: `logPath` (string); `record` (object).

Output: `true` on success, `false` when the write fails.

Errors: none thrown.

Example: `appendRaw("/nonexistent-root/raw.jsonl", {a: 1})` returns `false`.

### main(argv = process.argv.slice(2))

What it does: reads stdin, builds the record, appends it to the chosen log, swallows every error.

Inputs: `argv[0]` optional log path.

Output: none. Exit code is always 0.

Errors: none thrown.

Example:

```
echo '{"session_id":"test-123","hook_event_name":"Stop","cwd":"/tmp/x","stop_hook_active":false}' | node webhook/hooks/capture-raw.js /tmp/raw-test.jsonl; echo $?
0
```

The appended line has `input.kept` equal to `{"session_id":"test-123","hook_event_name":"Stop","cwd":"/tmp/x","stop_hook_active":false}`.
