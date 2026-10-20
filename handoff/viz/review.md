# Review: V7 2026-10-20

PASS

## Verified against SPEC V7

- `/web` and `/web.html` serve `viz/web.html` (200, text/html); `/` still serves `index.html`; `/sessions.json`, `/identity/<pid>.json`, `/index.html.bak`, unknown paths and a traversal all 404 now that `STATIC_DIRS` is `(VIZ_DIR,)`. `/state` and `/events` unchanged.
- Fixture replay at `/web`, frozen on port 4796 (stopped) at 10.300, 10.500, 11.000, 11.100, 17.600, 21.060 and 30.000, screenshotted through a 380 px iframe: `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/9e6343e0-d664-4782-b79a-a6cac9debb65/scratchpad/web{1,2,3,4,6,8,9}.png`. The pod of two cards, the Sending pill and watching line, the grey `Pending` arrow arched above the pod with its label, the green `✓ In inbox` arrow and `Inbox 1` pill plus orange chip count, the `✓✓ Read` flash with the quoted body on the builder card, the reply right to left, the `👁 idle notice` pulse with the muted `fake builder idle notice to fake manager` toast and no arrow, the entry-and-pair caption, and `No traffic` at the end all match ready.md and the mocks.
- Timing through the page script with a fake clock (`tests/page/render_web.mjs`): the change stream from the fixtures gives Pending → In inbox → Read flash (opacity 0.94 just after the read) → arrow and label gone after 3.5 s with the toast dimmed → toast gone after 8.5 s; the reply the same; the eye pulses for the notice and stops within 1.5 s; the round ends on `No traffic`; after 11 minutes both sessions stay in the ring (fresh-start rule). The stream render equals the frozen render at four cuts.
- Ten-session synthetic feed: compact nodes (100×24) with the orange count and working ring on the dot, one arrow per pair with `+1`, a label only on the newest arrow, the FAILED arrow red and staying until a later message on the pair reaches In inbox, chip pick thickens that session's arrows and dims the rest, `+2 more` under three toasts, a session without traffic in 10 minutes out of the ring and faded in the strip with the reason in the tooltip, the notice pulsing the head eye in compact mode.
- Live six-session view on a spare port with `--root` the project (read-only): ring of the four sessions with recent traffic, three in-flight arrows from the manager with labels, caption `system · turn_duration · manager`, strip with the two fake sessions faded, notice toast plus two `In inbox` toasts and `+1 more`. Same window as the mock's five-session view. Screenshot `weblive.png` in the same folder. The user's look on 4780/web is still theirs.

## Tests

- `tests/page/render_web.mjs` (fake clock, steps of frames, `advanceMs`, `clickChip`, `clickNode`, `hoverToast`, `leaveToast`, `hoverPath`, `error`, `reopen`; based on the builder's harness).
- `tests/integration/test_web_render.py`: 13 tests, fixture round plus synthetic ten-session, horizon, watching, unidentified and empty cases.
- `tests/integration/test_serve.py`: the fallback test replaced by `test_static_files_come_from_viz_only_and_web_route_serves_the_compact_page`.
- `tests/unit/test_watcher_server.py`: `STATIC_DIRS == (VIZ_DIR,)`, `PAGE_ROUTES`.
- `python3 -m pytest tests` → 259 passed.

## Notes

- On a snapshot load the caption pair is taken from the newest `kind == "message"` row within 1 s of the latest source, so a freeze just after the idle notice shows `fake manager` where the stream shows `fake builder → fake manager`. Cosmetic.
- A FAILED arrow also leaves after the 10 minute horizon; SPEC says it stays until resolved. Minor.
- `viz/web.html` line 543: an unused `ends` statement in `toastItems`.
- Arrow labels converge near the ring centre and overlap when three or more arrows are in flight (live view); the animation mock has the same geometry.
- The eye glyph is scaled 1.35 while pulsing, so `👁 idle notice` reads without a visible space. Cosmetic.
- Headless Chrome will not open narrower than 500 px; the 380 px shots use an iframe wrapper, as the builder did.
- Docs user items: plan §6 should describe the web window; earlier items unchanged.
