# Ready: F4 message particles (plus `waiting` state)

## Done

`frontend/state.js`
- `waiting` added to the live states.
- Threads: a `notify_on_idle` message appends `{ id, from, to, ts, status: "waiting", resolvedTs }` to `state.threads` (`id` = message index). A session event resolves threads addressed to that session's name: `idle` → `snapped`, `ended` → `dropped`, anything else leaves them waiting. At most 50 finished threads are kept. `waitingThreads(state)` exported. `snapshotSeq` increments on every `applySnapshot` so the renderer can tell a rebuild from incremental growth.

`frontend/layout.js`
- `messageCurve(from, to, center, { bow, sideOffset })` returns `{ d, control, length }` for a quadratic curve bowed toward the ring center with a perpendicular offset so opposite bodies do not cross the exact center and A→B / B→A arcs mirror.

`frontend/render.js`
- New layers: `threads` under the bodies, `particles` above. Remembers the last drawn position of every PID (ghosts included) to route messages.
- Particles: one per message added since the last draw; snapshot history is never animated. `<g class="particle" data-message-index>` with a hidden path, a dot moved by SMIL `animateMotion` over `travelMs` (1200 ms), then class `arrived`, shrunk and dimmed at the recipient for `lingerMs` (6 s) so F6 can make it clickable. `<title>` has from → to: text. Unknown names route to the ring center.
- Threads: `<path class="thread" data-thread-id>` for every waiting thread, drawn on with stroke-dash over `travelMs`, re-routed each draw. `snapped` → class `snapping`, dashoffset back to full length (retracts into the sender over 500 ms), removed. `dropped` → fades out.
- `waiting`: orange core (`--waiting`), faint static halo, no pulse.
- Options: `{ ghostMs, travelMs, lingerMs, reducedMotion }`. `reducedMotion` defaults to the media query; when true particles appear at the recipient as arrived markers and threads appear fully drawn and are removed at once when resolved (F7 groundwork).

`frontend/orbit.css`: particle, thread, waiting styles, reduced-motion block extended.

`frontend/fixtures/messages.json`: 5 sessions (one `waiting`), then 9 timed events covering notify → busy → idle (snap), plain message, reply, notify to a name not on the ring, notify whose recipient ends (drop).

Docs: `docs/frontend/state.md` (state shape, threads, `waitingThreads`, `snapshotSeq`, `waiting`), `layout.md` (`messageCurve`), `render.md` (particles, threads, reduced motion, new options, `waiting` color, examples), `README.md` (fixture table).

SPEC.md §8.2 F4 marked `[~] path-finder-18`.

## How to test

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

1. `http://127.0.0.1:8787/?fixture=messages`. At load: `tag-analyzer-63` is orange with a faint halo and no pulse (waiting). No particle for the snapshot message.
2. ~1 s: a blue-tinted dot flies from `path-finder-18` to `path-finder-e5` along an inward arc while a thin thread draws on behind it. The dot lingers at `path-finder-e5` as a small dim dot.
3. ~2.5 s: `path-finder-e5` turns busy, thread stays. ~3.5 s: a plain particle `listings-bc` → `tag-analyzer-63`, no thread. ~5 s: `tag-analyzer-63` turns yellow (busy).
4. ~7.5 s: `path-finder-e5` goes idle and the thread retracts into `path-finder-18` and disappears.
5. ~9 s: reply particle `path-finder-e5` → `path-finder-18`. ~10.5 s: notify to `nobody-99`: particle and thread go from `path-finder-0d` to the ring center and the thread stays (no recipient to go idle).
6. ~12 s: notify `path-finder-0d` → `listings-bc`; ~14.5 s `listings-bc` ends, its thread fades out and the body becomes a ghost.
7. Console: no errors.
8. Node, pure modules: replay `messages.json` through `applyEvent` and compare `state.threads` to the sequence in `docs/frontend/state.md` (ends `["1:path-finder-e5:snapped", "4:nobody-99:waiting", "5:listings-bc:dropped"]`); `messageCurve` example in `layout.md`.
9. DOM stub: the `render.md` example with `createRenderer(svg, { reducedMotion: true, lingerMs: 60000 })` (particle count, `data-message-index`, `notify`, `arrived`, thread count and `data-thread-id`, `snapping` after the idle event, pid 30111 `waiting` then `busy`).

## Requests

1. W4 fake generator: please include the `messages.json` scenario shape (notify → recipient busy → recipient idle, and notify → recipient ended) and a `waiting` session, so F4 can be re-checked against real generator output. The earlier request for the `{snapshot, events}` fixture format or a converter still stands.
2. Manager: a thread to a recipient that never appears (e.g. `nobody-99`) stays waiting forever and is drawn to the ring center. If that is wrong, say whether to drop threads to unknown names after a timeout or hide them.

## Blocked

Nothing.
