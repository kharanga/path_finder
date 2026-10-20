# Ready: V15 2026-10-20

## Done

Draggable, pinned nodes on `viz/web.html`; the watcher is unchanged.

- Dragging: every node (full card or compact) listens for `pointerdown` / `pointermove` / `pointerup` / `pointercancel` (mouse and touch; `touch-action: none`, pointer capture). A press that moves less than 4 px is a click and keeps the V7 pick; past 4 px the node follows the pointer (`.dragging`: no transition, raised, grab shadow; arrow labels stop animating while a drag is on), with every render in between so arrows, labels, and the envelope count follow it. The click Chrome fires at the end of a drag is ignored for 400 ms after the drop (`lastDragEnd`), a later click picks as before.
- Pins: a dropped node is pinned (`pins`, class `pinned`, `layout.pinned`). `positionNodes` still computes the automatic ring (or pod) for the whole ring exactly as in V11/V13, then overrides the pinned nodes with their pinned centres and runs the relax step once more with the pinned nodes fixed, so an unpinned node keeps its automatic place unless a pinned node is dropped onto it, in which case it is pushed vertically clear (and may nudge its ring neighbours). Positions are clamped: never past the graph's left or right edge, never above its top, never below the window's bottom edge (`clampToGraph`); the graph grows downward to hold any node dropped below it (`layout.H` ≥ lowest pinned card + 12).
- Storage: the pin is saved on drop under `localStorage["viz-web-pin:<key>"]` as `{x, y}` where the key is the session's label, else its role, else its PID (`pinKeyOf`). On every render a session without an in-memory pin is looked up once by that key, so a reload lands the node where it was and a later session with the same role lands there too; a session with no saved position takes its automatic place. All storage access is guarded.
- Reset layout: a `Reset layout` button in the caption bar (`#reset-layout`, hidden while nothing is pinned) clears every pin in memory and every `viz-web-pin:` key in storage and re-renders the ring. The page tolerates a DOM without the button.

Files: `viz/web.html`.

## How to test

Seven-session fixture on a spare port (4780 is the manager's):

```
python3 viz/watcher.py serve --port 4792 --no-log --spec /dev/null $(cat <scratchpad>/seven_args.txt) &
open http://127.0.0.1:4792/web
```

Expected: drag viz-builder down and left; its `D5 ready` arrow and label follow during the drag and after the drop; the node shows a solid border (`pinned`), the other nodes stay put unless the drop lands on one, and `Reset layout` appears at the right of the caption. Click the node: it is picked as before (arrows thicken), no move. Drag it below the ring: the graph grows so it stays inside; it cannot be dropped past the window bottom or outside the left/right edges. Reload: it is where it was, `localStorage["viz-web-pin:901"]` (this fixture has no role, so the PID is the key; on 4780 the key is the role, e.g. `viz-web-pin:viz-builder`). Replace the fixture with one where the same role has a new PID (relabel or regenerate): the new session lands at the saved spot. Click `Reset layout`: every node returns to its ring place and the button hides. Touch: same on a touchscreen or in DevTools device mode.

Checked here: Node harness `web_drag.json` (seven sessions, 901 labelled `viz-builder`): a 150 px left / 320 px down drag pins 901 at its drop point with the `900>901` path redrawn to the new spot, 900/905/906 unchanged, 904 pushed clear of the drop (it nudged 903 and 902 up), storage key `viz-web-pin:viz-builder` = `{"x":120,"y":497}`, the Reset button shown; a click at the same instant is ignored, a click a second later picks; a drag 900 px down grows the graph to 912 px and stores y 844; Reset returns every node to its start position, empties storage, hides the button. `web_drag_reload.json` (same role under pid 951, storage seeded): the new session lands at the stored spot, pinned. `cdp_drag.mjs` in headless Chrome at 380 px: a real mouse drag moves the node from (224, 165) to (104, 435) with its arrow following, `pinned dragging` during the move and `pinned` after, graph 475 → 553 px, the stored pin set on release, a click then picks it, `Page.reload` brings it back at (104, 435), clicking Reset layout returns it to (224, 165) with the pin removed and the button hidden.

Suite: `python3 -m pytest tests` → 354 passed, 0 failed (the validator's harness has no `#reset-layout` element, the page tolerates that; nothing else changed in the DOM the tests read).

## Requests

- Manager: nothing to restart; the page is served from the file.
- Validator: add `#reset-layout`, `getBoundingClientRect`, pointer capture stubs, `window.innerHeight`, and `localStorage.removeItem/key/length` to the harness, then tests for drag → pin → arrow follows, click guard, clamp and growth, storage key by label/role/PID, reload and same-role landing, Reset; my scratchpad has `web_drag.json`, `web_drag_reload.json`, the harness steps `dragNode` / `clickNodeOnly` / `clickReset`, and `cdp_drag.mjs`.
- Docs (user): plan §6 add dragging, pins keyed by role in localStorage, and Reset layout.

## Blocked

Nothing.
