# Review: V19 2026-10-21

PASS

## Verified against SPEC V19

- Seven-session fixture set (the V13 scratchpad copies, temp SPEC.md, spare port 4796, stopped) in headless Chrome at 380 × 1400 so the rows are on screen. Mouse: press on the second row (`fake manager`) and move 2 px → nothing; at 6 px the row gets `dragging` (opacity .55, `grabbing` cursor) and the row under the pointer gets `drop-above` with the 2 px blue `::before` line; moving above the first row moves the mark to the first row; the DOM order stays frozen while held; release → order `904, 901, 905, 902, 900, 903, 906`, storage `viz-web-row:904 = 0` only, Reset layout shown, no drag classes left; node positions identical before and after. A click right after the drop does not pick; a click 800 ms later picks and a second unpicks. Reload: the order is kept (and Reset layout is already shown 120 ms after the load). Touch (`Input.dispatchTouchEvent`): the fifth row dragged below the last shows `drop-below` (the `::after` line under the last row) and lands last; ranks 0–6 are saved for every row. Dragging node 901 afterwards leaves the row order alone and pins only the node. Reset layout: the automatic V8 order and the ring positions return, storage is empty, the button hides, title `clear every pinned node and row order and return to the automatic layout`. Screenshots `v19/v19-mid-drag.png`, `v19-dropped.png`, `v19-touch-mid.png`, `v19-touch-dropped.png`, `v19-reset.png` in the scratchpad.
- Tether glyph: computed z-index 4 while hovered, 2 at rest, `tglyph lit` with z-index 4 for both glyphs while their pair is picked; no inline `zIndex` on glyphs. The arrow labels keep their inline z-index (unchanged, not a glyph).
- Through the harness (rows now have index-based rects and typed pointer events): drag start after 4 px, `dragging` / `drop-above` / `drop-below` classes, pointer capture on the dragged row, frozen order while held, drop above the first and below the last, the saved-rank rule (top through the dropped row plus already-ranked rows below), a click right after a drop ignored and a later click picking, `pointercancel` leaving order and storage alone, a non-primary button ignored, node drags and row drags independent, row content unchanged after a drop. Keys by label, then role, then PID; a saved rank orders a reload and a later session with the same label (pid 9 for `b`); `nope`, empty, `1.5` and `-1` are ignored; a new WORKING session lands first among the unplaced rows below the placed ones; with storage blocked the drag still reorders in memory and Reset shows.

## Tests

- `tests/page/render_web.mjs`: rows get index-based `getBoundingClientRect` (40 px pitch, 35 px tall), `captured` and `draggable` in the row view, `dragRow` (`toY`/`toYs`, `hold`, `cancel`, `button`, `thenClick`) and `releaseRow`/`releaseY` steps, `className` in the glyph view; every synthetic pointer event now carries its `type` (the page tells a cancel from a release by it).
- `tests/integration/test_web_render.py`: `test_dragging_a_row_shows_the_indicator_and_drops_it_above_or_below_another_row`, `test_row_order_is_kept_by_label_then_role_then_pid_and_unplaced_rows_follow_the_automatic_order`, `test_row_drag_rules_and_the_glyph_lift_are_in_the_page_css`; the reset test also drags a row and seeds a stale row key; the five tether cases pin `tglyph lit` / `tglyph` with no inline z-index.
- `python3 -m pytest tests` → 405 passed.

## Notes

- Manager/user item from ready.md: `.arow { touch-action: none }` means a touch that starts on a row no longer scrolls the rows list; scrolling works from the list's padding and gaps, and the mouse wheel and trackpad are unaffected. Fine for the spec, but worth knowing on a phone.
- Dropping a row below the last one ranks every row (by the stated rule), after which new sessions follow below all of them until Reset; dropping a row back onto its own slot also saves ranks. Both follow the rule in ready.md.
- The new-session acceptance was checked through the harness only; a served fixture set cannot gain a session mid-run.
- Docs user items (from ready.md): plan §6 add the row order (per-label ranks in localStorage, Reset clears pins and rows); plan tether note: hovered glyphs rise to z-index 4; earlier items unchanged.
