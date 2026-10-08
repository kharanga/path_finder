# Review: V4+V5 rework 2026-10-08 (round 2)

PASS

## Round 2

- Round 1 item 1 (frozen-frame caption followed file order) is fixed: `Watcher.poll_once` applies the entries from every tailer in one timestamp-ordered pass, timestamp-less lines inheriting the previous timestamp in their file and remembered across polls. Re-frozen all eight times on port 4795 (stopped): the newest `seq` in `/state.sources` now gives frame 4 `system · turn_duration`, frame 6 `queue-operation · enqueue`, frame 7 `system · turn_duration`, frame 9 `system · turn_duration`; frames 1, 2, 3, 5 unchanged (`registry`, SendMessage, enqueue, SendMessage). `/state` sessions and messages at every freeze still match ready.md's table.
- First-poll change stream for the two fixtures is now 28 (2 registry + 26), the same sequence, change for change, as feeding the fixtures through `StateModel` in time order; every `at` in it is non-decreasing. The reply's enqueue is its own `IN_INBOX` change and the sender's results come after the reads, as they do live.
- Count pins re-pinned (26→28, 52→56, 2+24+1→2+26+1) in `tests/unit/test_watcher_server.py` and `tests/integration/test_serve.py`. New: `test_first_poll_applies_both_files_in_timestamp_order`, `test_timestamp_less_lines_inherit_the_previous_timestamp_in_their_file_across_polls`.
- `python3 -m pytest tests` → 237 passed.

## Verified in round 1 (unchanged, `viz/index.html` untouched this round)

- The eight freezes from ready.md rebuilt and `/state` matches the table at every one: frame 1 both IDLE, no messages; 2 manager WORKING watching 33993, first message PENDING; 3 builder inbox 1, IN_INBOX; 4 manager IDLE, builder WORKING, READ; 5 reply PENDING, builder WORKING; 6 manager inbox 1, reply IN_INBOX (the `apply_send` claim); 7 reply READ, manager WORKING, builder IDLE; 9 both IDLE, watching cleared, idle notice READ. `/state` keys are `generated_at`, `sessions`, `messages`, `sources`; every `/events` change carries `source` and `source_pid`.
- Headless Chrome works here with `--timeout=2500`. Screenshots of my freezes: `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/9e6343e0-d664-4782-b79a-a6cac9debb65/scratchpad/freeze{1,2,3,4,5,6,7,9}.png`. Against `handoff/viz/ui-frames.png`: cards, dots, pills, eye line, quoted last line, connector summary, bold arrow, stage colours and `No traffic` match frames 1 to 6. Differences are under Notes.
- The page script renders frames 2 to 9 from the change stream identically to the frozen snapshots, the idle-notice line shows for 4 s and on a snapshot loaded within 4 s of `read_at`, the pair panel lists both messages newest first, non-neighbour pairs get tiered clickable arcs, FAILED shows `✗ Failed` with the reason in the tooltip, unidentified sessions are dashed, `session_removed` drops the card and its caption source, a `snapshot` event replaces state, a stream error switches to polling.

## Tests

- `tests/page/render_page.mjs` replaced (based on the builder's `smoke_page.mjs`, plus `error`, `closePanel`, `clickArc`, `updated`, `linkClass`, `eventsUrl`, `fallbackPolls`, stage tooltips, arc geometry).
- `tests/integration/test_page_render.py` rewritten for the new DOM: 29 tests.
- `tests/unit/test_state_model.py`: 23 new (every `entry_source` label, `source`/`source_pid` on changes, `sources` in the snapshot, `note_source`, the `apply_send` enqueue claim in three variants, the receiver-first replay freeze).
- `tests/unit/test_watcher_server.py`: snapshot keys include `sources`; registry changes and `session_removed` carry `source: registry`; source row dropped on removal; first-poll ordering tests.
- `tests/fixtures/` unchanged. No home paths or user names in any new test file.

## Notes

- Differences from `ui-frames.png` that the fixture cannot reproduce and the page does not try to; for the user to rule on: frame 1 caption is `registry` (image: `agent-name · permission-mode`; the fixture's agent-name entries change nothing and it has no permission-mode entries); frame 2 shows `Watching fake builder` already (image: from frame 3; `notify_when_idle` is known at send time); frame 3 caption `queue-operation · enqueue` (image joins two entries, `toolUseResult.success · enqueue`; the result lands at 11.281, after the read at 11.097); frame 4 at 13.500 shows the manager `Idle` as in the image but the caption is `system · turn_duration`, since no single time gives both. The image's labels and summaries are shortened mock text; the fixture's are longer.
- Sorting a poll by timestamp also reorders within one file where the transcript itself is out of order (the manager fixture has 11.281 before 11.278 and 21.038 before 21.035); only attachment and informational entries are affected and they produce no change.
- Panel times line reads `sent · accepted · enqueued · read`; enqueued precedes accepted in every fixture message. Cosmetic.
- For the manager: the 4781 (or 4780 after the handover) server must be restarted on the new `viz/watcher.py` for captions and `sources`. The `.gitignore` change for `viz/events.jsonl` is still uncommitted.
- Docs user items unchanged from V6; plan §4/§5 should add `sources` and `source`/`source_pid`, plan §6 the frames' look (ready.md Requests).
