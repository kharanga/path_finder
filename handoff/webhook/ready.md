# Ready: W4 fake event generator

## Done

- `webhook/fake.js` rewritten. Two output modes: `--out <path>` writes raw `events.jsonl` (live with real placeholder `sleep` processes per fake session, or `--instant`), `--fixture <path>` writes the page fixture `{snapshot, events: [{delayMs, event, data}]}` that `frontend/connect.js` replays, with `--snapshot-until <s>` folding the first seconds into `snapshot` through `state.js`. Every emitted event passes `validateEvent`. Refuses the real events path. Seeded, and with `--start-time` the output is byte-identical across runs.
- Scenario covers everything in SPEC §8.1 W4 plus the manager's additions: zero sessions, 15 sessions, same-folder siblings (three `listings`, three `path_finder`), restart with a new PID and name, death without `ended`, `waiting` state, a `session: null` body that later gets a name and sends a `from: null` message, and four `notify_on_idle` threads: recipient idles normally, recipient goes `waiting` first, recipient is `ghost-session-00` and never appears, recipient dies without `ended`. Fixture mode emits `liveness` entries for the two deaths.
- `docs/webhook/fake-generator.md`: scenario, flags, frontend commands, every exported function with examples.
- `docs/webhook/README.md`: index of module docs.
- Untouched this task: `server.js`, `tail.js`, `state.js`, `liveness.js` (W5, not assigned). `fake.js` imports `state.js` for the snapshot fold.

## How to test

Fixture mode, deterministic:

```
cd /Users/khangnguyen/Documents/path_finder
node webhook/fake.js --fixture /tmp/fx.json --start-time 2026-10-05T21:40:00Z
node webhook/fake.js --fixture /tmp/fx-again.json --start-time 2026-10-05T21:40:00Z && cmp /tmp/fx.json /tmp/fx-again.json && echo identical
python3 -c "
import json,collections
f=json.load(open('/tmp/fx.json')); ev=f['events']
print('snapshot sessions', len(f['snapshot']['sessions']), 'events', len(ev))
print('kinds', dict(collections.Counter(e['event'] for e in ev)))
print('states', dict(collections.Counter(e['data']['state'] for e in ev if e['data']['type']=='session')))
print('notify', sum(e['data'].get('notify_on_idle') is True for e in ev))
print('null from', sum(e['data']['type']=='message' and e['data']['from'] is None for e in ev))
print('ghost', sum(e['data']['type']=='message' and e['data']['to']=='ghost-session-00' for e in ev))
print('null-name session events', sum(e['data']['type']=='session' and e['data']['session'] is None for e in ev))
print('first', json.dumps(ev[0]))
"
```

Expected: `identical`; `snapshot sessions 0 events 124`; kinds `session 103, message 19, liveness 2`; states include `started 17, waiting 1, ended 3`; `notify 6`; `null from 1`; `ghost 1`; `null-name session events 2`; first event `{"delayMs": 3000, "event": "session", "data": {"ts": "2026-10-05T21:40:03.000Z", "type": "session", "session": "listings-72", "folder": "listings", "pid": 70025, "state": "started", "role": null}}`.

Snapshot fold and zero sessions:

```
node webhook/fake.js --fixture /tmp/fx-mid.json --sessions 8 --snapshot-until 40 --start-time 2026-10-05T21:40:00Z
python3 -c "import json; f=json.load(open('/tmp/fx-mid.json')); print(len(f['snapshot']['sessions']), len(f['snapshot']['messages']), len(f['events']), f['events'][0]['delayMs'])"
node webhook/fake.js --fixture /tmp/fx-zero.json --sessions 0 && cat /tmp/fx-zero.json
```

Expected: `8 6 49 4000`, and the zero fixture is `{"snapshot": {"sessions": [], "messages": []}, "events": []}` pretty-printed.

Raw instant mode validates:

```
node webhook/fake.js --out /tmp/fake.jsonl --instant && wc -l < /tmp/fake.jsonl
node -e 'import("./webhook/schema.js").then(({parseEventLine}) => { const fs = require("fs"); console.log("invalid:", fs.readFileSync("/tmp/fake.jsonl", "utf8").trim().split("\n").filter(l => !parseEventLine(l)).length) })'
```

Expected: `122` and `invalid: 0`.

Error paths:

```
node webhook/fake.js; echo $?
node webhook/fake.js --out /tmp/a --fixture /tmp/b; echo $?
node webhook/fake.js --out ~/.claude/dashboard/events.jsonl; echo $?
```

Expected: each prints one error line and exits 1; the real events file is not touched.

Live mode with placeholder processes, 20x speed, five seconds of random phase:

```
node webhook/fake.js --out /tmp/live.jsonl --speed 20 --sessions 8 --duration 5; echo "children left: $(pgrep -f 'sleep 86400' | wc -l | tr -d ' ')"
```

Expected: finishes in about 10 seconds, `children left: 0`, `/tmp/live.jsonl` has about 110 valid lines and exactly one `"state":"ended"` (the restart). Deaths are not in the file; the server's PID check finds them, which I verified with the draft server (two `liveness` frames for the killed PIDs within one interval, then the rest when the generator exited).

Docs examples in `docs/webhook/fake-generator.md` run by importing `webhook/fake.js`.

## Requests

1. frontend-builder (path-finder-18): fixture commands are in `docs/webhook/fake-generator.md` under "Commands for frontend-builder". Write generated fixtures into `frontend/fixtures/` yourself; I do not write into `frontend/`. `--snapshot-until` gives you a mid-run snapshot for the "browser connects late" case. `liveness` entries are in the fixture stream for the two deaths.
2. Manager: `docs/overview.md` fixture note. The frontend README documents the fixture shape; if you want it in the contract, the shape is `{snapshot, events: [{delayMs, event, data}]}` with `event` one of `session`, `message`, `liveness`.

## Blocked

Empty.
