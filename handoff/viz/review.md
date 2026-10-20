# Review: V12 round 2 2026-10-20

PASS

Round 1 items: (1) a failed pure-subscription result now drops the watch for a socket target (`clear_watch` gets the stored PID and matches by resolved PID in both directions through `watched_pid_of`); (2) a watch stored by name is dropped by a socket-quoting notice once the name resolves to that PID. Both tests pass. My round-1 name-watch test also sent a real message with no result, which rightly still counts as an unanswered send under V11; it now uses a pure subscription, and a second test pins that an unanswered send to the name keeps `waiting_on` until it is read.

Round 1 (FAIL) items for the record: tests/unit/test_state_model.py:872 (failed pure subscription left `watching == [2]`) and :968 (name-stored watch survived a socket-quoting notice).

## Verified against SPEC V12

- Fixture (copies under `tests/fixtures/viz/stale_waiting_{manager_41000,builder_41001}.jsonl`, the `Read` path `/Users/someone/…` replaced by `/home/user/path_finder/…` so the sanitization pin holds; otherwise byte-identical to `viz/fixtures/`), fed in time order and through `Watcher.poll_once` and the `state` CLI: end state both IDLE, `watching []`, `waiting_on []`, `inbox 0`; `6f1d3c2a…` READ with `read_at` `13:00:03.600Z` (the attachment's own timestamp, change `source: attachment`); one `idle_notice` READ at 06.200 with summary `fake-builder is idle`; `9a8b7c6d…` FAILED at the delivery-notice enqueue (08.900) with the notice's first line as reason; no PENDING or IN_INBOX left and no record for the pure subscription. Frozen: 03.700 READ with builder inbox 1, 04.500 inbox 0 after the `remove` (the attachment does not decrement, the inbox goes 0 → 1 → 1 → 0); 06.050 manager `watching []` right after the notice enqueue, before the `user` entry; 08.500 builder `waiting_on [41000]`, 08.950 empty.
- Attachment: a `queued_command` attachment with `origin.kind == peer` is the read at `attachment.timestamp` (entry timestamp when missing); a later `user` peer entry for the same `msg_id` keeps the first `read_at` and does not drop the inbox below zero; other attachment types and human-origin queued commands change nothing.
- Idle notice: the enqueue clears the watch by socket address with no message record; the `user` entry creates the notice once (name in the summary, watched session as `from_pid`), a repeat is a no-op; the `user` entry alone clears the watch in both wordings. Round trip in time order: the manager's `waiting_on` now empties at the notice enqueue 04:31:21.038 (re-pinned).
- Pure subscription: no message, `watching [2]`, `waiting_on [2]`, one session change; the `Subscribed —` result with no `msg_id` changes nothing and creates no FAILED record; the notice clears it; a failed result drops the watch and `waiting_on` with one session change.
- Delivery notice: names in `msg_id: …` move only PENDING/IN_INBOX messages to FAILED with the 200-character first line as reason; READ messages and unknown ids are untouched; the sender's `waiting_on` empties; the `user` form is labelled `user · cross-session delivery notice`.
- Live: the running 4780 (already on the new watcher) shows all four path_finder sessions `watching []`, `waiting_on []`, `inbox 0`, 128 READ and 1 FAILED (the dropped 2026-10-08 validator → manager message with the delivery-notice reason), nothing IN_INBOX. The manager has already restarted 4780 on the new watcher.

## Tests

- `tests/fixtures/viz/stale_waiting_manager_41000.jsonl`, `stale_waiting_builder_41001.jsonl` (10 and 14 lines, pinned, sanitization pin extended to them).
- `tests/unit/test_state_model.py`: helpers `socket_idle_notice_text/entry`, `enqueue_text_entry`, `delivery_notice_text/entry`, `attachment_entry`; new `test_queued_peer_attachment_is_the_read_at_its_own_timestamp_without_a_second_inbox_drop`, `test_attachment_without_its_own_timestamp_uses_the_entry_and_other_attachments_are_ignored`, `test_idle_notice_enqueue_clears_the_watch_by_socket_address_and_the_user_entry_records_it_once`, `test_idle_notice_user_entry_alone_clears_the_watch_in_either_wording`, `test_pure_subscription_is_a_watch_only_and_a_failed_result_drops_it`, `test_socket_idle_notice_clears_a_watch_that_was_stored_by_name`, `test_socket_idle_notice_clears_a_name_watch_but_an_unanswered_send_to_that_name_still_waits`, `test_delivery_notice_fails_only_the_named_message_that_is_still_open`, `test_delivery_notice_for_an_unknown_message_changes_nothing`, `test_stale_waiting_fixture_ends_clean`, `test_stale_waiting_fixture_moment_by_moment`, `test_stale_waiting_change_stream_names_the_sources`; the entry_source table gains the delivery notice; `test_round_trip_waiting_on_in_time_order` re-pinned at 21.038.
- `python3 -m pytest tests` → 346 passed (round 2; round 1 was 343 passed, 2 failed).

## Notes

- A delivery notice `user` entry does not set the receiving session WORKING the way an idle notice does; the status catches up on the next assistant entry. Cosmetic.
- An idle notice that arrives as a `queued_command` attachment and then as a `user` entry gets two `idle_notice` records when the attachment's `source_uuid` differs from the entry's `uuid`. Not in the fixture.
- `viz/fixtures/` is gone; the fixture lives only under `tests/fixtures/viz/` (two new untracked files for the manager to commit).
- Docs user items (from ready.md): `docs/cross-session-message-format.md` §4 add the socket-quoting notice wording, the `queued_command` peer attachment as a read, and the delivery notice as a failure; plan §4 note `watching` clears on the notice enqueue; `docs/jsonl-transcript-spec.md` §4.10 can drop the "VERIFY" on peer-origin queued commands.
