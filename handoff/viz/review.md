# Review: V15 2026-10-20

PASS

## Verified against SPEC V15

- Real drag: seven-session fixture on spare port 4796 (stopped), headless Chrome at 380 px over the DevTools protocol. A mouse press that moves 3 px leaves the node alone; past that the viz-builder card follows the pointer (`pinned dragging`, graph class `dragging`) with its `900>901` arrow end moving with it and the graph growing from 518 to 631 px; on release it stays at the drop point as `pinned`, `localStorage["viz-web-pin:901"]` holds the centre, `Reset layout` appears in the caption bar, the node that was under the drop (904) is pushed clear and two neighbours nudge up, the others stay. A click 300 ms after the drop is ignored, a click a second later picks the node. `Page.reload` lands it back at the same spot with the arrow still attached. Clicking `Reset layout` returns it to its ring place (212, 120), removes the key and hides the button. A touch drag (`Input.dispatchTouchEvent`) on discovery-builder pins and saves it the same way. Screenshots `v15/webdrag-{mid,dropped,reloaded}.png` in the scratchpad.
- Through the harness (pointer events with the page's own listeners): the drop pins at exactly start + (dx, dy), the pin stores the rounded centre, the arrow end follows, unrelated nodes keep their automatic places, no node or shown label overlaps after the drop; a press under 4 px is a click (picks, no pin, no storage); a click right after a drop is ignored and one a second later picks; `pointercancel` after a move drops and saves; drops are clamped to the graph's left and right edges and its top, and to the window bottom (900 px window: centre at 900 − h/2) with the graph growing to 912 px; pins are keyed by label, else role, else PID, and other storage keys are untouched; a seeded pin lands the session there as `pinned` and a later session with the same label under a new PID lands there too; an unparseable pin and blocked storage fall back to the automatic place (blocked storage still drags, just does not remember); `Reset layout` clears every `viz-web-pin:` key including a stale one, keeps other keys, returns all seven nodes to their start positions and graph height, and hides; the two-session pod and the compact ten-session pills drag and pin the same way.
- Everything from V7 to V14 still renders the same (the page tolerates the harness having no reset button; the suite was green before the harness grew).

## Tests

- `tests/page/render_web.mjs`: `#reset-layout` fixed element (`hidden`), `getBoundingClientRect`, pointer capture stubs (`captured`), `window.innerHeight` (`windowHeight` input), `localStorage.removeItem/key/length`, `requestAnimationFrame`; steps `pointer` (`pid`, `dx`/`dy` or `moves`, `hold`, `cancel`, `thenClick`), `releaseNode`, `clickReset`; view adds `graphClass`, `resetHidden`, `storage`, node `captured` and `draggable`.
- `tests/integration/test_web_render.py`: `seven_render`, `node_pos`, `path_end`, `pin_keys`; new `test_dragging_a_node_pins_it_and_its_arrow_follows`, `test_a_press_under_four_pixels_is_a_click_and_a_click_right_after_a_drop_is_ignored`, `test_drops_are_clamped_to_the_graph_sides_and_window_bottom_and_the_graph_grows`, `test_pins_are_stored_by_label_then_role_then_pid`, `test_saved_pins_land_a_session_and_a_later_session_with_the_same_label_at_the_same_spot`, `test_reset_layout_clears_every_pin_and_returns_to_the_ring`, `test_pod_and_compact_nodes_drag_too`.
- `python3 -m pytest tests` → 361 passed.

## Notes

- A pin saved below a taller window is clamped up to the current window bottom on reload (the clamp uses `window.innerHeight` minus the graph top), so the same role can land higher on a smaller screen. By design.
- Dropping a pinned node onto an unpinned one pushes the unpinned one vertically and may nudge its ring neighbours; two pinned nodes dropped on each other are left overlapping (both fixed). Acceptable, the user chose both spots.
- Pin keys use the label first, so on 4780 the key is the role (`viz-web-pin:viz-builder`); the fixture sessions have no label or role, so their keys are PIDs.
- Docs user items (from ready.md): plan §6 add dragging, pins keyed by label/role in localStorage, clamping and growth, and Reset layout; earlier items unchanged.
