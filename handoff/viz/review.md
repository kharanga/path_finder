# Review: V16 2026-10-21

PASS

## Verified against SPEC V16

- Round trip through the harness: no tether at the start; from the send a `32813~33993` tether fades in (0 at the frame, 0.848 at the enqueue 0.3 s later, 0.850 from the read on), dashed, hollow-circle marker `#mc` at the builder's end, the eye glyph between the two cards with `waiting` as its hover text and the title `fake manager is waiting on fake builder`; the message arrow keeps the upper lane and the tether the lower, the pod graph grows to 206 px. At 17.0–17.6 both tethers are present one lane apart (24 px) under the reply arrow, both glyphs clear; after the reply is read only the manager's tether remains; at the idle notice it is still 0.850, 0.425 at +0.25 s and gone at +0.6 s; the end state has no tether and the pod is back to 150 px. A synthetic session frame that gains `waiting_on` fades the tether in over 500 ms, one that loses it fades out over 500 ms and removes it, and a pair that comes back mid-fade snaps to full opacity.
- Headless Chrome on spare port 4796 (stopped), six and seven sessions at a real 380 px and 720 px and the pod frozen at 13.5: every tether is dashed (`5px, 4px`), 1.4 px grey, hollow circle at the target end, opacity 0.85; hovering a glyph shows `waiting` (`.ttext` `display: block`) and leaving hides it; sampling every tether path against the cards and the shown arrow labels, and every clear glyph against cards, labels and other glyphs, reports no overlap in any view; the validator → manager tether runs beside the `V10 review: PASS` arrow on the same pair with the label still shown. Screenshots `v16/six-380.png`, `six-380-hover.png`, `six-720.png`, `seven-380.png`, `seven-720.png`, `pod-380.png` in the scratchpad.
- Through the harness on six, seven (both widths) and the compact ten-session ring: the tether set equals the `waiting_on` pairs; no tether runs through a third card or a shown label and no clear glyph overlaps a card, a label or another clear glyph; dragging a node moves its tether end with it and the six/seven layouts stay clear after the drop; picking a node dims every tether that does not touch it and lifts the touching glyphs to z-index 4. Crowded glyphs are hidden (`data-clear="0"`, opacity 0) and shown when their pair is picked, the V8 rule.
- Markup pins: `<g id="tethers">` precedes `<g id="arrows">` so tethers draw under the message arrows; `#tethers path` has `pointer-events: none`; `.tglyph .ttext` is hidden until `:hover`; glyph transitions stop while dragging.
- Message arrows (PENDING, IN_INBOX, FAILED, lingering READ) are unchanged; the V14 reply test only moved its pod-height pins from 150 to 206 px because the manager's tether now holds the lower lane for the whole wait, which also removes the 150 → 206 → 150 jump noted on V14.

## Tests

- `tests/page/render_web.mjs`: fixed `tethers` group; view adds `tethers` (`key`, `d`, `opacity`, `marker`, `className`) and `glyphs` (`key`, `clear`, `opacity`, `left`, `top`, `title`, `zIndex`, `eye`, `text`).
- `tests/integration/test_web_render.py`: two pod-height re-pins; helpers `glyph_rect`, `tether_ends`, `shown_labels`, `assert_tethers_clear`; new `test_waiting_tether_runs_from_the_send_until_the_idle_notice_with_the_eye_at_the_midpoint`, `test_tether_fades_in_and_out_over_half_a_second_and_snaps_back`, `test_tethers_match_waiting_on_run_clear_of_nodes_and_labels_and_follow_drags_and_picks` (six/seven at 356 and 720 px, ten compact), `test_tether_rules_are_in_the_page_markup_and_css`.
- `tests/unit/test_watcher_server.py`: `test_parse_repo_spec_has_every_task_with_a_known_state` now accepts the new P series (owner `null`, area `P`) the SPEC gained today; not a V16 change.
- `python3 -m pytest tests` → 369 passed.

## Notes

- During the 600 ms reply fade in the pod the manager's tether takes the upper lane next to the incoming reply arrow (its own arrow is fading in the lower lane), so for that window the tether and the reply arrow share a curve; once the old arrow is gone the tether returns to the lower lane. Transient.
- In the compact ten-session ring with a node dragged into the middle, one tether (`909~907`) is routed through the `908` pill; the scorer penalises node hits but has no clear lane there. The undragged compact ring is clean; the SPEC's no-overlap rule names the glyph, so this is a note.
- In the harness (estimated card heights) the seven-node wide view hides both glyphs; the real browser at 720 px shows one and hides the other. Hidden glyphs reappear on pick.
- The working tree also carries the discovery-builder's P1 files (`path_finder/`, `pyproject.toml`, `.gitignore`); not part of this review.
- Docs user items (from ready.md): plan §6 add the tether (dashed, hollow circle, eye, hover text), its lanes, the fade and the hide rules; earlier items unchanged.
