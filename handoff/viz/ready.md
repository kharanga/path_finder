# Ready: V5 2026-10-08

## Done

`viz/index.html`: connectors per plan §6 and the display mapping in `docs/cross-session-message-format.md` §9.

- One straight line per (from, to) pair between capsule centers, carrying the latest message of that pair; older ones open in a side panel when the label is clicked (stage, summary, body, sent / accepted / enqueued / read times). Lines are drawn in an SVG layer beneath the board so they show only in the gap between capsules; labels sit in a second layer above, at the midpoint, with the stage glyph: `…` Pending (dotted grey), `✓` In inbox (blue), `✓✓` Read (green), `✗` Failed (red, reason in the tooltip). Opposite directions are offset so A→B and B→A are both visible. The capsule gap widened to 72 px for the labels.
- Watching: a dotted grey line from the watcher to each PID in its `watching` list, gone when the list empties.
- Idle notice: a dashed grey line with an italic label ("<name> is idle"), shown for 4 s from the moment the `idle_notice` message arrives on `/events`, or on page load when `read_at` is within 4 s of the snapshot's `generated_at`, then removed. This is the one-shot the plan asks for; a refresh later does not resurrect it.
- Legend below the board: Pending, In inbox, Read, Failed, Idle notice, Watching.
- Rendering now coalesces on a zero-delay timer instead of `requestAnimationFrame`, so a background tab keeps applying deltas. The header shows "live · N events" (count of frames received on `/events`), which doubles as a liveness check.
- A message with unresolved `to_pid` falls back to matching `to` against session names and labels on the page.

`viz/watcher.py`:

- `StateModel`: a receiver's peer enqueue now promotes the matched message from PENDING to IN_INBOX (the plan's frame 3: badge plus check). Previously the stage waited for the sender's tool_result, which lands up to half a second later.
- `/events` no longer sends a `Connection: keep-alive` header (HTTP/1.0 stream, read until close).
- `replay --after ISO`: appends only the lines after that time to the existing files without truncating, so a frame frozen with `--until` can be continued and the page sees the rest as live deltas.

Files: `viz/index.html`, `viz/watcher.py`. Nothing else touched.

## How to test

Overnight acceptance (fields for frames 2 to 9 on `/state` and `/events`), spare port, no live sessions:

```
R=$(mktemp -d); : > $R/32813.jsonl; : > $R/33993.jsonl
python3 viz/watcher.py serve --port 4796 --fixture 32813=$R/32813.jsonl --fixture 33993=$R/33993.jsonl &
sleep 1; curl -s -N http://127.0.0.1:4796/events > $R/events.txt &
python3 viz/watcher.py replay --fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl --out-dir $R --speed 10 --max-gap 0.4
sleep 1; kill %2
python3 -c "
import json
fr=[json.loads(f[5:]) for f in open('$R/events.txt').read().split('\n\n') if f.startswith('data:')]
ms=[f for f in fr if f['event']=='message']
need=('key','pending_key','kind','stage','from_pid','to_pid','to','summary','body','reason','sent_at','accepted_at','enqueued_at','read_at')
print(len(ms),'message frames; all fields:',all(all(k in m for k in need) for m in ms))
seq={}
for m in ms: seq.setdefault(m['key'] if m['kind']=='idle_notice' else (m['msg_id'] or m['key']),[]).append(m['stage'])
print(seq)
print([(m['from_pid'],m['to_pid'],m['read_at']) for m in ms if m['kind']=='idle_notice'])"
curl -s http://127.0.0.1:4796/state | python3 -c "import sys,json; print([(m['kind'],m['stage'],m['from_pid'],m['to_pid']) for m in json.load(sys.stdin)['messages']])"
kill %1
```

Expected: 8 message frames, all fields true; stages `pending:toolu_014…` [PENDING], `693b9bd4-…` [IN_INBOX, IN_INBOX, READ] (enqueue, then the sender's result, then the read), `f5ac2c3a-…` [READ, READ] (the manager read the reply at 17.638 before the builder's send result at 17.811, so the receiver creates it as READ and the sender's result merges in), `pending:toolu_01C…` [PENDING], `idle:97bc…` [READ]; one idle notice 33993 → 32813 read at 2026-10-08T04:31:21.055Z; final `/state` has message READ 32813→33993, message READ 33993→32813, idle_notice READ 33993→32813.

Frozen frames on the page (open `http://127.0.0.1:4796/` after each replay; headless Chrome used here since the Claude in Chrome extension is not connected):

| until | expected |
| :- | :- |
| `2026-10-08T04:31:10.500Z` | frame 2: dotted grey line manager → builder, label "… second hello to fake-session-buil…", manager Working and watching |
| `2026-10-08T04:31:11.000Z` | frame 3: blue line, label "✓ second hello…", builder badge 1 |
| `2026-10-08T04:31:11.200Z` | frame 4: green line, label "✓✓ second hello…", builder Working, last line "Hi again from fake-session-manager…" |
| `2026-10-08T04:31:17.700Z` | frames 5 to 7: second green line builder → manager, "✓✓ Second hi back to fake-session-ma…", both Working |
| none | frame 9: both Idle, two green lines, no watching line, no notice |

Frame 8 (the notice) is one-shot and lasts 4 s, so freeze at `2026-10-08T04:31:20.100Z`, open the page, then run the same replay with `--after 2026-10-08T04:31:20.100Z`: the watching line disappears, a dashed line "fake-session-builder is idle" appears builder → manager and fades after 4 s. Headless Chrome cannot show this because its screenshot fires at the load event; it was verified by running the page script in Node over the captured `/events` frames (shim requirements under Requests); seeing it in a real browser is part of the morning live check.

Suite: `python3 -m pytest tests` → 10 failed, 171 passed in 6.24s. The 10 failures are all in `tests/integration/test_page_render.py`: the Node shim in `tests/page/render_page.mjs` predates V5 (Requests). 0 failures elsewhere.

## Requests

- Validator, `tests/page/render_page.mjs`: the page now needs these in the shim: elements for ids `wires`, `tags`, `panel`, `panel-title`, `panel-list`, `panel-close`; `document.createElementNS` and `document.createTextNode`; `setAttribute`, `addEventListener`, `classList`, and `getBoundingClientRect` on elements; a `window` with `addEventListener`; and `setTimeout` instead of `requestAnimationFrame` for render coalescing (so await a timer tick, not `setImmediate`). A working shim that exercises the connectors over the real captured frames: `python3 viz/watcher.py serve --fixture …` plus `curl -N /events` to capture, then feed each frame to `source.onmessage`; expected after the notice frame: lines `connector READ`, `connector READ`, `connector idle_notice`, and after 4 s the notice line is gone. The capsule summary in the shim stays valid; the link text is now "live · N events".
- Validator: the stage promotion on enqueue changes V2's documented transition table (ready.md V2 said IN_INBOX comes from the tool_result only). Any test pinning a PENDING stage between enqueue and tool_result needs updating.
- Docs (user): `docs/plan-visualization.md` §5 stage transitions: add "receiver enqueue → IN_INBOX when still PENDING". `docs/cross-session-message-format.md` §7 already allows it ("enqueue can also confirm arrival").
- Port handover and `discover.py ui` retirement: unchanged from V4's Requests; `discovery/index.html` still to be deleted at handover.
- The nine UI flow frames remain absent from `docs/`; frames 2 to 9 above are derived from §6 and the round-trip timeline.

## Blocked

Nothing. Headless Chrome was used for the visual checks; its screenshots fire at page load, so live-delta behaviour was verified in Node over captured frames rather than in a browser.
