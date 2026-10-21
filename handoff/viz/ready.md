# Ready: V18 2026-10-21

## Done

The waiting tether is yellow: the dashed curve, the hollow circle at the target, the eye glyph, and the "waiting" hover text all use `--yellow: #f0e45a`, a lemon yellow that reads on the dark background and sits apart from the orange envelope count (`#ffb454`), the green arrow stage (`#4ad17a`), and the red one (`#ff6b6b`). Nothing else about the tether changes: same geometry, lanes, fade, marker, hover behaviour, dim rule, and grey hover ring.

`viz/web.html`:

- `:root` gains `--yellow: #f0e45a`.
- `.graph #tethers path { stroke: var(--yellow); … }` (was `#9a9a9a`); the `#mc` marker circle stroke is `#f0e45a` (was `#8a8a8a`; markers take literal attributes).
- `.tglyph { color: var(--yellow) }` (was `--win-muted`) and `.tglyph:hover` no longer switches the colour to `--win-fg`, so the hover text "waiting" is yellow too.
- The tether eye was the 👁 emoji, which renders as the Apple Color Emoji bitmap and ignores CSS colour (checked in headless Chrome: U+1F441, U+1F441 U+FE0E, and `font-variant-emoji: text` all draw the brown bitmap). `tetherEyeEl()` now builds a small inline SVG eye (outline plus pupil, `stroke`/`fill: currentColor`) inside the same `span.eye`, so the glyph view in the page tests is unchanged (`eye: "eye"`, `text: "waiting"`). `svgEl(name, attrs)` is the helper. `.tglyph .eye` is a 13 px inline-flex box and `.tglyph .eye svg { position: static; … }` keeps the page's `.graph svg { position: absolute; inset: 0 }` rule from stretching it over the glyph. The idle-notice eye on nodes (`eyeEl(true)`, blue pulse) is untouched; it is not part of the tether.

Files: `viz/web.html`.

## How to test

Fixture replay to the moment the builder has read the send (green Read arrow and a tether on the same pair), spare port (4780 is the manager's):

```
S=$(mktemp -d); cp SPEC.md $S/SPEC.md
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
python3 viz/watcher.py replay $F --out-dir $S --speed 0 --until 2026-10-08T04:31:11.200Z
python3 viz/watcher.py serve --port 4792 --no-log --spec $S/SPEC.md --fixture 32813=$S/32813.jsonl --fixture 33993=$S/33993.jsonl &
open http://127.0.0.1:4792/web
```

Expected: a green arrow with the `✓✓ Read` label runs manager → builder along the top; below it a yellow dashed curve runs manager → builder, ending in a yellow hollow circle at the builder card, with a yellow eye at its midpoint. Hover the eye: "waiting" appears next to it in the same yellow. Everything else is as in V16/V17.

Checked here in headless Chrome at 380 × 720 and 720 × 600: computed `stroke` of `#tethers path` and of the `#mc` circle, and computed `color` of `.tglyph`, its `.eye`, and its `.ttext` (hidden until hover, `block` on hover) are all `rgb(240, 228, 90)`; the arrow on the same pair is `#4ad17a` at stage READ; screenshots show the four parts in yellow; the 380 px overlap probe reports no problems; the glyph layout (eye 13 px, then "waiting") is correct on hover.

Suite: `python3 -m pytest tests` → 400 passed, 1 failed, the expected pin: `tests/integration/test_web_render.py::test_tether_rules_are_in_the_page_markup_and_css` asserts the `#mc` circle `stroke="#8a8a8a"` (now `#f0e45a`).

## Requests

- Validator: re-pin that test to `stroke="#f0e45a"` and pin the colour where the task asks: `--yellow: #f0e45a` in `:root`, `.graph #tethers path { stroke: var(--yellow)`, `.tglyph { … color: var(--yellow)`, and that `.tglyph:hover` sets no `color`. The glyph view still reports `eye: "eye"`; if you want the SVG pinned, the `span.eye` now contains an `svg` child with a `path` and a `circle`, both `currentColor`.
- Docs (user): plan §6 tether note, grey → yellow (`#f0e45a`).

## Blocked

Nothing.
