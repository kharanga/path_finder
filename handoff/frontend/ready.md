# Ready: F11 removal editor and portrait board

## Done

`frontend/editor.js` (new)
- Pure: `removeUrl(pid)`, `endedSessions(state)`, `describeRemoval(targets)`.
- `createEditor({ toggleButton, removeAllButton, hintElement, confirmElement, getState, draw, request })`: Edit/Done toggle (`aria-pressed`, `body[data-mode]`), per-capsule removal through `requestRemove(session)`, "Remove all ended" (disabled when none), one inline confirmation bar (`role="alertdialog"`, Remove/Cancel, focus moves to Remove; no `window.confirm`), `POST /sessions/<pid>/remove` per target via injectable `request` (default `fetch`), success and failure hints, `setAvailable(bool)` which disables everything with the hint "Removal needs the server. Fixture mode has none." Nothing is changed locally on removal: the capsule drops when the server's `removed` event arrives (F10 behavior).

`frontend/render.js`
- `onRemove` option adds a `<g class="remove" role="button" aria-label="Remove <name>">` × control to every non-placeholder capsule, visible only under `svg.editing`, focusable only in edit mode (`draw.setEditing(bool)`). Footprints keep their control and report state `ended` to `onRemove`.
- `portrait` option and `draw.setPortrait(bool)`: viewBox 760×1100, two capsules per line, folder labels above rows, row labels anchored by the new `labelX/labelY/anchor` from the layout.

`frontend/layout.js`
- `BOARD_PORTRAIT`, `boardFor(portrait)`, `boardLayout(sessions, { portrait, width, height })` returning `rows[].labelX/labelY/anchor` and `board`. Boxes carry `columnOrigin` so `tracePath`'s bus columns and `edgeBox` work on both boards. Landscape numbers unchanged (all F10 examples still hold).

`frontend/app.js`: creates the editor, routes `onRemove` to it, enables it on SSE status `live`/`reconnecting`, follows `matchMedia("(max-width: 600px)")` for the portrait switch and redraws the current view instantly on change. `frontend/index.html`: editor controls in the top bar and the confirmation bar. `frontend/orbit.css`: editor, confirm, remove-control styles, portrait aspect ratio under 600 px.

Verified live against `node webhook/server.js --demo --port 4848` (own temp events file; 4747 is the user's real dashboard and was not touched): Edit enabled on `live`; × on `listings-99` → confirmation text → Remove → `POST /sessions/36024/remove` → capsule gone with no footprint, `/snapshot` no longer lists it, `stats.removals` 1; "Remove all ended" on 15 ended sessions (see test 4 for the numbers); Done hides the controls and restores Tab order. Fixture mode on the static server: Edit disabled with the hint. Portrait in a 390 px frame: viewBox `0 0 760 1100`, 15 capsules on 10 lines in 8 labeled rows, no horizontal scroll.

Docs: `docs/frontend/editor.md` (new), `layout.md`, `render.md`, `app.md`, `README.md` (file table, editor row, safe demo port note). Example runner: 194 checks, 0 failures, includes the editor flow with a recording `request` stub and the failure path.

SPEC.md §8.2 F11 is `[~] path-finder-18`.

## How to test

Editor (needs the server; use a sandbox port, never the live 4747):

```
node webhook/server.js --demo --port 4848
```

1. Open `http://127.0.0.1:4848/`. Status `live`, Edit enabled. Click Edit: it reads Done, every capsule shows a red × at its top-right, "Remove all ended" appears (disabled until a demo session ends), hint explains the mode.
2. Click a ×: the bar under the top bar reads "Remove <name> from the board?" with Remove and Cancel, focus on Remove. Cancel closes it. Remove: the capsule disappears at once with no footprint, the hint reads "Removed <name>.", `curl -s http://127.0.0.1:4848/snapshot` no longer lists the PID and `stats.removals` increased. Only the server wrote the event; reload the page and the capsule is still gone.
3. Keyboard: Tab in edit mode reaches each × (label "Remove <name>"), Enter opens the confirmation, Enter again removes. Outside edit mode Tab skips the controls.
4. After the demo has ended sessions (about a minute), "Remove all ended" is enabled: it asks "Remove N ended sessions from the board?" and Remove sends one POST per session; `/snapshot` then has zero `ended` sessions.
5. Fixture mode: `python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend`, open `?fixture=few`: Edit disabled, hint "Removal needs the server. Fixture mode has none."
6. Portrait: viewport under 600 px (DevTools device toolbar or a 390 px iframe): viewBox `0 0 760 1100`, two capsules per line, folder label above each row, no horizontal scroll; switching the width back and forth re-lays out the board without reload.
7. Node and DOM stub: `docs/frontend/editor.md` example (recording `request`, 404 path), `layout.md` portrait additions, `render.md` edit-mode block, or the scratchpad runner (194 checks).

## Requests

1. Validator (V7): runner at `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/658ff14a-2610-461f-9302-e64c02a54c6a/scratchpad/docs-check/run-examples.mjs` with the same DOM stub. The editor test needs `document.body` on the stub (the runner sets it).
2. Manager: footprints keep their old position while live capsules re-flow, so in portrait a footprint can briefly sit on top of a live capsule (it fades within 8 s). If that bothers the user, footprints could re-flow with the layout; say so and I will do it.
3. Manager: `index.html` still uses `id="orbit"` and `orbit.css`; renaming would touch tests and the server's static examples, so I left them.

## Blocked

Nothing.
