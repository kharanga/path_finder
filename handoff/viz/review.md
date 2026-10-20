# Review: V11 2026-10-20

PASS

## Verified against SPEC V11

- Watcher: every session carries `waiting_on` in `/state` and on `session` changes. A PID is listed while the session holds a `notify_when_idle` subscription for it (`watching`, names resolved through the name map) or has a message to it still `PENDING` or `IN_INBOX`; it leaves the list when the idle notice is read or the message reaches `READ` or `FAILED`. Each target appears once, watched targets first, then unanswered sends by `sent_at`. An unresolved name is skipped until the name is learned. `refresh_waiting` runs after every applied entry and emits a session change only when a list changes. Round trip in time order: the manager reads `[33993]` from its send at 10.318 through the idle notice at 21.055, then `[]`; the builder reads `[32813]` from its send at 16.750 until the manager reads the reply at 17.638, then `[]`.
- Page through the Node harness, round trip cut by cut: both blank at the start; from the send the manager row and node read `waiting on fake builder` (Sending, then Working, then Idle after its turn end, still waiting on the open subscription); the builder reads `working` while it works, `waiting on fake manager` from its send until the manager reads the reply, then its `SendMessage: Second hi back …` line, then blank once idle; after the idle notice the manager shows its last text while working and both go blank at the end. Idle rows and nodes show no `idle N min`, no stale tool name, no quoted message, and stay blank as the clock advances. Working nodes carry `.work`; the idle-notice eye still pulses.
- Six sessions (fixture `six_sessions_round`: manager waiting on viz-builder with a subscription, validator with a send in the manager's inbox, viz-builder working with a 94-character Bash description, discovery-builder idle after one received message, fake pair idle): headless Chrome over the DevTools protocol at a real 380 px and 720 px viewport on spare port 4796 (stopped) reports no node/node overlap, no node/label overlap, no clipped or overflowing line and every node inside the graph; viz-builder's card shows every word on seven lines (116 × 164 at 380 px, 138 × 134 at 720 px), the graph grows to 643.5 px and 552 px, discovery-builder's node and row are blank, manager and validator read `waiting on …`. Screenshots `v11/websix-narrow.png` and `v11/websix-wide.png` in the scratchpad. The harness (estimated heights) agrees: no overlap at 356 px (graph 551.5 px) or 720 px (460 px).
- Compact ten-session view: nodes stay 100 × 24 with the line hidden, nine arrows, geometry pins pass. The ring is 16 px taller than before (ry grew once because adjacent compact pills overlapped by 1.6 px with the 4 px gap), which swaps one shown label (`901>900` shown, `900>909` hidden). Still clean.
- Panel, folders, tasks, strip, caption, envelope unchanged.

## Tests

- `tests/page/render_web.mjs`: nodes expose `line` (`data-line`), the view exposes `graphHeight`; no layout engine, so the page's own height estimate is exercised.
- `tests/unit/test_state_model.py`: change count 29, manager inbox sequence, `waiting_on` on the first change; new `test_waiting_on_holds_a_notify_subscription_until_the_idle_notice`, `…_holds_a_plain_send_until_it_is_read`, `…_clears_when_the_send_fails`, `…_skips_an_unresolved_name_until_it_is_learned`, `…_lists_each_target_once_watched_first_then_sends_by_time`, `…_is_not_re_emitted_when_unchanged`, `test_round_trip_waiting_on_in_time_order`.
- Count pins: watcher first poll `2 + 31` (time order adds one change, the builder's clear at 17.638; the unit feed order adds two), log 33 and 66 after the appended second run, tasks test `3 + 31`, serve `2 + 31 + 1` and 33, state CLI 30.
- `tests/integration/test_web_render.py`: twelve re-pins (blank idle lines, `waiting on`, `.work`, pod tops, ten-session rows and labels), `test_idle_rows_stay_blank_however_long_the_session_has_been_idle`, new `test_activity_line_waiting_beats_working_and_idle_is_blank`, `test_waiting_label_falls_back_to_role_name_or_pid`, `test_six_sessions_show_every_word_of_a_long_line_and_the_ring_grows_without_overlap` (narrow and wide).
- `tests/fixtures/viz/ten_sessions.py`: `send(..., notify=)`, `six_sessions_round`, `LONG_DESCRIPTION`.
- `python3 -m pytest tests` → 333 passed.

## Notes

- Waiting beats working: a working session with an open subscription or an unread send shows `waiting on …` instead of its tool line (the ten-session fixture's listings-e6 shows `waiting on listings-bc` rather than `Edit scores.py`; the manager shows `waiting on fake builder` while it reads the reply at 17.6). This follows the SPEC's definition of waiting; the activity line is still in the row tooltip only when not waiting.
- A session waiting on a PID that is no longer a live session shows the bare number (`waiting on 9`); an unresolved target name is skipped entirely until the name is learned, and a name learned through registration shows up on the next applied entry.
- The page's height estimate (used only without a layout engine) counts the activity line, not the `idle notice` flash text, so the harness grows a pod graph during the flash; a real browser measures the rendered card.
- The 4780 watcher still runs the pre-V11 `viz/watcher.py`, so its page shows blank idle lines and working lines but never `waiting on` until the manager restarts it (builder request).
- Docs user items: plan §4 add `waiting_on`; plan §6 note the blank idle line, `waiting on`, the growing ring and graph height; earlier items unchanged.
