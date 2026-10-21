# Ready: V19 2026-10-21

## Done

Activity rows can be dragged into a viewer's order, the order persists by label, Reset layout clears it, and a hovered tether glyph rises above the arrows.

`viz/web.html`:

- Rows are persistent elements (`rowEls` by PID, like `nodeEls`), updated in place and re-appended in order each render. Each row has `pointerdown`/`pointermove`/`pointerup`/`pointercancel` handlers (`startRowDrag`, `moveRowDrag`, `endRowDrag`) with pointer capture, so mouse and touch both work (`.arow { touch-action: none; user-select: none }`). A drag starts after `DRAG_START_PX` (4 px) of vertical movement; the dragged row gets `.dragging` (dimmed, grab cursor). The drop target is the first other row whose vertical midpoint is below the pointer (`rowDropTargetAt`), marked `.drop-above`; below every row it is the last row marked `.drop-below`. The indicator is a 2 px blue line drawn by `::before`/`::after` in the 5 px gap between rows. While a drag is in progress the DOM order is frozen (reordering would release the pointer capture), so the list only moves on the drop. A click within `CLICK_AFTER_DRAG_MS` of a drag end is ignored, as for nodes, so a drop does not also pick the row. `pointercancel` ends the drag without placing anything.
- Order storage: `ROW_STORAGE_PREFIX = "viz-web-row:"` + `pinKeyOf(session)` (label, else role, else PID; the same key as the node pins) → a whole-number rank. `rowRankOf` reads a saved rank once per PID (`rowLookups`, like `pinLookups`); anything that is not `/^\d+$/` is ignored. `orderedRows()` = sessions with a rank sorted by rank (ties by PID), then the rest in the V8 automatic order (Working first, then last change, then PID). On a drop, `placeRow` takes the displayed order, moves the dragged row to the indicated slot, and saves ranks 0… for every row from the top through the dropped row plus any row below that already had a rank, so rows that were never placed keep following the automatic order below the placed ones and a new session lands among them. A later session with the same label gets the saved rank and so the same slot.
- Reset layout: `resetLayout()` = `clearPins()` + `clearRowOrder()` + render (`removeStoredKeys(prefix)` shared). The button shows while any node on the ring is pinned or any live session has a rank (`hasRowOrder`); title now reads `clear every pinned node and row order and return to the automatic layout`.
- Row content is unchanged (dot, name with owner badge, pill, activity, titles, `work`/`picked`/`tasked` classes). Row drags do not touch `pins`; node drags do not touch `rowRanks`.
- Tether glyph: the inline `style.zIndex` is gone; `.tglyph.lit { z-index: 4 }` (class toggled when the pair is picked) and `.tglyph:hover { z-index: 4 }` now both apply, the resting value stays the `.tglyph` rule's 2. Checked in Chrome: computed z-index 4 while hovered, 2 otherwise.

Files: `viz/web.html`.

## How to test

Seven-session fixture (the scratchpad set from V13; any fixture with several sessions works), spare port (4780 is the manager's), a window tall enough that the rows are on screen:

```
S=$(mktemp -d); cp SPEC.md $S/SPEC.md
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
python3 viz/watcher.py replay $F --out-dir $S --speed 0
python3 viz/watcher.py serve --port 4792 --no-log --spec $S/SPEC.md --fixture 32813=$S/32813.jsonl --fixture 33993=$S/33993.jsonl &
open http://127.0.0.1:4792/web
```

Expected: drag the second row upward; after a few pixels it dims and a blue line appears above the first row; release and the rows swap, Reset layout appears in the caption bar, and `localStorage` holds `viz-web-row:<label of the dragged row>` = `0` (the other row has no rank and follows automatically below). Reload: the order is kept. Drag a node: the rows stay; drag a row: the nodes stay. Click Reset layout: the automatic order returns, the button hides, the keys are gone. With more sessions, drop a row below the last one with a touch (the line appears under the last row) and watch a new session appear below the placed rows.

Checked here: headless Chrome at 380 × 1000 on the seven-session set: mouse press, move, release on a row shows `dragging` on it and `drop-above` on the target, drops and saves ranks, the reload keeps the order, a touch drag (`Input.dispatchTouchEvent`) of the fifth row to below the last shows `drop-below` on the last row and moves it there, node positions are unchanged throughout, a plain click still picks, and Reset layout restores the V8 order with the storage empty. Node harness (scratchpad copy with a `dragRow` step that gives rows index-based rects): drag indicator during a hold, drop above / below, the new-session case (a `session` frame for a new working PID lands at its automatic slot below the placed rows), node drag leaves rows alone, a reload with saved ranks and the same label on a new PID (validator 102 → 202) lands at rank 0, bad stored values (`nope`, empty) are ignored, pointercancel leaves the order alone, reset clears pins and ranks together.

Suite: `python3 -m pytest tests` → 397 passed, 5 failed, all the expected pin: `test_tethers_match_waiting_on_run_clear_of_nodes_and_labels_and_follow_drags_and_picks[*]` reads `glyph["zIndex"]` (inline, now unset; the glyph view returns no key).

## Requests

- Validator: re-pin the glyph test to the `lit` class (`glyph["className"]` or an `eye`-style field; inline `zIndex` is `""`). For row drags through `tests/page/render_web.mjs`: rows need `pointerdown`/`pointermove`/`pointerup`/`pointercancel` listeners driven like the node `pointer` step, and `getBoundingClientRect` on rows; with the shim's zero-height rects every row's midpoint is 0, so a `clientY` below 0 means "above the first other row" and `clientY ≥ 0` means "below the last other row". Index-based rects (for example `top = index * 40`, `bottom = top + 35`) let a test target any slot. The row view can expose `className` (already has it) and the storage keys `viz-web-row:*`.
- Docs (user): plan §6 add the row order (per-label ranks in `localStorage`, Reset clears pins and rows); plan tether note: hovered glyphs rise to z-index 4.
- Note for the manager: `.arow { touch-action: none }` is needed for touch drags, so on a touch screen the rows list scrolls from its padding and gaps rather than from a row; the mouse wheel and trackpad are unaffected.

## Blocked

Nothing.
