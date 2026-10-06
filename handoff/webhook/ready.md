# Ready: W5 server (plus fake.js --speed for fixtures)

## Done

- `webhook/server.js`: replays and tails the events file (`--events`, default `~/.claude/dashboard/events.jsonl`), keeps state through `state.js`, serves `GET /` as `frontend/index.html` and every other non-`/events` path as a static file from the frontend directory with content types for `.html`, `.js`, `.mjs`, `.css`, `.json`, `.svg`, `.png`, `.ico`, `.woff2`, `.txt`. Paths that escape the directory, directories, and missing files are 404; non-GET is 405. `GET /events` is SSE: `: connected`, `event: snapshot`, then `session`, `message`, `liveness`, and a `: ping` every 15 s. `GET /snapshot` is a JSON debug view with stats. Prints `dashboard at http://127.0.0.1:4747/` on start. `--demo` spawns `fake.js` on a temp file. Ctrl-C stops cleanly and kills the demo child.
- `webhook/liveness.js`: PID check plus `readRegistryStatus` and `findStatusCorrections`. On every liveness interval the server reads `~/.claude/sessions/<pid>.json` (`--sessions-dir` overrides) and, when `statusUpdatedAt` is newer than the last hook event and `status` disagrees, broadcasts a corrective `event: session`. It also fills a null `session` name from the registry. Stale registry entries are ignored.
- `webhook/tail.js`: byte-offset tailer with partial-line carry, truncation restart, and missing-file tolerance.
- `webhook/state.js`: unchanged since the draft; reducer keeps an earlier name and role when a later event has null, caps messages at 500.
- `webhook/fake.js`: `--speed` now also applies to fixture mode, dividing every `delayMs` (timestamps keep real pace). Requested by frontend-builder via the manager.
- `docs/webhook/server.md`: endpoints and every exported function of `server.js`, `tail.js`, `state.js`, `liveness.js`. `docs/webhook/fake-generator.md` updated for `--speed`. `docs/webhook/README.md` index updated.

## How to test

Unit level, every helper, no network:

```
cd /Users/khangnguyen/Documents/path_finder
cat > /tmp/w5-check.mjs <<'EOF'
import { createHub, resolveStaticFile, parseArgs } from "/Users/khangnguyen/Documents/path_finder/webhook/server.js";
import { findStatusCorrections, findDeadSessions } from "/Users/khangnguyen/Documents/path_finder/webhook/liveness.js";
import { createState, applyEvent } from "/Users/khangnguyen/Documents/path_finder/webhook/state.js";
import { readNewLines } from "/Users/khangnguyen/Documents/path_finder/webhook/tail.js";
import { writeFileSync, appendFileSync } from "node:fs";
const fe = "/Users/khangnguyen/Documents/path_finder/frontend";
console.log(resolveStaticFile(fe, "/").contentType, resolveStaticFile(fe, "/app.js").contentType, resolveStaticFile(fe, "/../CLAUDE.md"), resolveStaticFile(fe, "/%2e%2e/CLAUDE.md"), resolveStaticFile(fe, "/fixtures"));
const state = createState();
applyEvent(state, { ts: "2026-10-05T21:40:02Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: null });
const now = new Date("2026-10-05T21:45:00Z");
console.log(findDeadSessions(state, now, () => false).map(e => e.state), findDeadSessions(state, now, () => true).length);
console.log(findStatusCorrections(state, now, () => ({ status: "busy", name: "listings-bc", statusUpdatedAt: Date.parse("2026-10-05T21:44:00Z") })).map(e => e.state));
console.log(findStatusCorrections(state, now, () => ({ status: "busy", name: "listings-bc", statusUpdatedAt: Date.parse("2026-10-05T21:39:00Z") })).length);
const hub = createHub({ isAlive: () => true, readStatus: () => null });
hub.ingestLine("not json"); hub.ingestLine('{"ts":"x"}'); hub.ingestLine('{"ts":"2026-10-05T21:40:00Z","type":"session","session":"a-1","folder":"a","pid":1,"state":"busy","role":null}');
console.log(hub.stats.malformedLines, hub.stats.eventsApplied);
writeFileSync("/tmp/w5-tail.jsonl", "a\nb\npartial"); let r = readNewLines("/tmp/w5-tail.jsonl", 0);
appendFileSync("/tmp/w5-tail.jsonl", "-done\nc\n"); r = readNewLines("/tmp/w5-tail.jsonl", r.offset, r.carry); console.log(r.lines);
console.log(parseArgs(["--port", "5000", "--liveness-interval", "0"], { port: 1 }));
EOF
node /tmp/w5-check.mjs
```

Expected, line by line: `text/html; charset=utf-8 text/javascript; charset=utf-8 null null null`; `[ 'ended' ] 0`; `[ 'busy' ]`; `0`; `2 1`; `[ 'partial-done', 'c' ]`; `{ port: 5000, livenessIntervalMs: 0 }`.

End to end over HTTP. Uses two `sleep` processes as stand-in session PIDs and a temp registry dir, never the real files:

```
cd /Users/khangnguyen/Documents/path_finder
mkdir -p /tmp/w5/reg; E=/tmp/w5/e2e.jsonl; P=4796
sleep 86400 & VICTIM=$!; sleep 86400 & CORR=$!
printf '{"ts":"2026-10-05T21:40:00Z","type":"session","session":"listings-bc","folder":"listings","pid":%d,"state":"started","role":null}\n{"ts":"2026-10-05T21:40:01Z","type":"session","session":"tag-analyzer-63","folder":"tag_analyzer","pid":%d,"state":"idle","role":null}\nnot json\n{"ts":"bad"}\n' $VICTIM $CORR > $E
node webhook/server.js --events $E --port $P --liveness-interval 1000 --sessions-dir /tmp/w5/reg & SRV=$!; sleep 1
for p in / /app.js /orbit.css /fixtures/few.json /nope.js /../CLAUDE.md /%2e%2e/CLAUDE.md /fixtures; do printf "%-20s %s %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' --path-as-is http://127.0.0.1:$P$p)" "$(curl -s -o /dev/null -w '%{content_type}' --path-as-is http://127.0.0.1:$P$p)"; done
curl -s -o /dev/null -w 'POST %{http_code}\n' -X POST http://127.0.0.1:$P/
(curl -s -N -m 8 http://127.0.0.1:$P/events > /tmp/w5/sse.txt &); sleep 0.5
printf '{"ts":"2026-10-05T21:40:05Z","type":"message","from":"listings-bc","to":"tag-analyzer-63","text":"L16 is ready","notify_on_idle":true}\ngarbage line\n' >> $E; sleep 0.6
echo "{\"pid\":$CORR,\"name\":\"tag-analyzer-63\",\"status\":\"busy\",\"statusUpdatedAt\":$(node -e 'console.log(Date.now())')}" > /tmp/w5/reg/$CORR.json; sleep 1.3
kill -9 $VICTIM; sleep 1.5
curl -s http://127.0.0.1:$P/snapshot | python3 -c "import json,sys; d=json.load(sys.stdin); print([(s['session'],s['state']) for s in d['sessions']], len(d['messages']), d['stats'])"
sleep 4; grep -E '^event:' /tmp/w5/sse.txt | tr '\n' ' '; echo
curl -s -N -m 1 http://127.0.0.1:$P/events | grep -A1 '^event: snapshot' | grep ^data | python3 -c "import json,sys; d=json.loads(sys.stdin.read()[5:]); print([(s['session'],s['state']) for s in d['sessions']], [m['text'] for m in d['messages']])"
kill $SRV $CORR; wait $SRV; echo "server exit $?"
```

Expected:

- Server prints `dashboard at http://127.0.0.1:4796/` and `replayed 2 events, skipped 2 malformed lines`.
- Static table: `/` 200 `text/html; charset=utf-8`, `/app.js` 200 `text/javascript; charset=utf-8`, `/orbit.css` 200 `text/css; charset=utf-8`, `/fixtures/few.json` 200 `application/json; charset=utf-8`, the other four 404 `text/plain`. `POST 405`.
- Snapshot: `[('tag-analyzer-63', 'busy'), ('listings-bc', 'ended')] 1 {'linesRead': 6, 'malformedLines': 3, 'eventsApplied': 3, 'livenessEnded': 1, 'statusCorrections': 1}`.
- SSE frame order: `event: snapshot event: message event: session event: liveness` (the `session` frame is the registry correction to `busy`, the `liveness` frame is the killed PID).
- Late client snapshot: `[('tag-analyzer-63', 'busy'), ('listings-bc', 'ended')] ['L16 is ready']`.
- `server exit 0`.

Demo mode, one command:

```
node webhook/server.js --demo --port 4795 & D=$!; sleep 12; curl -s http://127.0.0.1:4795/snapshot | python3 -c "import json,sys; print('sessions', len(json.load(sys.stdin)['sessions']))"; kill -INT $D; sleep 1; echo "children left: $(pgrep -f 'sleep 86400' | wc -l | tr -d ' ')"
```

Expected: `sessions` at least 2, `children left: 0`. Open `http://127.0.0.1:4795/` in a browser while it runs to see the page on live data.

Fixture speed:

```
node webhook/fake.js --fixture /tmp/fast.json --speed 10 --start-time 2026-10-05T21:40:00Z
node webhook/fake.js --fixture /tmp/slow.json --start-time 2026-10-05T21:40:00Z
python3 -c "import json; a=json.load(open('/tmp/fast.json')); b=json.load(open('/tmp/slow.json')); print(len(a['events']), len(b['events']), sum(e['delayMs'] for e in a['events'])/1000, sum(e['delayMs'] for e in b['events'])/1000, a['events'][0]['data']['ts']==b['events'][0]['data']['ts'])"
```

Expected: `124 124 16.05 160.5 True`.

Docs examples in `docs/webhook/server.md` and the updated `buildFixture` example in `docs/webhook/fake-generator.md` run by importing the modules.

## Requests

1. Manager, `CLAUDE.md` run commands are now real:

```
# run server (prints the dashboard URL)
node webhook/server.js

# demo with fake data, no live sessions needed
node webhook/server.js --demo
```

2. Manager: `GET /snapshot` is a debug endpoint outside the contract. Keep it undocumented in `docs/overview.md` or add one line; either is fine with me.
3. Manager: the registry status poll reads `~/.claude/sessions/*.json`, an undocumented internal like `/tmp/cc-socks/`. Worth a line under Liveness in `docs/overview.md` so the dependency is visible.

## Blocked

Empty.
