# fake.js

Writes a realistic stream of §3 events so the page and the server can be developed without live sessions. Two output modes:

- `--out <path>`: raw `events.jsonl`, the same shape hooks write. Live by default: events appear in real time, every fake session is backed by a real placeholder process (`sleep 86400`) so the server's PID liveness check works, and the "dies without ended" session really gets killed. `--instant` writes the whole stream at once with virtual timestamps and no processes.
- `--fixture <path>`: the page fixture `{snapshot, events: [{delayMs, event, data}]}` that `frontend/connect.js` replays. Always instant. `event` is `session`, `message`, or `liveness`; `liveness` entries stand in for the server's synthetic ended events.

Refuses to write to `~/.claude/dashboard/events.jsonl`.

## Scenario

With the default 15 sessions, in order:

1. Three seconds with zero sessions.
2. Sessions start one by one across `FOLDERS` (three `listings`, three `path_finder`, nine others), each going `started`, `busy`, `idle`, with some plain messages.
3. `notify_on_idle` message, recipient goes `busy` then `idle` (thread snaps back normally).
4. `notify_on_idle` message, recipient goes `busy`, `waiting`, `busy`, `idle` (thread survives a permission prompt).
5. `notify_on_idle` message to `ghost-session-00`, a name with no session on the ring.
6. A session starts with `session: null` (name lookup failed), sends a message with `from: null`, then a later event gives it a name.
7. A session is renamed mid-stream, same PID, to `RENAMED_NAME` (`manager-drives-feature-work`), mirroring Claude Code's auto-rename. It sends a message under the old name, then receives a `notify_on_idle` message and sends another under the new name.
8. A session ends and a new one starts in the same folder with a new PID and new name suffix (restart).
9. A session goes `busy` and dies without `ended`. In instant and fixture mode a `liveness` entry follows after 5 virtual seconds; in live mode the server detects the dead PID itself.
10. Removal, as the server's `POST /sessions/<pid>/remove` would write it: one session goes `ended` and is then `removed` (gone for good, no later events), then a live session is `removed` by mistake and comes back with `busy` and `idle` two virtual seconds later.
11. `notify_on_idle` message whose recipient then dies without `ended`.
12. Random activity: busy/idle cycles, occasional `waiting`, messages with 30% `notify_on_idle`. Runs until `--duration` seconds (default 60 in instant and fixture mode, unbounded in live mode) or Ctrl-C.

Fewer sessions skip the steps that need more participants: steps 3 and 7 need 2, step 4 needs 3, step 8 needs 4, step 6 needs 5, step 9 needs 6, step 10 needs 7, step 11 needs 8. `--sessions 0` produces an empty stream.

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--out <path>` | | write raw events.jsonl |
| `--fixture <path>` | | write the page fixture instead |
| `--speed <x>` | 1 | divide every wait by x: live mode sleeps less, fixture mode writes smaller `delayMs` (timestamps stay at real pace) |
| `--sessions <n>` | 15 | how many of `FOLDERS` to start, 0 to 15 |
| `--seed <n>` | 42 | PRNG seed, same seed gives the same names, texts, and timing |
| `--instant` | off | raw mode without waits or processes |
| `--duration <s>` | 60 instant, unbounded live | length of the random phase |
| `--snapshot-until <s>` | 0 | fixture mode, fold everything up to this virtual second into `snapshot` |
| `--start-time <iso>` | now | instant mode, timestamp of virtual second 0, makes output byte-identical across runs |

## Commands for frontend-builder

Regenerate the page fixtures:

```
node webhook/fake.js --fixture frontend/fixtures/generated-many.json --start-time 2026-10-05T21:40:00Z
node webhook/fake.js --fixture frontend/fixtures/generated-mid.json --sessions 8 --snapshot-until 40 --start-time 2026-10-05T21:40:00Z
```

A fast variant for test runs, every `delayMs` divided by 10 so the 172 second stream plays in 17:

```
node webhook/fake.js --fixture /tmp/generated-fast.json --speed 10 --start-time 2026-10-05T21:40:00Z
```

Live against the real server, one command: `node webhook/server.js --demo` (lands with W5). Until then, two terminals:

```
node webhook/fake.js --out /tmp/fake-events.jsonl --speed 3
node webhook/server.js --events /tmp/fake-events.jsonl --liveness-interval 2000
```

## createRandom(seed)

What it does: mulberry32 PRNG.

Inputs: `seed` (integer).

Output: `{next(), int(min, max), pick(items), hex2()}`.

Errors: none.

Example: `createRandom(42).hex2()` is `"99"`. In the scenario the first draw goes to the PID allocator (`int(1, 40)` gives `25`), so the first session name uses the second draw and is always `listings-72`.

## parseArgs(argv)

What it does: turns CLI flags into an options object and validates them.

Inputs: `argv` (string[]) without the node and script entries.

Output: `{out, fixture, speed, sessions, seed, instant, durationSeconds, snapshotUntilSeconds, startTime}`. `--fixture` forces `instant: true`. Instant mode defaults `durationSeconds` to 60.

Errors: throws `Error` for an unknown flag, no output path, both output paths, the real events path, a non-positive speed, or a non-ISO start time.

Example:

```js
parseArgs(["--fixture", "/tmp/f.json", "--sessions", "8"])
// { out: null, fixture: "/tmp/f.json", speed: 1, sessions: 8, seed: 42, instant: true, durationSeconds: 60, snapshotUntilSeconds: 0, startTime: null }
parseArgs([]) // throws "--out <path> or --fixture <path> is required"
```

## createGenerator(options, deps = {})

What it does: builds the stateful generator. `deps.write(entry)` replaces file output, `deps.now` replaces the clock, `deps.noChildren` skips placeholder processes.

Inputs: `options` from `parseArgs`; `deps` (object, optional).

Output: `{random, sessions, entries, live(), advance(ms), startSession(folder, {anonymous}), setState(session, state), nameSession(session), renameSession(session, newName), endSession(session), removeSession(session), killSilently(session), emitLiveness(session), sendMessage(from, to, notifyOnIdle), shutdown(), emit(event)}`. Every emitted event passes `validateEvent` first. `entries` holds `{atMs, event, data}` for everything emitted.

Errors: `emit` throws when an event is invalid, which only happens on a programming error in the scenario.

Example:

```js
const written = [];
const generator = createGenerator({ instant: true, seed: 1 }, { write: (entry) => written.push(entry), now: () => new Date("2026-10-05T21:40:00Z") });
const session = generator.startSession("listings");
generator.advance(1000);
generator.setState(session, "busy");
written.map((entry) => [entry.atMs, entry.event, entry.data.state])
// [[0, "session", "started"], [1000, "session", "busy"]]
```

## runScenario(generator, options, sleepFn)

What it does: plays the scenario above through the generator.

Inputs: `generator`; `options` from `parseArgs`; `sleepFn(ms)` (returns a Promise) used in live mode only.

Output: Promise that resolves when the random phase ends.

Errors: none expected.

Example: `await runScenario(createGenerator(opts, {write}), opts)` with `opts = parseArgs(["--fixture", "/tmp/x.json", "--sessions", "0"])` records zero entries.

## buildFixture(entries, snapshotUntilSeconds = 0, speed = 1)

What it does: converts recorded entries into the page fixture, reducing entries up to the cutoff into `snapshot` through `state.js` and turning the rest into timed events with `delayMs` relative to the previous one (the first relative to the cutoff), divided by `speed` and rounded.

Inputs: `entries` (`{atMs, event, data}[]`); `snapshotUntilSeconds` (number); `speed` (positive number).

Output: `{snapshot: {sessions, messages}, events: [{delayMs, event, data}]}`.

Errors: none.

Example:

```js
buildFixture([
  { atMs: 3000, event: "session", data: { ts: "2026-10-05T21:40:03.000Z", type: "session", session: "a-01", folder: "a", pid: 1, state: "started", role: null } },
  { atMs: 5000, event: "session", data: { ts: "2026-10-05T21:40:05.000Z", type: "session", session: "a-01", folder: "a", pid: 1, state: "busy", role: null } },
], 4)
// { snapshot: { sessions: [{ ...state: "started" }], messages: [] }, events: [{ delayMs: 1000, event: "session", data: { ...state: "busy" } }] }
```

With the same entries and `speed = 4` the single event has `delayMs: 250`.

## Command examples

```
node webhook/fake.js --fixture /tmp/fx.json --start-time 2026-10-05T21:40:00Z
```

Produces 134 events, 0 snapshot sessions, 18 distinct names, 7 `notify_on_idle` messages, 1 message with `from: null`, 1 message to `ghost-session-00`, 2 `liveness` entries, first event `{"delayMs":3000,"event":"session","data":{"ts":"2026-10-05T21:40:03.000Z","type":"session","session":"listings-72","folder":"listings","pid":70025,"state":"started","role":null}}`. Running it twice gives byte-identical files.

```
node webhook/fake.js --out /tmp/fake.jsonl --instant
```

Produces 132 lines (the two liveness entries are not written in raw mode), every line passes `parseEventLine`.
