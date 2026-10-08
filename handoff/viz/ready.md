# Ready: V4+V5 rework (match handoff/viz/ui-frames.png) 2026-10-08, round 2

## Round 2: review item 1 (caption picked file order, not time order)

Fixed in `viz/watcher.py`: `Watcher.poll_once` now applies the entries gathered from every tailer in one poll in timestamp order (`Watcher.entries_in_time_order`, stable per file, a line without a timestamp inherits the previous one in its file, remembered across polls). The first poll of a frozen replay therefore feeds both files as the live run did, `seq` follows time, and the captions are: frame 4 `system · turn_duration`, frame 6 `queue-operation · enqueue`, frame 7 `system · turn_duration`. Re-frozen all eight freezes on port 4792 (stopped) and checked the newest `seq` in `/state.sources` at each one. `test_first_poll_newest_source_is_the_newest_transcript_entry_across_files` passes.

Side effect for the validator: the first-poll change count for the two fixtures is 28, not 26 (29 with the appended line), because the reply's enqueue at 17.590 now matches the send and is emitted as its own `IN_INBOX` change, and the sender's result at 11.281 and 17.811 is emitted after the read instead of before it. Four count pins flip: `test_fixture_watcher_first_poll_registers_sessions_and_replays_history`, `test_log_matches_the_stream_for_the_fixture_round_trip`, `test_event_log_written_during_the_v3_style_test`, `test_default_log_is_next_to_the_script_and_no_log_disables_it`. Suite: 231 passed, those 4 failed.


## Done

`viz/index.html` rebuilt to the frames' look, one live page whose cards and connector move through the frames over time. Data flow unchanged: `./state` on load, then `./events` SSE deltas, 2 s `/state` polling fallback on stream error.

- Page: near-black background, one row per folder (folder title shown only when there is more than one folder), cards side by side with the connector in the gap between neighbours.
- Card: coloured dot (purple for a role or label containing "manager", green for "builder", otherwise a fixed palette by PID order) then the bold label; a pill row with the status pill (`Idle` grey, `Working` and `Sending` blue) and an orange `Inbox N` pill only when inbox > 0; an eye icon line `Watching <label>` only while watching; the last message line in quotes, clamped to two lines, full text in the tooltip. Dashed border for a session that has not run `identify`.
- `Sending` is derived on the page: status WORKING and the session's latest send still PENDING.
- Last line is derived on the page from the messages, as in the frames: the summary while the session's own latest send is PENDING, nothing once it is accepted or enqueued, the received body after the session reads a message. `session.last_text` is still in the data for anyone who wants the raw value.
- Connector between neighbouring cards: summary on top, bold `→` or `←` from sender to receiver, then the stage: `Pending` grey, `✓ In inbox` green, `✓✓ Read` green, `✗ Failed` red with the reason in the tooltip; `No traffic` grey when the pair has no message. Latest message of the pair in either direction. An idle notice between the pair adds an italic muted line `<name> is idle` under the stage for 4 s (also on load when `read_at` is within 4 s of `generated_at`).
- Pairs that are not neighbours in the row (three or more sessions in a folder) get a thin arc above the cards with the same summary, arrow, and stage; arcs are tiered so they do not overlap. The row scrolls sideways instead of wrapping so arcs stay attached to their cards.
- Caption under each row in muted monospace: the transcript entry that produced the row's latest change, e.g. `assistant → tool_use SendMessage`, `queue-operation · enqueue`, `user · origin.kind = peer`, `toolUseResult.success`, `system · turn_duration`, `user · cross-session idle notice`, `registry` for a registration change.
- Clicking a connector or an arc label opens the side panel with every message of the pair and its timestamps. No legend.

`viz/watcher.py`:

- Every change now carries `source` (the entry label above) and `source_pid` (the transcript it came from). The snapshot carries `sources`: per PID the latest `{pid, at, source, seq}`; `seq` is the emission order, which the page uses to pick the newest caption (timestamps cannot be compared between registry time and fixture time).
- `apply_send` claims a held enqueue for its (from, to) pair and promotes the row to IN_INBOX. Before, when the receiver's file was read before the sender's in the same poll (every `replay --until` freeze does this for the reply), the reply stayed PENDING until the read. Live polling did not hit it because the send lands 800 ms before the enqueue.

Files: `viz/index.html`, `viz/watcher.py`.

## How to test

Frozen frames, spare port (4781 is the manager's server, leave it):

```
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
for T in 10.300 10.500 11.000 13.500 17.000 17.600; do
  R=$(mktemp -d); python3 viz/watcher.py replay $F --out-dir $R --speed 0 --until 2026-10-08T04:31:${T}Z
  python3 viz/watcher.py serve --port 4792 --no-log --fixture 32813=$R/32813.jsonl --fixture 33993=$R/33993.jsonl & sleep 1
  open http://127.0.0.1:4792/   # compare with the frame, then: kill %1
done
```

| Frame | `--until` | Expected on the page |
| :- | :- | :- |
| 1 | 04:31:10.300 | both `Idle`, `No traffic`, caption `registry` (the fixture's agent-name entries change nothing because the registry already knows the names) |
| 2 | 04:31:10.500 | manager `Sending`, `Watching fake builder`, “second hello to fake-session-builder”; connector `second hello… → Pending`; builder `Idle`; caption `assistant → tool_use SendMessage` |
| 3 | 04:31:11.000 | manager `Working` + watching, no quote; `→ ✓ In inbox`; builder `Idle` `Inbox 1`; caption `queue-operation · enqueue` |
| 4 | 04:31:13.500 | manager `Idle` + watching; `→ ✓✓ Read`; builder `Working` “Hi again from fake-session-manager…”; caption `system · turn_duration` (at 11.500 the caption is `user · origin.kind = peer` as in the frame, but the manager is still `Working` until its turn ends at 13.415) |
| 5 | 04:31:17.000 | manager `Idle` + watching; `Second hi back… ← Pending`; builder `Sending` “Second hi back to fake-session-manager”; caption `assistant → tool_use SendMessage` |
| 6 | 04:31:17.600 | manager `Idle` `Inbox 1` + watching; `← ✓ In inbox`; builder `Working`, no quote; caption `queue-operation · enqueue` |
| 7 | 04:31:19.800 | manager `Working` “Hi again from fake-session-builder…”, `← ✓✓ Read`; builder `Idle`; caption `system · turn_duration` |
| 9 | 04:31:30.000 | both `Idle`, no watching line, `← ✓✓ Read` |

Headless screenshots of these eight freezes, 1000 px wide, are in my scratchpad: `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/7afbe860-9f28-49e2-be73-7ec9ac066391/scratchpad/frame{1,2,3,4,5,6,7,9}.png`, plus `live.png` (six real sessions, arcs for the non-neighbour pairs).

Live deltas (headless Chrome only captures page load): `smoke_page.mjs` in the same scratchpad folder runs the page script in Node against a snapshot plus change frames and prints cards, links, arcs, caption, and panel. Fed with the fixture change stream it renders frames 2 to 9 identically to the frozen snapshots, the idle notice line expires after 4 s, and the pair panel lists both messages. The validator may copy it into `tests/page/` as the replacement harness.

Suite after round 1: 20 failed, 181 passed (old page harness and the snapshot-keys pin); the validator replaced those. Suite after round 2: see the top of this file.

## Requests

- Validator: re-pin the four first-poll change counts listed at the top (26 → 28, 27 → 29). Round 1 requests (page harness, snapshot keys, source assertions) are done.
- Manager: restart the 4781 server (or the 4780 one after the handover) so it serves the new page and emits `source`; the page needs the new watcher for captions. Then the user's live look.
- Unchanged: port handover, `discover.py ui` retirement, docs items (plan §6 could now describe the frames' look; the `sources` field and `source` on changes belong in plan §4/§5).

## Blocked

Nothing.
