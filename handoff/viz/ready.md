# Ready: V7 2026-10-20

## Done

`viz/web.html`, the compact web window, served by the watcher at `/web` (and `/web.html`). Reads `./state` then `./events` like `index.html`, with the same 2 s `/state` polling fallback. The render logic is ported from `handoff/viz/v7-animation.html` onto the real feed; the look follows `handoff/viz/v7-styles.html` (last three sections).

Layout, top to bottom:

1. **Web.** One node per session in a ring (radius 140 or less so nodes fit the width), the frame-style card: dot, label, status pill (Idle grey, Working and Sending blue), inbox pill, then one line that is the eye + `Watching <label>` while watching, `👁 idle notice` while the eye pulses, or the quoted last line. Two sessions render side by side as the pod (graph 150 px high, arrow arched above the cards). More than eight sessions in the ring switches to compact nodes (dot, name, orange inbox count, blue working ring on the dot; full card on hover). Nodes are dashed when the session has not run `identify`.
2. **Caption.** The transcript entry behind the latest change on the left (`source` from the feed), the pair it belongs to on the right (`from → to` for a message change, the session label otherwise).
3. **Strip.** One chip per session, blue ring on the dot while working, orange count while mail waits. Clicking a chip (or a node) picks that session: its arrows thicken, the others dim; click again to clear. Sessions outside the ring are still in the strip, slightly faded, with the reason in the tooltip.
4. **Toasts.** One per message in flight, newest first, three then `+N more`, with the full first line of the message body. Left edge grey Pending, green In inbox and Read, red Failed. A Read toast dims after 3 s and leaves after 8 s. Idle notices are muted toasts with the eye. Hovering a toast thickens its arrow; hovering an arrow lights its toast.

Arrows: only PENDING (grey), IN_INBOX (green), FAILED (red, stays until a later message on the same pair reaches In inbox or Read), and a 3 s fading flash on READ. Idle notices are never arrows; they pulse the eye on the watching node for 1.2 s. One arrow per (from, to) pair, newest message on top with `+N` for the rest, curved toward the ring centre (opposite directions bend apart), clipped at the card edges with the mock's `exitPt`, label at the curve midpoint with summary and stage. In compact mode only the newest arrow carries a label; the others show it on hover. The newest arrow is thicker.

Horizon: a session with no message in the last 10 minutes leaves the ring and stays in the strip; arrows and toasts only consider messages inside that window too, so stale in-flight rows from old transcripts do not clutter the live view. When no session has a message in the window the ring shows every session, so a fresh start is not an empty box. The page clock is the newest feed timestamp plus wall time since it arrived, so a fixture replay with old timestamps still flashes, pulses, and lingers in real time.

Title bar: `<folder or "all folders"> · N sessions · M working · K in flight`, and a `live` / `reconnecting` indicator.

`viz/watcher.py`:

- `/web` serves `viz/web.html` (`PAGE_ROUTES`).
- Addition from the D4 review: the `discovery/` static fallback is dropped. `STATIC_DIRS` is `(VIZ_DIR,)`, so `/sessions.json` and the identity files are no longer reachable; only `viz/` files plus `/state`, `/events`, `/web`. `IDENTITY_DIR` is still read for labels.

Files: `viz/web.html` (new), `viz/watcher.py`.

## How to test

Fixture replay at `/web`, spare port (4780 is the manager's server):

```
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
R=$(mktemp -d); python3 viz/watcher.py replay $F --out-dir $R --speed 0 --until 2026-10-08T04:31:10.000Z
python3 viz/watcher.py serve --port 4792 --no-log --fixture 32813=$R/32813.jsonl --fixture 33993=$R/33993.jsonl &
open http://127.0.0.1:4792/web
python3 viz/watcher.py replay $F --out-dir $R --speed 1 --after 2026-10-08T04:31:10.000Z
```

Expected in the window, paced as in the transcripts: pod of two cards; `second hello…` grey Pending arrow left to right, manager `Sending` + `Watching fake builder`, grey toast with the message's first line; arrow turns green `✓ In inbox`, builder `Inbox 1`, chip count 1; `✓✓ Read` flash that fades over 3 s, builder `Working` with the quoted body, toast dims; the reply right to left through the same stages; then the eye on the manager card pulses with `👁 idle notice` for about a second, a muted `fake builder idle notice to fake manager` toast, no arrow; the last toast leaves after 8 s and `No traffic` returns. Caption shows the entry and the pair at each step.

Frozen freezes (same `--until` times as the V4+V5 table) screenshotted through a 380 px iframe (headless Chrome will not go narrower than 500): `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/7afbe860-9f28-49e2-be73-7ec9ac066391/scratchpad/web{1,2,3,4,6,8,9}.png`; `weblive.png` is the six-session live view on a spare port with `--root` the project, matching the mock's five-session window (ring of the sessions with recent traffic, in-flight arrows with labels, caption, strip with the inactive fake sessions faded, toasts).

Live deltas and timing: `web_harness.mjs` in the same scratchpad folder runs the page script in Node with a fake clock (`steps` of frames, `advanceMs`, `clickChip`, `hoverToast`) and prints nodes, arrows, labels, chips, toasts, caption, and title. Inputs used: `web_round.json` (the fixture change stream in slices: Pending → In inbox → Read flash present, gone after 3.5 s, toast gone after 8.5 s, reply the same, pulse present then gone after 1.5 s, chip pick) and `web_ten.json` (ten sessions, four with recent traffic in the ring and six faded in the strip, `+1` count on a pair with two in flight, a FAILED arrow that stays until the resend is read, chip pick dims the other arrows, `+1 more` under three toasts). The validator can copy the harness into `tests/page/`.

Suite: `python3 -m pytest tests` → 196 passed, 2 failed, 42 errors. The 42 errors are `tests/unit/test_discover.py` (conftest references `UI_LOG`, which D4 removed from `discover.py`), not viz. The 2 failures pin the dropped fallback: `tests/integration/test_serve.py::test_static_files_fall_back_to_discovery_and_viz_wins` and `tests/unit/test_watcher_server.py::test_serve_parser_defaults` (expects `STATIC_DIRS` to end with `discovery`).

## Requests

- Manager: restart the 4780 watcher (pid 25176) on the new `viz/watcher.py` so `/web` is served and the `discovery/` fallback is gone; then the live look on `http://127.0.0.1:4780/web`.
- Validator: re-pin the two fallback tests (`/sessions.json` now 404, `STATIC_DIRS == (VIZ_DIR,)`); add a route test for `/web`; page tests for `web.html` from the harness above if wanted.
- Docs (user): plan §6 could describe the web window; SPEC V7 entry as written in `handoff/status.md`.
- Unchanged: docs items from V4 to V6.

## Blocked

Nothing.
