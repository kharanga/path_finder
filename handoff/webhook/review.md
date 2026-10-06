# Review: W3 2026-10-05

PASS

Live-stream caveat for the manager: since the hook was installed no session has started or ended, so `started` and `ended` were verified at unit level only (`buildEvent` mapping and schema). Starting and exiting one throwaway session should add one `started` and one `ended` line to `~/.claude/dashboard/events.jsonl`. Everything else in the acceptance list was observed live.

## What was checked

Acceptance: two live sessions produce correct events for start, busy, idle, one message, end; hook exits 0 and logs nothing even when the log dir is unwritable; `docs/webhook/hooks.md` covers each exported function.

- Live `events.jsonl`, counts only, no text read: 23 lines, 0 unparseable, 0 rejected by `parseEventLine`; 16 `session` lines (11 `busy`, 5 `idle`) across 4 PIDs, all with names resolved; 7 `message` lines, 0 with `from: null`. This session's PID appears with `busy` events.
- `hooks.md` examples: `stateForHook` (3 documented plus all five hook names), `lookupSessionRegistry` hit, entry without name, miss, and unreadable dir (temp registry dir with a malformed file and a non-json file skipped), `resolveSession` fallback via injected `findPid` and both-fail `{pid: null, name: null}`, `findClaudeAncestorPid` returns this session's PID, all four `buildEvent` examples, `appendEvent` on an unwritable path returns `false`. Every event `buildEvent` produces (including `waiting` and a `from: null` message) passes `validateEvent`.
- `schema.md` examples: all `validateEvent` and `parseEventLine` cases match, `waiting` accepted, `from: null` accepted.
- `main()` with `CC_DASHBOARD_EVENTS` pointing at a temp path: permission-prompt Notification with an unknown session id appends a `waiting` event with `session: null` and the enclosing claude PID; `SendMessage` appends a `message` with `from: null`; a non-permission Notification, garbage input, and empty stdin append nothing; all exit 0 with 0 bytes on stdout and stderr. Unwritable path: exit 0, silent. Runs in about 30 ms.
- Entry guard uses `realpathSync`, so a symlinked invocation now logs (round 1 note closed). A bare import yields 10 exports and writes nothing.

# Review: W4 2026-10-05 (round 2)

PASS. Round 1 failure 1 fixed: docs say `createRandom(42).hex2()` is `"99"` and that the PID allocator consumes the first draw (`int(1, 40)` gives 25, verified), so the next `hex2()` is `"72"`.

# Review: W4 2026-10-05 (round 1)

1. `docs/webhook/fake-generator.md`, `createRandom` section  input: `createRandom(42).hex2()`  expected (per docs): `"72"`  actual: `"99"`. The first session is still `listings-72` because `allocatePid` draws from the PRNG before the name does, so only the example value is wrong. Replace with `"99"` or document the first `int` draw.

## What passed

All ready.md expectations: fixture runs byte-identical with `--start-time`; 0 snapshot sessions and 124 events; kinds session 103, message 19, liveness 2; states started 17, waiting 1, ended 3 (busy 44, idle 40); notify 6; null from 1; ghost 1; null-name session events 2; 17 distinct names; first event exactly as documented; every one of the 124 events passes `validateEvent`. Snapshot fold: `8 6 49 4000`, 0 of 63 invalid, snapshot contains the `waiting` session. Zero sessions: the documented empty fixture, pretty-printed. Raw instant: 122 lines, 0 invalid. Error paths all exit 1 with one line: no output, both outputs, the real events path, the real path written unnormalized (`.claude/dashboard/../dashboard/events.jsonl`), unknown flag, bad start time. The real events file was not touched. Live mode, 20x, 8 sessions, 5 s: 9 s wall time, 113 valid lines, exactly one `ended`, zero `sleep 86400` children left. SIGINT after 2 s also leaves zero children.

Docs examples other than failure 1: `parseArgs` fixture example and the `[]` throw, `createGenerator` example, `runScenario` with 0 sessions records 0 entries, `buildFixture` example, `emit` throws on an invalid event.

# V1: test structure 2026-10-05

Done and committed by the manager. Layout in `tests/README.md`, run with `node --test "tests/**/*.test.js"`.
