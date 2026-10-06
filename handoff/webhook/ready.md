# Ready: W9 session removal endpoint

## Done

- `webhook/schema.js`: `SESSION_STATES` gains `removed` as the sixth state; new `NOT_LIVE_STATES = ["ended", "removed"]`. The `validateEvent` state error message now lists `removed`.
- `webhook/state.js`: new `isLive(session)` and `liveSessions(state)`; `snapshot` excludes `removed` sessions (ended ones stay so the page can fade them); `findSessionByName` never returns a removed session. A removed session stays in the map, so any later event for its PID replaces it and it reappears.
- `webhook/liveness.js`: `findDeadSessions` and `findStatusCorrections` skip removed sessions, so the liveness interval can neither end nor resurrect one.
- `webhook/server.js`: `POST /sessions/<pid>/remove` appends a `session` event with state `removed` carrying the PID's current name, folder, and role to the events file, applies it, and broadcasts it as `event: session`. 204 on success, 404 `unknown pid`, 405 with `Allow: POST` for other methods. New `hub.removeSession(pid)`; `stats` gains `removals`. The tailer recognizes the line the server just wrote and does not apply or broadcast it a second time, so SSE clients see exactly one `removed` frame.
- `webhook/fake.js`: new `removeSession`; scenario step 10 ends one session and removes it (gone for good), then removes a live session by mistake and brings it back with `busy` and `idle`. Both output modes. Fixture is now 134 events, raw instant 132 lines, 7 notify messages, 18 names, 171.5 s total, 17.15 s at `--speed 10`.
- Verified: unit checks of every helper; HTTP 204/404/405; curl SSE client received exactly one `removed` frame and then the `busy` comeback frame; server restarted on the same file still omits the PID; `/snapshot` stats show `removals: 1` and `eventsApplied` without double counting.
- Docs: `schema.md`, `state.md`, `liveness.md`, `server.md` (endpoint and `removeSession`), `fake-generator.md` updated. `handoff/webhook/docs-examples.mjs` now 53 checks, `passed 53, failed 0`.

## How to test

Against the demo server, as SPEC W9 acceptance says. Use a temp events file so the real one is untouched:

```
cd /Users/khangnguyen/Documents/path_finder
node webhook/fake.js --out /tmp/w9/events.jsonl --instant
node webhook/server.js --events /tmp/w9/events.jsonl --port 4793 --liveness-interval 0 & SRV=$!; sleep 1
PID=$(curl -s http://127.0.0.1:4793/snapshot | python3 -c "import json,sys; print(json.load(sys.stdin)['sessions'][0]['pid'])")
(curl -s -N -m 6 http://127.0.0.1:4793/events > /tmp/w9/sse.txt &); sleep 0.5
curl -s -o /dev/null -w "remove %{http_code}\n" -X POST http://127.0.0.1:4793/sessions/$PID/remove
curl -s -o /dev/null -w "unknown %{http_code}\n" -X POST http://127.0.0.1:4793/sessions/4242/remove
curl -s -o /dev/null -w "get %{http_code}\n" http://127.0.0.1:4793/sessions/$PID/remove
curl -s http://127.0.0.1:4793/snapshot | python3 -c "import json,sys; d=json.load(sys.stdin); print('pid still listed:', $PID in [s['pid'] for s in d['sessions']], '| removals', d['stats']['removals'])"
tail -1 /tmp/w9/events.jsonl | cut -c1-120
kill $SRV; sleep 0.5
node webhook/server.js --events /tmp/w9/events.jsonl --port 4793 --liveness-interval 0 & SRV=$!; sleep 1
curl -s http://127.0.0.1:4793/snapshot | python3 -c "import json,sys; d=json.load(sys.stdin); print('after restart still listed:', $PID in [s['pid'] for s in d['sessions']])"
echo "{\"ts\":\"2026-10-06T08:00:00Z\",\"type\":\"session\",\"session\":\"back-again\",\"folder\":\"listings\",\"pid\":$PID,\"state\":\"busy\",\"role\":null}" >> /tmp/w9/events.jsonl; sleep 0.6
curl -s http://127.0.0.1:4793/snapshot | python3 -c "import json,sys; d=json.load(sys.stdin); print('after new event listed:', $PID in [s['pid'] for s in d['sessions']])"
kill $SRV
sleep 6; echo "removed frames: $(grep -c '\"state\":\"removed\"' /tmp/w9/sse.txt) (expect 1)"
```

Expected: `remove 204`, `unknown 404`, `get 405`, `pid still listed: False | removals 1`, the last file line has `"state":"removed"` with the PID's name and folder, `after restart still listed: False`, `after new event listed: True`, `removed frames: 1`.

Generator scenario:

```
node webhook/fake.js --fixture /tmp/w9/fx.json --start-time 2026-10-05T21:40:00Z
python3 -c "
import json; ev=json.load(open('/tmp/w9/fx.json'))['events']
rem=[(i,e['data']['pid']) for i,e in enumerate(ev) if e['data'].get('state')=='removed']
print(len(ev), rem, [[e['data']['state'] for j,e in enumerate(ev) if j>i and e['data'].get('pid')==pid][:2] for i,pid in rem])"
```

Expected: `134 [(97, 70144), (98, 70025)] [[], ['busy', 'idle']]`, that is one removal with no later events and one that comes back.

Docs examples: `node handoff/webhook/docs-examples.mjs /tmp/webhook-docs-examples` gives `passed 53, failed 0`.

## Requests

1. Validator, test shape changes from W9, all in `tests/`. Suite run before handoff with `node --test --test-force-exit --test-timeout=60000 "tests/**/*.test.js"`: 195 tests, 175 pass, 20 fail. Seven of the failures are W9:
   - `tests/unit/webhook/schema.test.js:8` `SESSION_STATES` is now six states, `[..., "ended", "removed"]`.
   - `tests/unit/webhook/schema.test.js:29` the state error message is `state must be one of started, busy, waiting, idle, ended, removed`.
   - `tests/unit/webhook/server.test.js:65` and `:102` `hub.stats` has a sixth key `removals: 0`.
   - `tests/unit/webhook/fake.test.js:89` the default scenario now also produces state `removed`.
   - `tests/docs-examples/webhook-docs.test.js` checks `schema validate errors` and `schema states`, same two changes. If that file still carries the old `stats` strings and fixture counts (129, 127), they are now `removals: 0`, 134, and 132.
2. Validator, suite hygiene: `webhook-docs.test.js` `server startServer` calls `stop()` only at the end of the test body, so when an assertion fails the server stays open and the file's process never exits, which is why `node --test` hung for me until I used `--test-force-exit`. Register the stop with `t.after(stop)` right after `startServer`, or run the suite with `--test-force-exit`. The same applies to my runner; I will not touch your copy.
3. Validator and manager, not W9: the other 13 failures are all frontend: `tests/docs-examples/frontend-docs.test.js` (uncaught `Cannot read properties of null (reading 'querySelector')` after a test ended), `tests/unit/frontend/layout.test.js`, and eleven render tests. None of those files import webhook code, and `git status` shows only my runner modified, so they come from the Circuit v2 frontend work in progress.
4. Manager: `docs/overview.md` already lists `removed` and the endpoint. One wording nit there if you want it: the endpoint broadcasts the removal as `event: session`, not as a separate event name.

## Blocked

Empty.
