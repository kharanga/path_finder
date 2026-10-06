# Ready: F5 timeline strip (plus placeholder bodies from the F4 decision)

## Done

`frontend/timeline.js` (new)
- `createTimeline()`: records every snapshot entry and incremental event with its event timestamp and arrival time, sorted by time. `range()`, `messageTimes()`, `stateAt(tsMs)` (rebuilds a state from scratch by replaying entries at or before `tsMs`, with a unique negative `snapshotSeq` so the renderer never animates a replay), `size`.
- `mountTimelineStrip(container, timeline, { onScrub, onLive })`: binds the footer in `index.html` (Live button, range input, tick marks per message, clock label). Slider input leaves live mode and calls `onScrub`; Live calls `onLive`. `refresh()` grows the range as events arrive; in live mode the knob follows the end, in scrub mode it stays put. Disabled with fewer than two distinct timestamps.
- `formatClock(tsMs)`.

`frontend/app.js`: keeps the live state and the timeline in step. Live mode draws the live state on every event; scrub mode draws `timeline.stateAt(ts)` with `instant: true` and keeps recording, so nothing is lost; Live redraws the live state instantly and resumes. Prunes placeholders every 5 s.

`frontend/render.js`: `draw(state, { instant })`. Instant removes non-live bodies at once (no ghosts), skips fade-in, shows threads fully drawn. Fade-in and thread draw-on now use a synchronous style flush instead of `requestAnimationFrame`, which Chrome pauses in background tabs (bodies were stuck invisible when the tab was not in front). Placeholder bodies: hollow dashed circle, italic label, explanatory title.

`frontend/state.js` (F4 decision, manager 2026-10-05): a message `from` or `to` a name with no session creates a placeholder `{ name, folder: folderFromName(name), createdAtMs }`. Placeholders appear in `liveSessions` as pseudo-sessions `{ pid: "placeholder:<name>", state: "placeholder" }` at the folder slot guessed by stripping the trailing `-<id>`, are found by `sessionByName` so particles and threads route to them, are merged (deleted) when a session event with that name arrives, and are removed by `prunePlaceholders(state, nowMs, maxAgeMs = 60000)`. `applySnapshot`, `applyEvent`, `applyMessageEvent` take an optional `receivedAtMs` (default `Date.now()`) so tests control the clock. Folder sorting treats `_` and `-` as equal so a guessed `path-finder` sits beside `path_finder`.

`frontend/index.html`, `frontend/orbit.css`: footer strip markup and styles; placeholder style.

Fixtures: `generated-many.json` and `generated-mid.json` written from W4 with the commands in `docs/webhook/fake-generator.md`; both load and run in the page (see test 6). `messages.json` unchanged, its `nobody-99` message now produces a placeholder body instead of routing to the center.

Docs: `docs/frontend/timeline.md` (new), `state.md`, `render.md`, `app.md`, `README.md` updated.

SPEC.md §8.2 F5 marked `[~] path-finder-18`.

## How to test

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

1. `?fixture=messages`, wait 15 s. Strip at the bottom: Live button (disabled, green), slider knob at the right, 6 ticks, label `Live`. `nobody-99` is a dashed hollow body at the top of the ring with an italic label and the thread from `path-finder-0d` ends on it, not at the center. After 60 s from its message it disappears.
2. Drag the knob left. Label shows a clock time, border above the strip turns yellow, Live button enables, the ring shows that instant's state with no fades or particles. Early in this fixture (before 22:00:00Z event time) only the snapshot message exists, so the ring shows two placeholders, `path-finder-0d` and `path-finder-18`, which is the faithful state at that moment.
3. While scrubbed, events keep arriving: the range grows (knob proportionally moves left) but the ring does not change. Click Live: current state appears at once, label `Live`.
4. Reload while the tab is in the background (open it, switch tabs, come back after 10 s): bodies are fully visible, not stuck faded.
5. Node, `docs/frontend/timeline.md` example: `size` 15, range, 6 message times, `stateAt` at 22:00:13Z and at the end, `stateAt(0)` empty. `docs/frontend/state.md` placeholder examples: create, merge, prune at +59 s (0) and +60 s (1), `folderFromName` cases.
6. `?fixture=generated-mid` (8 sessions, snapshot) and `?fixture=generated-many` (15 sessions from empty, ~160 s): bodies appear, messages fly, strip fills with ticks, scrubbing works. One generated message has `from: null`; the reducer drops it per the §3 schema (see Requests 2).

## Requests

1. Validator: `docs/frontend/timeline.md` `formatClock` example is timezone dependent; compare against `new Date(ts).getHours()` etc. in the test's own zone.
2. webhook-builder (via manager): the generator emits one message with `from: null`. §3 says `from` is a string, so the page drops it. If a sender can really be unknown, the contract should say so and I will render it from a placeholder or the center; otherwise the generator should not emit it.
3. Manager: the generator's 15-session run takes 160 s real time; a `--speed` for `--fixture` output would make validator checks faster if W4 does not already support it.

## Blocked

Nothing.
