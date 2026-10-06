# Review: W8 2026-10-06

PASS

## What was checked

- `claude plugin validate .` and on a fresh `git clone`: passes with the one intended `CLAUDE.md` warning. `hooks/hooks.json` has six entries, every command through `${CLAUDE_PLUGIN_ROOT}` (12 occurrences on 6 lines); `commands/dashboard.md` 3, `skills/declare-role/SKILL.md` 1. No repo path anywhere in the plugin files. The only `.nvm` hit is the search glob in `run-node.sh`, which is the documented fallback, not a hard-coded install.
- `run-node.sh`: with `PATH=/usr/bin:/bin` it finds the nvm Node and the hook writes its event; with `PATH=/nonexistent HOME=/nonexistent` it exits 0 with no output and writes nothing. Both silent.
- Roles on temp files: `declare-role.js` writes `roles.json` keyed by the session's start folder; the hook then stamps that role on a later event for the same `cwd` and leaves other folders at `null`; an unwritable roles path exits 1 with one line. New unit tests in `tests/unit/webhook/roles.test.js` cover `saveRole` (create, merge, replace, malformed or array file, missing cwd, unwritable), `readSavedRole` (exact match only, wrong type, missing or bad file), and `buildEvent` carrying the role.
- Clean-checkout acceptance, headless, `CC_DASHBOARD_EVENTS` and `CC_DASHBOARD_ROLES` on scratch files: run 1 replied `ok` and logged `started`, `busy`, `idle`, `ended` for its new session, each twice (settings snippet plus plugin hook). Run 2 replied `done`, the skill ran `declare-role.js` from the plugin root, and the file shows one `busy` with `role: "plugin-test"` (written by the script, so once) followed by `idle` and `ended` carrying the role, each twice. Two PIDs, two names. `roles.json` maps the session's start folder (the directory the headless session was launched from) to `plugin-test`. Real `events.jsonl` and `roles.json` untouched.
- `handoff/webhook/docs-examples.mjs`: 50 of 52, the same two session-literal checks as before.
- Suite: 129 tests, 127 pass, 2 todo, with the `cwd` field added to the two `resolveCallingSession` assertions as requested.

## Notes, not failures

1. ready.md expects the `('busy', 'plugin-test')` count to be even; it is 1 because that line comes from `declare-role.js`, not from a hook. The docs in `plugin.md` describe it correctly.
2. `roles.json` is keyed by the session's start folder, so running the acceptance from the repo root maps the repo path, not the clone path. `plugin.md` says start folder, which is right; ready.md's expected `/tmp/path_finder-clean` assumes the command is run from inside the clone.

# Review: W7 2026-10-05

PASS

## What was checked

Acceptance: `declare-role.js <role>` appends a `session` event for the calling session with `role` set, resolving PID and name like the hook; prints nothing on success and exits 0; exits 1 with one stderr line when the session cannot be resolved.

- CLI on a temp events file from this session: `validator` exits 0 with 0 bytes on stdout and stderr and appends one line with this session's name (`path-finder-e5`), claude PID (40707), folder `path_finder`, state `busy`, role `validator`; the line passes `parseEventLine`. Missing role and `bad/role!` print the usage line and exit 1. Unwritable path prints `declare-role: cannot write ...` and exits 1. A second declaration appends a second line, and reducing both through `webhook/state.js` followed by a later hook event with `role: null` keeps the latest role (`reviewer`) while the state updates. The real events file was not written by any of these runs.
- `declare-role.md` examples: `parseRole` trim and every documented throw (plus a 41-character role, a blank, and a leading dash, all rejected), the four `resolveCallingSession` cases, an `ended` registry status mapping to `busy`, `buildRoleEvent`, `main` returning 1 with one stderr line.
- `hooks.md` additions: `readSessionRegistry("/nonexistent")` is `[]`, the live registry lists this session, `lookupSessionRegistryByPid` resolves this session's name and returns `null` for PID 1.
- W5 notes closed: with a scratch frontend dir containing `escape.txt -> /etc/hosts`, `resolveStaticFile` returns `null` for it and still serves `index.html`; `parseArgs` rejects `--port` with no value, `abc`, or `-1`, `--liveness-interval` and `--poll` likewise, and `--events` or `--host` without a value, each with the documented message.
- Live acceptance (role appears under the body within a tail interval) was not run against the real events file from this session, since that would write real data from a review step. The builder reports it verified from their session; the reducer behavior that makes it work is covered above.

# Review: W6 2026-10-05

PASS

## What was checked

Acceptance: every public function has a one-line docstring; every module has a docs file with what, inputs, output, errors, example; every documented example produces the documented output.

- Docstring coverage command from ready.md: zero exports without a `/** */` line, zero non-docstring comments across `webhook/*.js` and `webhook/hooks/*.js`.
- Module docs: `schema.md`, `state.md`, `tail.md`, `liveness.md`, `server.md`, `fake-generator.md` present; `hooks.md` has 19 headed sections; `README.md` indexes them.
- `handoff/webhook/docs-examples.mjs` run with a scratchpad temp dir (it now holds 50 checks after W7): `passed 48, failed 2`. The two failures are `hook ancestor` and `declare cli`, both asserting the writing session's PID and name (52134, `path-finder-37`), which differ by nature from this session. `hook registry` and `hook main cli` pass because that session's registry entry still exists. Every other example, including the CLI and HTTP ones, matches. The runner touches only its temp dir and leaves no child processes; the real events file was not modified by it.
- All examples I had already verified by hand in the W1 to W5 reviews still hold.

For V5 I will move the runner's checks into `tests/docs-examples/` and parameterize the session-specific values from the running session instead of literals.

# Review: W5 2026-10-05

PASS

## What was checked

Acceptance: browser connecting mid-run receives a correct snapshot; killing a session process marks it ended within one interval; server survives malformed lines; `docs/webhook/server.md` has one entry per public function and endpoint.

ready.md unit script: every line matches the expected output. End to end on port 4796 with two `sleep` stand-ins and a temp registry dir: startup log `replayed 2 events, skipped 2 malformed lines`; static table exactly as expected (four 200s with the right content types, `/nope.js`, `/../CLAUDE.md`, `/%2e%2e/CLAUDE.md`, `/fixtures` all 404 with body `not found`, `POST` 405, `HEAD` 200 with an empty body, `Cache-Control: no-store`); `/snapshot` after the message, the registry correction, and the kill: `[('tag-analyzer-63', 'busy'), ('listings-bc', 'ended')] 1` with stats `linesRead 6, malformedLines 3, eventsApplied 3, livenessEnded 1, statusCorrections 1`; SSE frame order `snapshot, message, session, liveness`; late client snapshot shows the corrected states and the message text; clean exit 0, no stand-ins left. Extra: truncating the events file mid-run and appending a new line is picked up (`linesRead` 7, new session present).

Demo mode on port 4795: 3 sessions and 11 events applied after 12 s, page serves 200, SIGINT exits and leaves zero `sleep 86400` children. Fixture speed: `124 124 16.05 160.5 True`.

Docs examples, all matching: `server.md` (`parseArgs` incl. the throw, `sseFrame`, `DEFAULTS`, ten `CONTENT_TYPES`, every `resolveStaticFile` case incl. bad encoding, `createHub` ingest/stats/frames/remove/liveness, `startServer` on port 0 with `/snapshot` stats and a rejected `EADDRINUSE` on a second bind); `tail.md` (`readNewLines` three steps incl. truncation and the missing file, `tailFile` replay marker, `fromStart: false`, a file that appears later); `liveness.md` (`isPidAlive`, `hasSocket`, `readRegistryStatus` hit/miss/bad json, `findDeadSessions` both cases, `findStatusCorrections` newer, older, agreeing, missing, `ended` status, unknown status, name fill); webhook `state.md` (`createState(2)`, name/folder/role carry-over, message trim, `findSessionByName`, `snapshot`); `fake-generator.md` `buildFixture` with `speed` (250 at speed 4 per docs, 100 at speed 10 verified). Every export of `server.js`, `tail.js`, `liveness.js`, `state.js` has a docs entry.

## Notes, not failures

1. `resolveStaticFile` resolves paths lexically and then `statSync` follows symlinks, so a symlink placed inside `frontend/` pointing outside would be served. Nothing in the repo does that; mention it in server.md or add a `realpathSync` check if you want it closed.
2. `--port` without a value becomes `NaN` and the listen rejects with an unclear error. Low priority.

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

# V2: unit tests for webhook 2026-10-05

Done. `tests/unit/webhook/` holds one file per module, 8 files, 71 tests, all green with `node --test "tests/**/*.test.js"` (82 tests in the whole suite, 2 todo markers for V4 and V5).

| File | Covers | Mocks |
|---|---|---|
| `schema.test.js` | every validation error, all five states, null sender, `parseEventLine` edge cases | none needed |
| `state.test.js` | pid keying, name/folder/role carry-over, message cap, name lookup preferring live, snapshot order | none needed |
| `liveness.test.js` | `isPidAlive` EPERM/ESRCH, socket hint, registry reads incl. bad JSON and wrong types, dead-session detection, every status-correction rule | `process.kill` via `mock.method`, injected `isAlive`/`readStatus`, temp registry dir |
| `tail.test.js` | partial lines, truncation restart, missing file, multi-byte split, malformed lines passed through, replay then poll, `fromStart`, file appearing later | `mock.timers` for the poll interval, temp files |
| `server.test.js` | flag parsing and every flag error, SSE frame, static resolution incl. traversal, bad encoding, directory, symlink escape, hub ingest/stats/broadcast/late snapshot/message limit, liveness check broadcasting `liveness` and `session` | injected `isAlive`/`readStatus`, temp frontend dir |
| `dashboard-hook.test.js` | hook-to-state mapping incl. `waiting`, registry lookups by session id and pid with malformed files, resolver fallback, every `buildEvent` branch validated against the schema, `appendEvent`, and the script itself run with stdin for silent exit 0 and an unwritable path | injected `findPid`, temp registry and events dirs, `CC_DASHBOARD_EVENTS` |
| `declare-role.test.js` | role pattern, session resolution with injected lookups, event building, `main` error path | injected resolvers, `process.stderr.write` via `mock.method` |
| `fake.test.js` | PRNG determinism, flag parsing incl. refusing the real events path, generator with injected writer and virtual clock, anonymous/rename/end/kill/liveness paths, zero-session run, structural checks on the default scenario, byte-identical reruns, `buildFixture` fold and speed | injected `write`/`now`, `noChildren` |

Not covered on purpose: `findClaudeAncestorPid` and `ancestorChain` (they shell out to `ps`; covered indirectly by the hook script run), `startServer`/`handleRequest` over HTTP, `tailFile` against a live server, and `startDemoGenerator` (V4 integration). Nothing reads or writes `~/.claude`, `/tmp/cc-socks`, or the real events file.

# V1: test structure 2026-10-05

Done and committed by the manager. Layout in `tests/README.md`, run with `node --test "tests/**/*.test.js"`.
