# Review: V3 2026-10-08

PASS

## Checked against SPEC.md V3

- `GET /state` on the running server returns both fake sessions (`32813 fake manager IDLE`, `33993 fake builder IDLE`) and 73 messages with stages READ and IN_INBOX, as `application/json`, `Cache-Control: no-store`, keys `generated_at`, `sessions`, `messages`. Checked on port 4797 in registry mode with `--root fake_session`.
- `GET /events` streams a change within 1 s of an appended line: in fixture mode on port 4796 the snapshot frame arrived first, then the 33993 WORKING frame within the 1 s window after the append; the integration test measures the gap and asserts under 1 s. A `turn_duration` append yields an IDLE frame the same way. Headers are `text/event-stream`, `no-store`.
- Port 4780 is held by the D2 `http.server` (pid 62889, started by a session none of us own); not touched. `serve --port 4780` reports `cannot bind 127.0.0.1:4780: [Errno 48] Address already in use` and exits 1.
- Static fallback: `/` serves the D2 page (`text/html`), `/sessions.json` the D2 directory (`application/json`), a `viz/` file wins over `discovery/`, missing paths 404, `/../` traversal 404.
- Registry mode adds a live session once its transcript resolves and publishes `session_removed` within one poll of the PID dying (integration test with a real child process in a temp HOME).
- V2 note 1 fixed: the first `agent-name` on a bare session now emits a change. The former xfail is a plain passing test; the fixture event stream is 24 lines with the manager's name change first.
- Nothing under `~/.claude` or `discovery/` is written. Only `viz/watcher.py` changed.

## Tests

`python3 -m pytest tests` runs 164 tests (18 new for V3), all passing, in about 6 s.

- `tests/unit/test_watcher_server.py`: `now_iso`, broadcaster subscribe, publish, unsubscribe, fixture watcher first poll (registration plus 24 replayed changes), one change per appended line, registry name and label in fixture mode, registry mode add, remove, skip without transcript or outside root, republish on identity change, snapshot copy, `serve` parser.
- `tests/integration/test_serve.py`: `serve` as a subprocess on a free port with a temp HOME and temp `viz/` and `discovery/` folders: `/state` shape and headers, `/events` snapshot then change under 1 s then IDLE, SSE headers, static fallback and 404s, registry add and `session_removed`, bind failure exit 1 against a socket the test holds.
- Updated per the builder's request: xfail marker removed, event stream count 24 with the `at: null` name change first.

## Notes, not failures

1. For the manager (also in the builder's Requests): before V4 goes on 4780, stop the D2 server with `discover.py ui --stop` and start `watcher.py serve` in its place. `ui_is_up` fetches `/sessions.json`, which the watcher serves, so `discover.py ui` will not spawn a second server once the watcher holds the port.
2. A live session under the root whose transcript has not been written yet is absent from `/state` until the file appears. Harmless for the fake sessions; a brand-new session shows up a few seconds late.
3. Each SSE subscriber has an unbounded queue. A client that stops reading without closing accumulates frames until the next write fails. Not a concern for one local page.
4. The SSE handler thread only notices a closed client on its next write (a change or the 15 s keepalive). Fine for V4; worth remembering if V6's event log counts subscribers.
