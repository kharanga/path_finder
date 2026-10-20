# Ready: V13 2026-10-20

## Done

Every live session is always a node; the activity line never starts with the tool name.

`viz/watcher.py`:

- `describe_tool_use` returns the tool call's `description` (or `summary`) alone: `Restart the watcher on port 4780`, `V13 assigned`. Only a call with neither falls back to the tool name and target (`Read SPEC.md`) or the bare name. `activity` therefore carries no `Bash:` style prefix, so the row and the node agree.

`viz/web.html`:

- `ringSessions()` returns every session the watcher reports, sorted by PID; the V7 ten-minute ring rule and the watching rule are gone. A session is a node from the poll that registers it until the watcher drops it. The strip lists the same set with no dimmed `out` chips (CSS and title removed). Arrows keep their own V7/V8 rules (PENDING, IN_INBOX, unresolved FAILED, READ flash, ten-minute arrow horizon), so `RING_WINDOW_MS` now only bounds arrows.
- Ring geometry fix needed for the full count: with seven nodes two of them sit at the same height on opposite sides and closer than a card width, which no amount of vertical ring growth separates (the V11 loop ran to its 700 px cap and still overlapped). `positionNodes` now grows the ring only while a step reduces the number of overlapping pairs, capped at 2.5 × rx, then `relaxVertically` pushes any still-overlapping pair apart along y (up to 60 rounds, each push half the overlap plus 1 px). Result: six nodes at 380 px fit in a 454 px graph (was 644), seven in 474 px, no overlaps at 380 or 720 px. Pod and compact layouts are unchanged.

Files: `viz/watcher.py`, `viz/web.html`.

## How to test

Seven-session fixture (six from V11 plus `scribe`, whose transcript has only its `agent-name` line and never sends or receives anything), spare port:

```
python3 <scratchpad>/make_six.py $PWD/seven > seven_args.txt      # or any transcript set with one silent session
python3 viz/watcher.py serve --port 4792 --no-log --spec /dev/null $(cat seven_args.txt) &
open http://127.0.0.1:4792/web
```

Expected: seven nodes in the ring from the first poll, `scribe` among them with the `Idle` pill and a blank line, seven chips in the strip, seven rows; viz-builder's row and node read `Run the whole suite and compare the change counts against the pinned numbers for every fixture` with no `Bash:`; the title reads `7 sessions · 3 working · 2 in flight`. Leave it open for more than ten minutes (or jump the page clock in the harness): every node stays; only arrows older than ten minutes go. Live: `http://127.0.0.1:4780/web` shows every session under the project root as a node (four today: manager, discovery-builder, viz-builder, validator); after the 4780 restart the working line shows the description without a prefix.

Checked here: harness (`web_seven.json`): seven nodes and seven chips at the first poll and after an eleven-minute jump (arrows 3 → 0, nodes unchanged), rows and node lines as above, `scribe` blank; `cdp_check.mjs` in headless Chrome: seven nodes at 380 px (graph 474 px) and 720 px (502 px) and six nodes at both widths with no node/node or node/label overlap and no clipped line; `webseven-narrow.png` is the 380 px view; compact ten-session harness unchanged (10 nodes, 9 arrows); pod harness unchanged; the live 4780 page already serves the new file and its DevTools check shows all four sessions as nodes with no overlap (its working line still has the `Bash:` prefix until the restart).

Suite: `python3 -m pytest tests` → 331 passed, 15 failed, all expected pins:

- `tests/unit/test_state_model.py` (8): `test_describe_tool_use` cases and the activity-sequence tests expect `Bash: …` / `SendMessage: …`; the text after the prefix is unchanged.
- `tests/integration/test_web_render.py` (7): `test_ring_drops_sessions_without_recent_traffic_and_falls_back_to_everyone`, `test_watching_keeps_a_session_in_the_ring…`, `test_failed_arrow_stays_past_the_horizon…` expect the old ring membership; the ten-, six- and round-trip tests pin the prefixed line or positions from the old growth loop.

## Requests

- Manager: restart the 4780 watcher on the new `viz/watcher.py` so `activity` loses the prefix; the page change is live already.
- Validator: re-pin the 15; replace the ring-membership tests with "every session is a node, idle or not, ten minutes later too"; add a seven-node geometry case (two nodes at the same height) to the overlap test.
- Docs (user): plan §6 drop the ten-minute ring rule and note the activity line is the description alone.

## Blocked

Nothing.
