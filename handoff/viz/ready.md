# Ready: V12 round 2 2026-10-20

Round 2 fixes the two `clear_watch` items from review.md: the watch is now matched by resolved PID in both directions (`watched_pid_of`): a failed pure-subscription result passes the stored target itself (an int PID for a socket target) and it is removed; a watch stored by name before the session was known is removed by a notice quoting the socket, because the name resolves to that PID at clearing time. The duplicate `viz/fixtures/` folder is deleted; the fixture pair lives in `tests/fixtures/viz/` (validator's copies).

## Done

Stale waiting state. Four causes handled in `viz/watcher.py`; the page is unchanged.

1. Queued peer attachment is the read. `attachment` entries were kept by the tailer but had no handler. `StateModel.apply_attachment` takes a `queued_command` attachment: with `attachment.origin.kind == "peer"` it runs the same path as a `user` peer entry (`apply_peer_delivery`), so `attachment.origin.msg_id` moves to READ at `attachment.timestamp` (falls back to the entry timestamp), the receiver goes WORKING, and nothing touches the inbox; the `queue-operation remove` that follows in the transcript is what decrements it, as before. `read_at` is set only once, so a later entry for the same `msg_id` cannot move it. A queued attachment whose prompt is an idle notice or a delivery notice is handled like the matching `user` entry.
2. Idle notice clears the watch. `clear_watch(pid, watched)` takes a PID or text (`uds:/tmp/cc-socks/<pid>.sock` or a name), resolves it to a PID (`watched_pid_of`), and drops every `watching` entry that is the same text, the same bare name, or resolves to the same PID. It runs on the `queue-operation enqueue` of the notice and on the `user` entry, whichever comes first (the second is a no-op). The notice record (`kind: idle_notice`, keyed by uuid) is still created once on the `user` entry, with the watched session's name in the summary when known.
3. Pure subscription is a watch only. `apply_send` with `notify_when_idle` and no `message` adds the watch (`add_watch`) and remembers the tool use in `pure_watch_by_tool_use`; no message is created, so nothing can go PENDING or FAILED. `apply_send_result` for that tool use removes the watch if `success` is false and otherwise does nothing.
4. Delivery notice fails the message (found on the live registry, not in the spec). A `[Cross-session delivery notice] Do not resend now: … (recipient: …; msg_id: <id>) and NOT delivered …` in the sender's transcript (enqueue, `user` entry, or queued attachment) moves each named `msg_id` that is still PENDING or IN_INBOX to FAILED with the notice's first line as `reason` (`apply_delivery_notice`). Without this one 12-day-old dropped message kept the validator `waiting on manager` forever, and its enqueue claim had been stolen from the validator's re-send. `entry_source` labels the `user` form `user · cross-session delivery notice`.

`waiting_on` (V11) is unchanged and now empties as those events arrive.

Fixture: `tests/fixtures/viz/stale_waiting_manager_41000.jsonl` and `tests/fixtures/viz/stale_waiting_builder_41001.jsonl`, synthetic and sanitized (fake names, fake session ids, fake cwd), built with `make_stale.py` from my scratchpad using the field shapes of the real 2026-10-08/10-20 captures: a pure subscription with its `Subscribed —` result and no `msg_id` (13:00:01), a message delivered as a `queued_command` peer attachment with `enqueue` at the same timestamp and `remove` later (13:00:03.6 / 04.0), an idle notice in the new wording quoting the socket address as `enqueue`, `dequeue`, `user` (13:00:06.0–06.2), and a dropped message with its delivery notice (13:00:08.0–09.0).

Files: `viz/watcher.py`.

## How to test

Replay the fixture (spare port; 4780 is the manager's):

```
F="--fixture 41000=tests/fixtures/viz/stale_waiting_manager_41000.jsonl --fixture 41001=tests/fixtures/viz/stale_waiting_builder_41001.jsonl"
python3 viz/watcher.py state 41000=tests/fixtures/viz/stale_waiting_manager_41000.jsonl 41001=tests/fixtures/viz/stale_waiting_builder_41001.jsonl | python3 -c "import sys,json; s=json.load(sys.stdin); print([(x['pid'], x['status'], x['watching'], x['waiting_on'], x['inbox']) for x in s['sessions']]); print([(m['key'][:8], m['kind'], m['stage'], m['read_at'], (m['reason'] or '')[:40]) for m in s['messages']])"
S=$(mktemp -d); python3 viz/watcher.py replay $F --out-dir $S --speed 0
python3 viz/watcher.py serve --port 4792 --no-log --fixture 41000=$S/41000.jsonl --fixture 41001=$S/41001.jsonl &
curl -s http://127.0.0.1:4792/state
```

Expected at the end: both sessions IDLE, `watching: []`, `waiting_on: []`, `inbox: 0`; message `6f1d3c2a…` READ with `read_at` `2026-10-20T13:00:03.600Z` (the attachment's timestamp); one `idle_notice` READ at 06.200 with summary `fake-builder is idle`; message `9a8b7c6d…` FAILED with reason starting `[Cross-session delivery notice] Do not resend now`; no other message, so the pure subscription left no PENDING or FAILED record. Frozen with `replay --until`: 13:00:03.700 shows the message READ and the builder inbox 1 (the `remove` at 04.0 takes it to 0); 13:00:06.050 (the notice enqueue, before the `user` entry) shows the manager `watching: []`; 13:00:08.500 shows the builder `waiting_on: [41000]` and 13:00:08.950 (the delivery-notice enqueue) shows it empty.

Live: after the 4780 restart, `curl -s http://127.0.0.1:4780/state` shows `waiting_on: []` for every session that has no open subscription or unanswered send, no IN_INBOX message older than the receiver's last turn, and the dropped 2026-10-08 validator → manager message as FAILED.

Checked here: the moment-by-moment replay above through `Watcher.poll_once` (serve path) prints exactly those states; `state --events` on the fixture shows the watch cleared on the enqueue and the attachment emitting the READ change with `source: attachment`; the patched watcher run in-process against the live registry (same thing `serve` does, read-only) shows `waiting_on: []` and `watching: []` for all 8 live sessions, 0 unresolved messages, 1 FAILED (the dropped one), where the running 4780 watcher at the same moment showed the manager watching 3 sessions, 12 messages stuck IN_INBOX, and 4 of 4 path_finder sessions waiting on someone.

Suite: `python3 -m pytest tests` → 344 passed, 1 failed: `tests/unit/test_state_model.py::test_socket_idle_notice_clears_a_watch_that_was_stored_by_name`. Its first half passes (`watching == []` after the socket notice). Its second half expects `waiting_on == []`, but the test's `send_entry` carries the default body `"b"` and never gets a `result_entry`, so that message stays PENDING to `later-named` and counts as waiting under the V11 rule. With `body=None` (a pure subscription, which is what the name-stored watch case is about) or a result plus a read, the watcher gives `[]`.

## Requests

- Manager: restart the 4780 watcher on the new `viz/watcher.py`; the stale `waiting on` lines and stuck IN_INBOX arrows clear on the first poll.
- Validator: adjust `test_socket_idle_notice_clears_a_watch_that_was_stored_by_name` as above (or tell me if a PENDING send with no result should not count as waiting, which would be a V11 rule change for the manager to decide).
- Docs (user): `docs/cross-session-message-format.md` §4 add the socket-quoting notice wording, the `queued_command` peer attachment as a read, and the delivery notice as a failure; plan §4 note `watching` clears on the notice enqueue.

## Blocked

Nothing.
