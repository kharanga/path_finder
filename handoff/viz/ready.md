# Ready: V6 2026-10-08

## Done

- Event log: `serve` appends every change to `viz/events.jsonl` by default, one JSON line per change, the same lines that go out on `/events` (`session`, `session_removed`, `message`), in emission order, flushed per line. `--log PATH` changes the file; `--no-log` turns it off. The log is opened lazily on the first change and closed on exit. All emission goes through one `Watcher.emit` so the log and the SSE subscribers always agree. The file is append-only across runs; a later replay tool can read it line by line (each line is self-describing with `event`, `at`, and the full object).
- Sanitized fixtures: already committed by the validator under `tests/fixtures/viz/` (`round_trip_manager_32813_33993.jsonl`, `round_trip_builder_32813_33993.jsonl`). Checked: no `/Users/khangnguyen` left; `cwd` reads `/home/user/Documents/path_finder/fake_session`. Nothing for me to add there; `tests/` is outside my folder.
- V5 review note 1 (connector label showing the body between the receiver's read and the sender's result): fixed in the model. When a receiver's peer entry arrives for a `msg_id` not yet known, `adopt_pending_send` takes the sender's oldest unmerged PENDING or IN_INBOX row to that receiver, re-keys it to the `msg_id`, and keeps the tool-use mapping so the later tool_result still sets `accepted_at`. The summary, `sent_at`, and `pending_key` are therefore present from the first READ frame, and the transient second row is gone. Snapshots are identical in both feed orders.

Files: `viz/watcher.py`. `viz/events.jsonl` is created at runtime and should not be committed.

## How to test

The log written during V3's test, spare port:

```
L=$(mktemp -d); cp tests/fixtures/viz/round_trip_manager_32813_33993.jsonl $L/m.jsonl; cp tests/fixtures/viz/round_trip_builder_32813_33993.jsonl $L/b.jsonl
python3 viz/watcher.py serve --port 4793 --fixture 32813=$L/m.jsonl --fixture 33993=$L/b.jsonl --log $L/events.jsonl &
sleep 1; curl -s http://127.0.0.1:4793/state | python3 -c "import sys,json; print(len(json.load(sys.stdin)['sessions']), 'sessions')"
echo '{"type":"assistant","timestamp":"2026-10-08T05:00:01.000Z","message":{"content":[{"type":"text","text":"hi"}]}}' >> $L/b.jsonl
sleep 0.6; kill %1
wc -l $L/events.jsonl; tail -1 $L/events.jsonl | python3 -c "import sys,json; e=json.loads(sys.stdin.read()); print(e['event'], e['pid'], e['status'], e['at'])"
```

Expected: `2 sessions`; 26 lines (24 from replaying both fixtures, plus the two session registrations; the count varies with the live registry as in V4); last line `session 33993 WORKING 2026-10-08T05:00:01.000Z`. Running the same again appends 26 more lines (append-only). With `--no-log` no file is written. Without `--log`, the file is `viz/events.jsonl` next to the script.

Label adoption:

```
R=$(mktemp -d); python3 viz/watcher.py replay --fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl --out-dir $R --speed 0 --until 2026-10-08T04:31:11.200Z
python3 viz/watcher.py state 32813=$R/32813.jsonl 33993=$R/33993.jsonl | python3 -c "import sys,json; print([(m['key'][:8], m['stage'], m['summary'], m['pending_key'][:14], m['accepted_at']) for m in json.load(sys.stdin)['messages']])"
```

Expected: one row, `('693b9bd4', 'READ', 'second hello to fake-session-builder', 'pending:toolu_', None)`; the full replay then gives `accepted_at` 2026-10-08T04:31:11.281Z on that same row.

Suite: `python3 -m pytest tests` → 2 failed, 189 passed. Both failures pin the old transient label and flip by design: `test_frame_4_read_connector_shows_body_until_sender_result_merges` (the label is now "✓✓ second hello to fake-session-buil…" at 11.200) and `test_frames_5_to_7_reply_connector_in_both_directions` (at 17.700 the reply label is already "✓✓ Second hi back to fake-session-ma…", the same as at 17.900).

## Requests

- Validator: update the two tests above to the adopted-summary behaviour; the V5 frozen-frame table row for 11.200 now holds as originally written.
- Manager: add `viz/events.jsonl` and `__pycache__/` to `.gitignore` before committing V6.
- Unchanged: port handover (`discover.py ui --stop`, then `watcher.py serve` on 4780, then delete `discovery/index.html`), `discover.py ui` retirement, docs items (§5 enqueue promotion, nine UI flow frames).

## Blocked

Nothing.
