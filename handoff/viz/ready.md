# Ready: V11 2026-10-20

## Done

Idle sessions show nothing unless waiting; waiting sessions read `waiting on <label>`; nodes grow to show their line in full.

`viz/watcher.py`:

- Every session carries `waiting_on`: a list of PIDs, each once, in `/state` and on every `session` change. A PID is in it while the session holds an idle-notice subscription for that session (`watching`, resolved to a PID through the name map) or has a message to that session still `PENDING` or `IN_INBOX`. `StateModel.refresh_waiting` recomputes it after every applied entry (`waiting_targets`), so it clears when the idle notice is read (`watching` drops the target) or the message reaches `READ` or `FAILED`, and the session change is emitted only when the list changes. Order: watched targets first, then unanswered sends by `sent_at`.

`viz/web.html`:

- `activityOf(session)`: `waiting on <label>[, <label>]` when `waiting_on` is non-empty (label, else role, name, or `pid N`); otherwise the V8 line for a working session (`activity`, else `working`); otherwise an empty string. Used for both the activity row and the node line. No `idle N min`, no stale tool name, no quoted last message; the Watching line and the client-side last-line derivation are gone (`lastLineOf`, `latestReadBy` removed). The idle-notice eye still flashes for 1.2 s when a notice is read.
- Node line (`.last`) wraps (`white-space: normal; overflow-wrap: anywhere`), never truncated or clipped; working nodes get `.work` so the line is bright like the working row. Node width is 116 px, up to 160 px on wide graphs (`floor(W/3) − 10`); height is whatever the content needs.
- Layout now runs in three steps in `render()`: `layoutNodes` picks compact/pod and the card width, `renderNodes` builds the content, `measureNodes` reads each node's `offsetHeight` (falls back to a text-length estimate when there is no layout engine), `positionNodes` places them. Ring: rx as before, ry starts equal and grows in 8 px steps until no two cards (plus 4 px) overlap; the graph height grows to fit (`graph.style.height`), the ring is centred the way it was. Pod: the arrow lift grows with the tallest card and the graph with it. Arrow start/end clipping (`exitPoint`) and the label scorer's node rectangles use each node's measured size. Compact nodes (more than eight) are unchanged (100 × 24, line hidden).
- Everything else (strip, caption, panel, folders, tasks, highlights) is unchanged.

Files: `viz/watcher.py`, `viz/web.html`.

## How to test

Round trip on a spare port, frozen at a moment (4780 is the manager's):

```
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
S=$(mktemp -d); python3 viz/watcher.py replay $F --out-dir $S --speed 0 --until 2026-10-08T04:31:13.500Z
python3 viz/watcher.py serve --port 4792 --no-log --fixture 32813=$S/32813.jsonl --fixture 33993=$S/33993.jsonl &
curl -s http://127.0.0.1:4792/state | python3 -c "import sys,json; print([(s['pid'], s['status'], s['waiting_on']) for s in json.load(sys.stdin)['sessions']])"
open http://127.0.0.1:4792/web
```

Expected by moment (replay `--until`): 10.000 both idle, rows and node lines blank. 10.500 manager `Sending`, row and node `waiting on fake-session-builder`, `waiting_on: [33993]`. 13.500 manager `Idle`, still `waiting on fake-session-builder` (the notify subscription is open), builder `Working | working`. 17.000 builder `Sending | waiting on fake-session-manager`, `waiting_on: [32813]`. 17.700 the manager read the reply: builder `Working | SendMessage: Second hi back to fake-session-manager`, `waiting_on: []`; manager still waiting on the builder. 19.800 builder `Idle` with a blank row and node line. 21.100 the idle notice is read: manager `waiting_on: []`, row shows its last text, node flashes the eye. 23.300 both idle, both blank.

Six sessions, long line, 380 px: generate the fixture with `make_six.py` from my scratchpad (or any six-session transcript set where one working session's last tool use has a long description), serve it, open `/web` at 380 px: six nodes in the ring, viz-builder's node shows `Bash: Run the whole suite and compare the change counts against the pinned numbers for every fixture` on seven lines, nothing truncated, no card over another card or over a shown label, tag-analyzer (idle, never sent) blank on node and row, manager and validator `waiting on …`.

Checked here: `v11timeline.py` (replays each moment above through `Watcher.poll_once` and runs the page in the Node harness) prints exactly the rows and node lines listed; `webv11_{a,b,c,d}.png` are the 13.5 / 17.0 / 19.8 / 23.3 frames at 380 px; `cdp_check.mjs` drives headless Chrome over the DevTools protocol at a real 380 px and 720 px viewport against the six-session fixture and reports no node/node overlap, no node/label overlap, no clipped line, all nodes inside the graph (graph grows to 644 px at 380 px, 552 px at 720 px; viz-builder's card 116 × 164 and 138 × 134); `websix-{narrow,wide}.png` are those views. Compact ten-session harness run unchanged (10 nodes, 100 px, 9 arrows).

Suite: `python3 -m pytest tests` → 303 passed, 19 failed, all expected pins:

- `tests/integration/test_web_render.py` (12): idle rows and node lines are now `""` (no `idle N min`, no `idle`, no last text), the Watching line is gone, working nodes carry the `work` class, pod/ring positions follow measured sizes (the harness has no layout engine, so the page estimates heights from the line length).
- Change counts (`test_state_model.py::test_round_trip_change_stream` 27→29, `test_state_cli.py::test_state_events_stream` 28→30, `test_watcher_server.py` ×3 and `test_serve.py` ×2 at +2): two more `session` changes in the round trip, one when `waiting_on` is set at the send and one when it clears at the read.

## Requests

- Manager: restart the 4780 watcher on the new `viz/watcher.py` so `/state` carries `waiting_on`; until then the page shows blank idle lines and working lines but never `waiting on`.
- Validator: re-pin the 19 tests; add tests for `waiting_targets` (subscription, pending send, in-inbox send, cleared on READ, FAILED, and idle notice; unresolved names skipped; each target once), the page `activityOf` cases (waiting beats working, idle blank, working line), and a six-session overlap check (the page's `data-line` plus estimated heights in the harness, or `cdp_check.mjs` from my scratchpad for a real browser).
- Docs (user): plan §4 add `waiting_on`; plan §6 note the blank idle line, `waiting on`, and the growing ring.

## Blocked

Nothing.
