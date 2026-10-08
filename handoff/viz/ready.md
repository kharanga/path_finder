# Ready: V3 2026-10-08

## Done

`viz/watcher.py` gains `Watcher`, `EventBroadcaster`, `VizRequestHandler`, and a `serve` command.

- `serve [--port 4780] [--root PATH] [--fixture PID=PATH ...] [--verbose]` binds `127.0.0.1:<port>` with `ThreadingHTTPServer` and runs the poll loop in a daemon thread every 250 ms. Each poll re-reads the registry and `discovery/identity/`, registers new live sessions under the root (resolving their transcript once, then tailing it from byte 0 so the state is rebuilt from history), drops sessions whose PID is gone with a `session_removed` event, and feeds every new transcript line through `StateModel`.
- `GET /state`: the full snapshot, `{"generated_at", "sessions", "messages"}`, `application/json`, no-store.
- `GET /events`: `text/event-stream`. The first frame is `{"event": "snapshot", ...}` with the same content as `/state`, so a page can connect without a separate fetch; every later frame is one change line as V2 emits it (`session`, `message`, or `session_removed`), `data: <json>` followed by a blank line. A `: keepalive` comment goes out after 15 s of silence. Each subscriber has its own queue; a dropped connection unsubscribes.
- Every other path is served statically, `viz/` first, then `discovery/`. With nothing in `viz/` yet, `/` is the D2 page and `/sessions.json` the D2 directory, so `discover.py ui`'s health check (`ui_is_up` fetches `/sessions.json`) reports the watcher as up and does not spawn a second server. This is how the port 4780 server is reused: the watcher serves the same files plus the two endpoints.
- `--fixture PID=PATH` tails the given files instead of the registry, for offline tests; a listed PID that is live in the registry still gets its name and label from it.
- `--port` other than 4780 is for tests. Bind failure prints the error and exits 1.
- V2 review note 1 fixed: the first `agent-name` on a bare session now emits a change (`name_changed` is computed before `learn_name` fills the name).

Files: `viz/watcher.py`. Nothing else touched.

## How to test

Registry mode (the two fake sessions are live). Port 4780 is held by the D2 `http.server` process (pid in `discovery/ui.pid`), which this session did not start, so use another port:

```
python3 viz/watcher.py serve --port 4799 --root fake_session &
sleep 1
curl -s http://127.0.0.1:4799/state | python3 -c "import sys,json; s=json.load(sys.stdin); print([(x['pid'], x['label'], x['status']) for x in s['sessions']], len(s['messages']))"
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' http://127.0.0.1:4799/sessions.json
kill %1
```

Expected: `[(32813, 'fake manager', 'IDLE'), (33993, 'fake builder', 'IDLE')] 73` (message count grows if the fake sessions talk again; stages are READ plus IN_INBOX for sends to sessions outside the root), then `200 application/json`.

Fixture mode, change within 1 s of an append (copies so the committed fixtures stay untouched):

```
T=$(mktemp -d); cp tests/fixtures/viz/round_trip_manager_32813_33993.jsonl $T/m.jsonl; cp tests/fixtures/viz/round_trip_builder_32813_33993.jsonl $T/b.jsonl
python3 viz/watcher.py serve --port 4798 --fixture 32813=$T/m.jsonl --fixture 33993=$T/b.jsonl &
sleep 1
curl -s -N http://127.0.0.1:4798/events > $T/events.txt &
sleep 0.5; date +%s.%N
echo '{"type":"assistant","timestamp":"2026-10-08T05:00:01.000Z","message":{"content":[{"type":"text","text":"hi"}]}}' >> $T/b.jsonl
sleep 1; date +%s.%N; grep -c '^data:' $T/events.txt; grep -o '"status": "WORKING"' $T/events.txt | head -1
kill %1 %2
```

Expected: two `data:` frames (the snapshot, then the 33993 session change with `"status": "WORKING"`). Measured here: 56 ms from append to frame. Any `turn_duration` line appended afterwards yields an IDLE frame the same way.

Full suite after the test updates under Requests: `python3 -m pytest tests`.

## Requests

- `tests/unit/test_state_model.py`: remove the strict xfail marker on `test_first_agent_name_on_bare_session_emits_a_change`; it passes now.
- `tests/integration/test_state_cli.py::test_state_events_stream`: the stream is 24 lines, not 23; the new first line is the bare manager session's `agent-name` change with `at` null, so the `watching == ["fake-session-builder"]` check belongs on `lines[1]`. The builder gets no such line because its name is learned from the manager's delivery entries before its own file is fed.
- For the manager, before V4 goes live on 4780: stop the D2 server (`python3 discovery/discover.py ui --stop`, which kills the pid in `discovery/ui.pid`) and start `python3 viz/watcher.py serve` in its place. Ask the discovery-builder to make `discover.py ui` start the watcher instead of `http.server`, or to leave `ui` alone and document that the watcher owns the port. Either way the health check keeps working.
- V6 note: `viz/events.jsonl` is not written yet; the broadcaster is the single point where every change passes, so V6 appends there.

## Blocked

Nothing.
