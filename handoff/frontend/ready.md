# Ready: F10 circuit visual (round 2)

## Done

Round 2: review failure 1 (ring-era wording) fixed in `README.md`, `app.md`, `connect.md`, `state.md`, plus the same wording the review did not list in `timeline.md` and `panel.md`. Review note 2: the README file table now says `id="orbit"` and `orbit.css` are v1 identifiers kept on purpose. No code change.

The ring is gone. The page now draws the Circuit board from SPEC §4.

`frontend/layout.js` (pure, new API)
- `BOARD`, `CAPSULE` constants (viewBox 1360×1000, capsules 220×56).
- `boardLayout(sessions, { width, height })`: one row per folder (sorted, `_`/`-` equal), capsules ordered by `firstSeen` then name so a capsule keeps its slot while live and newcomers append; rows wrap at 4 per line; lines spaced evenly and centered, compressed when many. Returns `{ capsules: Map<pid, box>, rows, lineCount, perLine }`.
- `tracePath(from, to, { cornerRadius })`: orthogonal route with rounded corners that never crosses another capsule: same line via a channel below, adjacent lines via the mid channel, farther lines via a vertical bus in the column gap right of the two capsules. Returns `{ d, points, length }`.
- `traceKey(a, b)`, `edgeBox(nearBox)` (origin for unknown senders at the left edge of the recipient's line), `truncateLabel` kept.
- Removed: `ringPositions`, `labelSide`, `labelPlacement`, `messageCurve`. V3 tests that import them will fail until V7 updates them; the docs examples in `docs/frontend/layout.md` give the new expected values.

`frontend/render.js`
- Layers: board rect, row labels (glide with their rows), traces, charges, capsules, pulses.
- Capsules: `<g class="capsule" data-pid data-state>` with shell rect, name, role, title, aria-label, tabindex. States per §4: busy lit with flicker, waiting amber steady, idle dim, started dim with a 1 s power-on flash (class `powering`), ended fades to a footprint for `ghostMs`, `removed` drops the capsule immediately with no footprint, placeholder dashed at the end of its guessed folder row. Fade-in at slot, rename flash and `formerly` tooltip kept from v1.
- Traces: drawn on the first message between two capsules (`data-trace="<traceKey>"`), kept faint, re-routed on every draw, dropped when a capsule goes. Rebuilt from snapshot messages on connect (no pulses).
- Pulses: bright dot along the trace route via SMIL, rests at the recipient for `lingerMs`, clickable and keyboard-activatable (`onSelect`), `draw.select(index)` highlight. Unknown or null sender starts from `edgeBox(recipient)`.
- Charges: `notify_on_idle` keeps the trace charged (glowing overlay drawn on along the route) until the recipient's idle, then drains back to the sender (`draining`), or fades if the recipient ends (`dropping`).
- Reduced motion: instant pulses, charges fully drawn, no flicker, no flashes, no transitions (CSS media query plus the `reducedMotion` option and `?motion=reduce`).

`frontend/orbit.css`: all capsule, trace, charge, pulse styles; phone rules updated. `frontend/index.html`: title Circuit, svg aria-label. `state.js`, `timeline.js`, `panel.js`, `app.js`, `connect.js`: unchanged (`removed` is already non-live because `LIVE_STATES` is an allowlist).

`frontend/fixtures/removed.json`: 4 sessions and a historical message, then `ended` (footprint), `removed` (gone at once), the removed session comes back busy and sends a message.

Docs: `layout.md` and `render.md` rewritten, `README.md` (file table, fixture rows), `state.md` (`removed`), `app.md` (board wording). Example runner updated: 164 checks, 0 failures (`run-examples.mjs` in the scratchpad path below, ready for V7 to copy over `tests/docs-examples/frontend-docs.test.js`).

SPEC.md §8.2 F10 is `[~] path-finder-18`.

## How to test

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

1. `?fixture=few`: board with four folder rows labeled on the left; two path_finder capsules side by side; `tag-analyzer-63` and `path-finder-e5` lit yellow with a soft flicker; `pid 30444` dim blue with a power-on flash at load. At ~7 s `tag-analyzer-63` fades to a hollow footprint and the rows slide up together with their labels.
2. `?fixture=messages`: at ~1 s a pulse runs from `path-finder-18` down into the channel and up into `path-finder-e5`, leaving a glowing charge; the faint trace stays after. At ~7.5 s the charge drains back into `path-finder-18`. At ~10.5 s `nobody-99` appears as a dashed capsule in its own row and the pulse/charge reach it. At ~16 s a pulse enters `path-finder-18` from the left edge of its row (null sender). Click any resting dot: panel as in v1.
3. `?fixture=removed`: at ~1.5 s `listings-bc` becomes a footprint; at ~4 s `path-finder-e5` vanishes at once with no footprint while the footprint is still there; at ~6.5 s it is back and sends a pulse. The snapshot message shows as a faint trace from load.
4. `?fixture=many`: 15 capsules in 8 rows, nothing overlapping, the trace `listings-00` → `tag-analyzer-6f` (3 rows apart) runs through the gap right of the first column, not through capsules.
5. `?fixture=rename`: capsule label changes in place with the flash, same slot, no placeholder for the old name.
6. `?fixture=messages&motion=reduce`: dots appear at the recipient instantly, charges appear fully drawn and vanish at once when resolved, no flicker on busy capsules under an OS reduce-motion setting.
7. Timeline, panel, keyboard (Tab reaches capsules, pulses, Live, ticks, slider), phone width (390 px: `scrollWidth === clientWidth`, panel docks to the bottom): unchanged behavior.
8. Node and DOM stub: every example in `docs/frontend/layout.md` and `render.md`, or run the scratchpad runner (164 checks).

## Requests

1. Validator (V7): updated runner at `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/658ff14a-2610-461f-9302-e64c02a54c6a/scratchpad/docs-check/run-examples.mjs` (same DOM stub). V3 layout tests need `boardLayout`/`tracePath`/`traceKey`/`edgeBox` instead of the ring functions; `layout.md` has the values.
2. Manager: the 1.36 landscape board is short on a phone (the capsules are legible but small). A portrait layout under 600 px (fewer capsules per line, taller board) would help; say if you want it as part of F11 or a later task.
3. Manager: F11 not started, waiting for W9's endpoint as instructed.

## Blocked

Nothing.
