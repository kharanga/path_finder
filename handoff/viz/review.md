# Review: V13 2026-10-20

PASS

## Verified against SPEC V13

- Watcher: `describe_tool_use` returns the description (or summary) alone, first line only: `List files`, `V8 assigned`, `Review the diff`, `Restart the watcher on port 4780`; the wire input still fills in when the block has none; a call without a description falls back to `Read viz/web.html`, `Bash python3 -m pytest tests -q` or the bare name, as before. `activity` in the round trip reads `second hello to fake-session-builder` with no prefix, so the row and the node agree.
- Page: `ringSessions` is every session the watcher reports, by PID; the strip lists the same set with plain titles and no dimmed `out` chips. Through the harness: four synthetic sessions with one in-flight message are all nodes from the start (idle, idle with a two-hour-old turn end, working), eleven minutes later the arrow is gone and all four nodes, chips and rows remain; a `session` change for a new PID adds a fifth node; a `session_removed` drops its node and chip. The FAILED arrow still stays until resolved with every session a node.
- Seven-session fixture (`seven_sessions_round`: the V11 six plus `scribe`, whose transcript is only its `agent-name` line) on spare port 4796 (stopped) in headless Chrome at a real 380 px and 720 px viewport: seven nodes from the first poll, `scribe` with the `Idle` pill and a blank line, seven chips and rows, viz-builder's node and row read `Run the whole suite and compare the change counts against the pinned numbers for every fixture` with no `Bash:`, no node/node or node/label overlap, nothing clipped, graph 517 px and 487 px. Screenshot `v13/webseven-narrow.png` in the scratchpad. The harness (estimated heights) agrees for six and seven nodes at 356 px and 720 px, and after an eleven-minute jump every node stays while the arrows go.
- Live `http://127.0.0.1:4780/web` in headless Chrome at 380 px and 720 px: all four sessions under the project root are nodes (manager, discovery-builder, viz-builder, validator), no overlap, the working line on the validator's node shows the full description. 4780 already serves the new page; its `activity` still carries the prefix until the manager restarts the watcher.
- Compact ten-session view: nodes stay 100 × 24 with nine arrows and the same labels as V10; the ring no longer stretches for the 1.6 px compact overlap (the growth loop stops when a step does not reduce the overlap count), and `relaxVertically` nudges those pairs a few pixels apart instead. Pod layout unchanged.

## Tests

- `tests/fixtures/viz/ten_sessions.py`: `seven_sessions_round`.
- `tests/unit/test_state_model.py`: the five `describe_tool_use` cases and the three activity tests re-pinned without the prefix; one new case for a multi-line description.
- `tests/integration/test_web_render.py`: the round-trip reply, ten-session rows and labels re-pinned; `test_ring_drops_sessions…` and `test_watching_keeps…` replaced by `test_every_session_is_a_node_idle_or_not_and_stays_after_ten_minutes` and `test_session_removed_leaves_the_ring_and_unidentified_nodes_are_dashed`; the FAILED-arrow test keeps the third session as a node; the six-session geometry test is now `test_ring_shows_every_word_of_a_long_line_and_grows_without_overlap` over six and seven nodes at 356 px and 720 px (no overlap, inside the graph, labels clear of nodes, every node still there eleven minutes later).
- `python3 -m pytest tests` → 349 passed.

## Notes

- At 356 px the label on the validator → manager arrow (`V10 review: PASS ✓ In inbox`) is hidden by the V8 scorer in the six- and seven-node layouts (it shows on hover); it was shown in the V11 layout because the ring was taller. Same rule as before, different outcome.
- `relaxVertically` moves nodes off the ellipse, so node order around the ring is by PID but heights are no longer symmetric; the title, strip and rows are unaffected.
- A session's node appears when the watcher registers it; a session that exits stays until the watcher's registry poll drops it (`session_removed`), as the SPEC says.
- Docs user items (from ready.md): plan §6 drop the ten-minute ring rule, note that the activity line is the description alone and that the ring relaxes vertically past the growth cap; earlier items unchanged.
