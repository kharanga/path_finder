# Ready: V8 2026-10-20, round 2

## Round 2: review items 1 and 2

1. Pod side: `controlCandidates` now takes `hasReverse`; a lone arrow always arches above the cards, and only the second direction of a pair goes below (as in V7). Frozen at 17.000, 17.600 and 17.700 the reply label sits above the cards, clear of the caption (`web6.png`).
2. Curves through labels and nodes: placement now runs two rounds (`PLACEMENT_ROUNDS`), so every arrow is re-placed against all the others once they are known; a final pass hides any label that another curve still crosses (`labelClear` requires a clean score and no crossing curve); a curve through another node costs `NODE_HIT_PENALTY` 400, above every other cost, and three more pulls (0.95, −0.3, 1.15) give chords near the ring edge room to swing inward. On the ten-session fixture no arrow passes through a shown label or a non-endpoint node, and five labels are shown with zero overlaps (`webten.png`). `test_ten_sessions_arrows_do_not_pass_through_shown_labels_or_other_nodes` passes.

Side effect: the shown-label set on the ten-session fixture changed (five shown: `908>906`, `902>900`, `906>907`, `900>903`, `900>909`); `test_ten_sessions_rows_envelopes_and_label_visibility` pins the old four. Suite: 287 passed, that 1 failed.


## Done

Three changes to `viz/web.html` and one to `viz/watcher.py`.

1. **Activity rows.** The bottom list is one row per session: dot, label, status pill, then one line of activity. Rows are ordered Working first, then by last change (`last_seen_at`), then PID. Clicking a row picks the session like a chip. The watcher now carries an `activity` field on every session in `/state` and on `/events` session changes, plus `activity_at` (the entry that set it), `idle_since` (the last `turn_duration`), and `last_assistant_text`:
   - an assistant entry with tool uses sets `activity` to the last tool use: `"<name>: <description or summary>"` when the input has one (Bash, Agent, SendMessage), otherwise `"<name> <target>"` from the first of `file_path`, `path`, `url`, `skill`, `query`, `pattern`, `to`, `command`, `prompt`, otherwise the bare name (e.g. `Read viz/web.html`, `Bash: Run the suite`, `SendMessage: V8 assigned`);
   - an assistant entry with text only sets `activity` to the first line of that text;
   - `turn_duration` sets `activity` to the first line of the last assistant text and stamps `idle_since`.
   The page shows `activity` when present; otherwise `working` while WORKING, otherwise `idle N min` from `idle_since` (or `last_seen_at`). Only a change in activity emits a session change.
2. **Envelope.** Nodes show `✉ N` (orange) next to the status pill, and in the compact header, instead of the Inbox pill; nothing at zero. N is `session.inbox`, which the model keeps as enqueues − dequeues − removes. The strip chip keeps its orange count.
3. **No overlaps.** Arrows are placed newest first by a scorer: for each pair it tries the ring pulls 0.35, 0.15, 0.55, −0.15, 0.75, 0 (preferred pull first for opposite directions; three lifts for the pod), and for the label seven positions along the curve (t 0.2 to 0.8) times three side offsets (on the curve, ±20 px along the normal). Score = 100 per node or placed label the label box overlaps, 50 per placed curve through the label box, 50 per other node the curve passes through, 50 per placed label the curve passes through, 25 for leaving the graph, 4 per crossing with a placed curve, small costs for distance from the midpoint, side offset, and non-preferred pull. The best candidate is used; a label whose best score still contains an overlap (≥ 50) is hidden and shown on hover of its arrow (`data-clear="0"`). Compact mode no longer hides labels by itself: every label that fits is shown.

Also folded in from the V7 review notes: a FAILED arrow is no longer subject to the 10-minute horizon (stays until resolved, and keeps its two sessions in the ring); the eye glyph has a margin so `👁 Watching …` reads with a space; the toast code (and its unused statement) is gone.

Files: `viz/web.html`, `viz/watcher.py`.

## How to test

Fixture replay, spare port (4780 is the manager's, pid 94758):

```
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
R=$(mktemp -d); python3 viz/watcher.py replay $F --out-dir $R --speed 0 --until 2026-10-08T04:31:10.000Z
python3 viz/watcher.py serve --port 4792 --no-log --fixture 32813=$R/32813.jsonl --fixture 33993=$R/33993.jsonl &
open http://127.0.0.1:4792/web
python3 viz/watcher.py replay $F --out-dir $R --speed 1 --after 2026-10-08T04:31:10.000Z
```

Expected: rows start `Idle · idle 0 min`; the manager row goes `Sending · SendMessage: second hello to fake-session-builder`, then `Working`, then its text `The hello is in …`, then `Idle` with that text; the builder row goes `Working · working` on the read, `Sending · SendMessage: Second hi back …`, then `Idle · Replied to …`. The builder node shows `✉ 1` between the enqueue (10.817) and the dequeue (11.028), the manager node between 17.590 and 17.614; nothing otherwise. (The fake sessions are no longer live, so labels are the names from the transcripts.)

Ten-session layout: `make_ten.py` in my scratchpad writes ten synthetic transcripts (`<scratchpad>/ten/<pid>.jsonl`, pids 900 to 909) with eleven messages across nine pairs (eight in flight, one FAILED, two READ) and tool uses for the activity rows:

```
S=/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/7afbe860-9f28-49e2-be73-7ec9ac066391/scratchpad
python3 viz/watcher.py serve --port 4792 --no-log $(cat $S/ten_args.txt) &
open http://127.0.0.1:4792/web
```

Expected at 380 px: ten compact nodes, nine arrows, four labels shown (`tags done ✓✓ Read`, `V6 review: PASS ✗ Failed`, `V7 ready ✓ In inbox`, `rerun scores ✓ In inbox`), five hidden until their arrow is hovered; no label touches another label or a node. Screenshot: `$S/webten.png` (through the 380 px iframe wrapper). The geometric check in Node (`web_harness.mjs` with `web_ten2.json`, label boxes estimated the same way as in the page) reports `overlaps: 0` for the shown labels against each other and all ten node boxes. Rows list `listings-e6 · Working · Edit scores.py`, `tag-analyzer · Working · SendMessage: tags done`, … , idle sessions last.

Fixture round trip in Node (`web_harness.mjs` with `web_round2.json`): `✉ 1` appears on the builder at the enqueue step and is gone at the dequeue step, likewise on the manager for the reply; the rows change as listed above at each step. Freezes: `$S/web{1,2,3,4,6,8,9}.png`.

Suite: `python3 -m pytest tests` → 239 passed, 13 failed, 7 errors, all expected pins:

- `tests/integration/test_web_render.py` (6 failed, 7 errors): `tests/page/render_web.mjs` reads `#toasts`, which is now `#rows` (`.arow[data-pid][data-status]` with `.dot`, `.name`, `.pill`, `.act`), and the toast assertions. My updated harness (`$S/web_harness.mjs`, reporting `rows`, label `clear`/`left`/`top`, and `hoverArrow`) can replace it.
- Change counts: the activity field adds session changes on assistant text and turn ends, so the fixture round trip now has 32 model changes (34 with registration, 35 with the appended line): `test_round_trip_change_stream`, `test_state_events_stream`, `test_fixture_watcher_first_poll_registers_sessions_and_replays_history`, `test_log_matches_the_stream_for_the_fixture_round_trip`, `test_event_log_written_during_the_v3_style_test`, `test_default_log_is_next_to_the_script_and_no_log_disables_it`.
- `test_turn_duration_sets_idle_only_on_change`: a second `turn_duration` at a new time now emits a change because `idle_since` moves.

## Requests

- Manager: restart the 4780 watcher (pid 94758) on the new `viz/watcher.py` so sessions carry `activity`; the page shows `working` / `idle N min` until the field arrives.
- Validator: re-pin the counts above, replace the web harness and tests for the rows, add `activity`/`idle_since` tests (`describe_tool_use`, text-only entries, turn end).
- Docs (user): plan §4 session fields `activity`, `activity_at`, `idle_since`, `last_assistant_text`; SPEC V8 as written.

## Blocked

Nothing.
