# Ready: F2 ring layout and F3 state visuals (round 2)

## Done

Round 2 fixes: render.md many.json paragraph now names pid 41008 / `add-semantic-similarity-scores-28` (33 chars); many.json messages have string `from`/`to` (`listings-00` ↔ `tag-analyzer-6f`); viewBox widened to 1360×1000 so 24-char side labels stay inside the box (review note 1). Review note 2 (slot inside a folder group follows name order) left as is pending the manager's call.

F1 review (round 1) fixes: `docs/frontend/layout.md` now documents `labelSide` returning `top`/`bottom`/`left`/`right`, has sections for `labelPlacement` and `truncateLabel` (including the validator's observed outputs), and `docs/frontend/render.md` states the real viewBox (now 1360×1000 after round 2). Review note 1 addressed: `frontend/app.js` only calls `start()` when `#orbit` exists, so it imports cleanly in Node.

F2 ring layout, in `frontend/layout.js` and `frontend/render.js`:

- Sessions sorted by folder then name, evenly spaced from the top clockwise. Same-folder sessions are adjacent. Ordering is independent of arrival order, so reloads and restarts put a folder back in the same group.
- `labelPlacement` puts labels outward: side labels hang left or right, labels within 11.5° of vertical stack above or below the body. Two lines when a role is declared. No overlap at 15 sessions (arc spacing 142 units vs 44 units for two text lines).
- `truncateLabel` cuts names over 24 characters with an ellipsis. Full name, role, and folder are in a `<title>` tooltip on the body.
- viewBox 1360×1000 so side labels fit inside the box. Bodies move with a 600 ms CSS transform transition, disabled under `prefers-reduced-motion`.
- `data-folder` on each body for styling and tests.

New fixtures: `frontend/fixtures/one.json` (1 session), `frontend/fixtures/many.json` (15 sessions, 8 folders, siblings, a 33-char name, 3 unnamed, then a `liveness` end followed by a new PID in the same folder). Table of fixtures in `docs/frontend/README.md`.

F3 state visuals, in `frontend/render.js` and `frontend/orbit.css`:

- Busy: yellow core with drop-shadow glow and a pulsing halo circle. Idle: dim core, muted label. Started: light blue. Ended: ring-colored.
- Fade in: new body nodes start with class `entering` (opacity 0), removed on the next frame.
- Fade out with faint mark: a session that leaves the live set is kept as a ghost (`data-state="ended"`, class `leaving`, opacity 0.3) at its last position for `ghostMs` (default 8000) and then removed. A PID that comes back within that window reuses its node and the timer is cancelled.
- Role label underneath only when declared (unchanged from F1/F2).
- Under `prefers-reduced-motion: reduce`: no transitions, no pulse, static glow. Full reduced-motion pass is F7.

SPEC.md §8.2: F1, F2, F3 marked `[~] path-finder-18`.

## How to test

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

1. `http://127.0.0.1:8787/?fixture=one`: one body at the top, label above it, turns from yellow to dim after 2 s.
2. `http://127.0.0.1:8787/?fixture=few`: 5 bodies as in the F1 round.
3. F3 on `?fixture=few`: `tag-analyzer-63` and `path-finder-e5` glow and pulse. After ~1.5 s `listings-bc` starts glowing. At ~7 s `tag-analyzer-63` fades to a faint grey mark with muted label, still on the ring, and disappears about 8 s later. `pid 30444` fades in light blue and later turns dim as `scratch-7a`.
4. F3 in Node with a DOM stub: `createRenderer(svg, { ghostMs: 10 })`, draw `few.json`, then `draw(createState())` gives 5 bodies all `data-state="ended"` with class `leaving`; after 10 ms there are 0. See the example in `docs/frontend/render.md`.
5. `http://127.0.0.1:8787/?fixture=many`: 15 bodies, no label touching another, `add-semantic-similarity…` truncated at the top with the full name on hover, path-finder bodies adjacent with roles underneath, listings bodies adjacent. After ~2 s `listings-25` leaves and after ~3.5 s `listings-f0` appears next to the other listings bodies, and the others slide to make room.
6. Node: every example in `docs/frontend/layout.md` (`ringPositions`, `labelSide`, `labelPlacement` with 0.01 tolerance, `truncateLabel`), plus `import("./frontend/app.js")` resolves without a DOM.
7. Acceptance for F2 says "checked against W4 output at 1, 5, and 15 sessions". W4 does not exist yet, so `one`, `few`, and `many` stand in. I will re-check against W4 output when it lands.

## Requests

1. **Contract (docs/overview.md):** server must serve all of `frontend/` as static files, not only `GET /`. Validator confirmed necessary (six files besides `index.html`).
2. **W4 fixture format (optional):** emit `{snapshot, events:[{delayMs,event,data}]}` per `docs/frontend/README.md`, or I write a converter from `events.jsonl` in `frontend/`.

## Blocked

Nothing.
