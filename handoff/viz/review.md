# Review: V18 2026-10-21

PASS

## Verified against SPEC V18

- Fixture replay (round-trip manager/builder fixtures, `--until 2026-10-08T04:31:11.200Z`, temp copy of SPEC.md, spare port 4796, stopped) in headless Chrome at 380 × 720 and 720 × 600: the pair manager → builder carries a green `READ` arrow (computed stroke `rgb(74, 209, 122)`, marker `#mg`) and, on the lower lane, the waiting tether with computed stroke `rgb(240, 228, 90)`, dash `5px, 4px`, marker `#mc`, opacity 0.85. The `#mc` circle has computed stroke `rgb(240, 228, 90)` and fill `rgb(20, 20, 20)`. The glyph, its `.eye` and its `.ttext` all compute to `rgb(240, 228, 90)`; the eye is a 13 × 13 px inline SVG (static position, inside the `span.eye` box, path stroke and pupil fill both yellow) with no text content. Hover: `waiting` shows (display `block` inside the flex glyph) to the right of the eye, still yellow, glyph 58 px wide, grey hover ring; leaving hides it. Overlap probe: no tether through a node or label, no glyph over a node or label, glyph inside the graph. Screenshots `v18/v18-380.png`, `v18-380-hover.png`, `v18-720.png`, `v18-720-hover.png` in the scratchpad.
- `--yellow: #f0e45a` is distinct from the orange count `#ffb454`, green `#4ad17a`, red `#ff6b6b` and the grey `#8a8a8a`; the old `#9a9a9a` is gone from the page. The node idle-notice eye (`eyeEl(true)`, emoji, blue pulse) is unchanged.
- Through the harness: the glyph's `span.eye` holds an `svg` with `stroke="currentColor"`, `fill="none"`, a `path` and a `circle` filled `currentColor`; `eye` class, `waiting` text and title are as in V16, geometry, fade, lanes, drag and pick tests all unchanged.

## Tests

- `tests/page/render_web.mjs`: `glyphView` gains `eyeText` and `eyePicture` (svg stroke/fill and its parts).
- `tests/integration/test_web_render.py`: `#mc` re-pinned to `stroke="#f0e45a"` and the tether rule to `stroke: var(--yellow)`; new `test_tether_yellow_is_one_root_colour_used_by_curve_circle_eye_and_hover_text` pins `--yellow: #f0e45a` in `:root`, the curve, `.tglyph` colour, no `color` in `.tglyph:hover`, `.tglyph .ttext` or `.tglyph .eye`, the `svg { position: static }` rule, the marker colours, the emoji node eye and the SVG tether eye; the midpoint and multi-tether tests assert the SVG eye.
- `python3 -m pytest tests` → 402 passed.

## Notes

- Pre-existing, not V18: `.tglyph:hover { z-index: 4 }` never applies because the page sets `style.zIndex` inline (2, or 4 when its pair is picked), and inline wins; on hover the glyph stays at z-index 2 (computed `2` in Chrome). The hover text still shows because nothing overlaps it in the fixtures. Worth a builder follow-up if the manager wants hovered glyphs above neighbouring labels.
- Docs user item (from ready.md): plan §6 tether note, grey → yellow (`#f0e45a`); earlier items unchanged.
- The 4780 watcher serves the page from disk, so the yellow tether is already live there.
