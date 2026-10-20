# Review: V8 2026-10-20 (round 2)

PASS

## Round 2

- Item 1 fixed: `controlCandidates` takes `hasReverse`, so a lone pod arrow arches above the cards and only the second direction of a pair goes below. Frozen at 17.000, 17.600 and 17.700 the reply label box lies inside the graph above the cards, clear of the caption (`web6.png`, `web7.png`). `test_pod_labels_stay_inside_the_graph` passes at all five pod freezes.
- Item 2 fixed: two placement rounds, a final pass that hides any label another curve still crosses, a 400 cost for a curve through a non-endpoint node, three more pulls. On the ten-session fixture no arrow passes through a shown label or another node, shown labels are clear of each other and of every node, and five labels are shown (`908>906`, `906>907`, `900>903`, `900>909`, `902>901`) with four hidden until hovered. `test_ten_sessions_arrows_do_not_pass_through_shown_labels_or_other_nodes` and the label-clearance test pass; the shown-label pin re-pinned to the new set (`webten.png`).
- `python3 -m pytest tests` → 288 passed. Only `viz/web.html` changed this round.

## Verified in round 1 (unchanged)

- Watcher: every session in `/state` and on `/events` carries `activity`, `activity_at`, `idle_since`, `last_assistant_text`. A tool use sets `activity` to `"<name>: <description or summary>"` or `"<name> <target>"` or the bare name, the last tool use in an entry wins, a text-only entry sets the first line, `turn_duration` stamps `idle_since` and falls back to the last assistant text, and only a change emits a session change. Fixture round trip: the manager's activity goes SendMessage → "The hello is in …" → "The reply came back …" → "The builder is idle again …" with `idle_since` 13.415, 20.055, 23.218; the builder ends on "Replied to …" with `idle_since` 19.753. Inbox stays enqueues − dequeues − removes.
- Page, fixture replay at `/web` frozen on port 4796 (stopped) and through the fake-clock harness: rows start `Idle · idle`; the manager row goes `Sending · SendMessage: second hello …`, `Working`, then `Idle · The hello is in …` (140 chars then `…`, tooltip with the full line and `activity_at`); the builder row `Working · working` on the read, `Sending · SendMessage: Second hi back …`, `Idle · Replied to …`; rows ordered Working first then by last change; clicking a row picks the session. `✉ 1` with tooltip `1 queued message` on the builder node between 10.817 and 11.028 and on the manager between 17.590 and 17.614, nothing otherwise; the strip count matches. The stream render equals the frozen render at four cuts. Screenshots: `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/9e6343e0-d664-4782-b79a-a6cac9debb65/scratchpad/web{2,3,4,6,7,9}.png`, `webten.png`.
- Ten-session fixture: ten compact nodes with `✉ 1` on manager, viz-builder, validator, discovery-builder and `✉ 2` on listings-bc; nine arrows (seven In inbox, one Failed, one Read flash); rows `listings-e6 · Working · Edit scores.py`, `tag-analyzer · Working · SendMessage: tags done`, … idle sessions last with `idle 0 min`; title `10 sessions · 6 working · 8 in flight`.
- V7 notes folded in: a FAILED arrow outlives the horizon until a resend lands, the eye glyph has its margin, the toast code is gone.

## Tests

- Count pins: `test_round_trip_change_stream` 27, `test_state_events_stream` 28, first poll `2 + 30`, event log 32 and 64, V3-style serve `2 + 30 + 1`, default log 32.
- `test_turn_duration_sets_idle_and_idle_since_only_on_change` replaces the old turn-end test.
- `tests/unit/test_state_model.py`: 16 `describe_tool_use` cases, `first_line`, tool-use activity, last tool use wins, text-only entries, turn end to last text, default fields, the fixture activity sequence.
- `tests/fixtures/viz/ten_sessions.py`: deterministic ten-session transcript generator (synthetic, no real paths).
- `tests/page/render_web.mjs`: rows instead of toasts, `clickRow`, `leavePath`, label `clear`/`zIndex`, node `mail`.
- `tests/integration/test_web_render.py`: 19 tests including the pod-bounds and ten-session geometry checks.

## Notes

- The geometry check uses the page's own estimates (label width from character count, node height 24 in compact mode), not rendered boxes; the screenshots agree with it.
- While a session is WORKING before its first assistant entry of the turn, the row shows the previous turn's text. Allowed by SPEC; mentioned for the live look.
- Fixture labels are the transcript names (`fake-session-manager`) since the fake sessions are no longer live; expected.
- Docs user items: plan §4 session fields `activity`, `activity_at`, `idle_since`, `last_assistant_text`; plan §6 the rows, envelope and placement.
