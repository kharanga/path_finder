# Ready: V16 2026-10-21

## Done

Waiting tethers on `viz/web.html`; the watcher is unchanged.

- Source: `activeTetherPairs()` reads `waiting_on` from every session, one pair per (waiter, target). `trackTethers` keeps `tetherSeen` so a tether fades in over `TETHER_FADE_MS` = 500 ms when the pair appears and fades out over the same time when it leaves (reply read, idle notice, message FAILED), then is removed; a pair that comes back mid-fade snaps back. Steady opacity `TETHER_OPACITY` = 0.85.
- Drawing: a `<g id="tethers">` before `<g id="arrows">` in the graph SVG, so tethers sit under the message arrows. Each tether is a thin dashed grey quadratic curve (`stroke #9a9a9a`, 1.4 px, dash 5 4), no arrowhead, hollow circle marker `#mc` at the target end, `pointer-events: none`. The glyph is a `div.tglyph` (the same eye glyph the V5 watching line used) centred on the curve, with the word `waiting` shown on hover (`.ttext`) and a title `<waiter> is waiting on <target>`. Picking a node (click) dims tethers that do not touch it, like arrows.
- Placement: a tether with no message arrow on its pair runs through the V8 scorer (`placeArrow` with the glyph as its label and side offset 0 only), so it avoids nodes, arrow labels, and crossings like any arrow. A tether whose pair has a message arrow (either direction: PENDING, IN_INBOX, FAILED, or a lingering READ) runs beside it: in the ring, `besideArrow` scores candidate curves on both sides of the arrow at three distances starting just past the arrow label's reach across the curve (`curveAtDistance` corrects the control point for the end-point shift so the midpoint lands at the asked distance), plus the free-scorer curve as a fallback, and takes the cheapest; in the pod the tether takes the lane opposite the arrow (lower when the arrow is upper) and the graph grows for it (`podNeedsLowerLane`). Two tethers on a reversed pair get ranks 1 and 2 (one lane step apart).
- Glyph: `placeGlyph` tries positions along the curve (t 0.2–0.8, nearest the midpoint first) and small offsets off the curve (0, ±12 px), penalising nodes, arrow labels, other tethers' glyphs, curve hits, and leaving the graph. A glyph that still has no clear spot (two nodes almost touching) is hidden (`data-clear="0"`) and shows when either node is picked, exactly as V8 hides a crowded arrow label. An arrow label that a tether has to cross (no clean lane in a tight ring) is hidden by the same V8 rule (`hideCrossedLabel`) and shows on hover or pick.
- Tethers follow dragged and pinned nodes because they are computed from `layout.pos` on every render.

Files: `viz/web.html`.

## How to test

Round trip frozen at moments (spare port; 4780 is the manager's):

```
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
S=$(mktemp -d); python3 viz/watcher.py replay $F --out-dir $S --speed 0 --until 2026-10-08T04:31:13.500Z
python3 viz/watcher.py serve --port 4792 --no-log --fixture 32813=$S/32813.jsonl --fixture 33993=$S/33993.jsonl &
open http://127.0.0.1:4792/web
```

Expected: from 10.318 (the send) a dashed tether runs from the manager to the builder in the lower lane under the two cards, hollow circle at the builder's edge, eye at the midpoint, the pod graph grown to 206 px; the message arrow stays in the upper lane. Hover the eye: `waiting` appears beside it. At 17.000 a second tether (builder → manager) sits one lane lower while the reply arrow is above; at 17.700 only the manager's tether remains; at 21.100 (idle notice read) it is gone, after a 500 ms fade in the live replay. Six sessions at 380 px (`make_six.py` fixture, `serve … $(cat six_args.txt)`): tethers manager → viz-builder, validator → discovery-builder, discovery-builder → manager; the last runs beside the `D5 ready` arrow on the same pair with its label still shown; no tether, glyph, label, or node overlaps another (the validator ↔ discovery-builder glyph is hidden at 380 px because those two cards nearly touch; it shows when either is picked).

Checked here: `v16timeline.py` (serve-path replay of the nine round-trip moments through the Node harness): tether `32813~33993` present with a clear glyph and the title `fake-session-manager is waiting on fake-session-builder` from 10.5 through 19.8, both tethers at 17.0, none from 21.1; `web_tether_fade.json` harness: opacity 0 → 0.85 over the first 600 ms, a `tasks`-style session frame clearing `waiting_on` takes it 0.85 → 0.425 at +250 ms → gone at +600 ms, picking an unrelated node dims the others; `cdp_check.mjs` (now also checks clear glyphs against nodes, labels and each other, and samples every tether path against nodes and shown labels) reports no problems for six and seven sessions at 380 and 720 px; `websix-tether.png` (380 px), `websix-tether-wide.png`, `websix-tether-wide2x.png` (720 px) show the dashed tethers, circles and eyes beside the arrows.

Suite: `python3 -m pytest tests` → 360 passed, 1 failed, expected pin: `test_reply_on_the_reversed_pair_fades_the_read_arrow_within_600ms_and_takes_the_upper_lane` pins the pod graph at 150 px before the reply; it is 206 px now because the manager's tether occupies the lower lane beside its own arrow (this also removes the 150 → 206 → 150 jump noted on V14 for this scenario, the graph stays at 206 while the wait lasts).

## Requests

- Manager: nothing to restart; the page is served from the file.
- Validator: re-pin the one test; harness needs a fixed `tethers` element (SVG group) and a view of `#tethers` paths and `.tglyph` elements; tests for appear/fade/disappear, the pod lanes, beside-arrow placement in the ring, the hidden glyph and hidden crossed label rules, drag following — my scratchpad has `web_tether_fade.json`, `v16timeline.py`, and the updated `cdp_check.mjs`.
- Docs (user): plan §6 add the tether (dashed, hollow circle, eye, hover text), its lanes and the hide rules.

## Blocked

Nothing.
