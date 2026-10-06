# Ready: F12 removal polish

## Done

(1) Reinstatement by message, `frontend/state.js`
- `Session.stateBeforeRemoval`: set when a `removed` event is applied (the state the session had at that moment; a repeated `removed` keeps the first value), `null` otherwise.
- `applyMessageEvent`: for each string `from`/`to` name, `sessionByName` is consulted; nothing found → placeholder as before; a `removed` session found (by current name, or by former name through a new fourth lookup step) → reinstated in `stateBeforeRemoval` (`idle` if unknown) with the message `ts`. No placeholder is created for it. The renderer then shows it as an ordinary capsule (fade-in), since it is live again.
- Limitation, documented: a page that connected after the removal has no record of that session (the server snapshot excludes removed sessions), so a message naming it still produces a placeholder until a session event arrives.

(2) Footprint slot reuse, `frontend/render.js`
- Every capsule node remembers its box. On each draw, a footprint whose box overlaps any live capsule's new box is removed at once instead of fading. Since a row closes the gap left by an ended capsule in the same draw, footprints now survive only where nothing moves in (for example the last capsule of a row, or a row that disappears entirely). This removes the portrait overlap and also tidies landscape.

Fixture: `frontend/fixtures/removed.json` gained a message from the removed `path-finder-e5` between its `removed` and `busy` events (it reinstates as idle, then turns busy).

Docs: `state.md` (field, `applyMessageEvent`, `sessionByName` four steps, reinstatement examples incl. by former name), `render.md` (footprint rule, removed and slot-reuse paragraphs), `README.md` (fixture row). Example runner: 202 checks, 0 failures.

Verified in Chrome: `?fixture=removed` shows pid 40707 back as `idle` right after its message with zero placeholders, then `busy`; portrait 390 px frame on `?fixture=many` after the restart event: 15 capsules, no footprints, no two capsules sharing a box. Demo (`--port 4848`): see test 4.

SPEC.md §8.2 F12 is `[~] path-finder-18`.

## How to test

```
node webhook/server.js --demo --port 4848        # never the live 4747
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

1. `http://127.0.0.1:8787/?fixture=removed` (hard-reload if the static server cached modules): at ~4 s `path-finder-e5` vanishes (removed), at ~6 s a pulse leaves its slot and the capsule is back, dim (idle), no dashed placeholder anywhere; at ~8 s it lights up busy.
2. Node: `state.md` reinstatement examples (`["removed", "idle"]` → `["idle", null]`, placeholders 0, live labels; former-name case leaves only `x-99` as a placeholder).
3. Portrait: 390 px wide frame on `?fixture=many`, wait 4 s: no `.capsule.leaving`, no two capsules with the same transform. Landscape `?fixture=few`: `tag-analyzer-63` (alone in its row) still fades as a footprint, `many.json` `listings-25` (middle of its row) leaves no footprint because the row closes up.
4. Demo on 4848: Edit → remove a live session that is busy or idle (not an ended one) → it disappears; within the random phase it sends or receives a message and comes back as a normal capsule in its previous state, no dashed placeholder. The generator's own `removedByMistake` session comes back through its busy event as before.
5. DOM stub: `render.md` slot-reuse paragraph (`many.json` event 1: pid 41001 gone, 0 `leaving`), removed paragraph (message reinstates pid 40707 as `idle`, 0 placeholders).

## Requests

1. Validator (V7): runner at `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/658ff14a-2610-461f-9302-e64c02a54c6a/scratchpad/docs-check/run-examples.mjs` (202 checks). Your `removed.json` render test and the `applySessionEvent` merge example need the new `stateBeforeRemoval: null` field and the extra fixture event, as you noted.
2. Manager: nothing pending.

## Blocked

Nothing.
