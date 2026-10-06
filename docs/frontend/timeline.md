# timeline.js

Records every event the page has seen and rebuilds the dashboard state at any instant, so the strip at the bottom of the page can scrub through history while the live stream keeps being recorded. The recording part is pure and runs in Node; `mountTimelineStrip` needs a DOM.

## createTimeline()

What it does: returns a recorder with the methods below. Entries are kept sorted by their event timestamp (`data.ts` parsed to ms, falling back to the arrival time when `ts` is missing or unparsable).

Inputs: none.

Output: `{ recordSnapshot, record, range, messageTimes, stateAt, size }`.

Errors: none.

### recordSnapshot(snapshot, receivedAtMs)

What it does: records each session object and each message of a snapshot as its own entry, so history starts at the oldest timestamp in the snapshot.

Inputs: `snapshot` (object, `{ sessions, messages }`), `receivedAtMs` (number, default `Date.now()`).

Output: none.

Errors: none; a `null` snapshot records nothing.

### record(name, data, receivedAtMs)

What it does: records one incremental event.

Inputs: `name` (`"session"`, `"message"`, or `"liveness"`), `data` (object), `receivedAtMs` (number, default `Date.now()`).

Output: none.

Errors: none.

### range()

What it does: returns the span of recorded history.

Inputs: none.

Output: `{ startMs, endMs }`, or `null` when nothing is recorded.

Errors: none.

### messageTimes()

What it does: lists the timestamps of recorded messages for the tick marks on the strip.

Inputs: none.

Output: `number[]` in ms, oldest first.

Errors: none.

### messages()

What it does: lists recorded messages with their timestamps, for the clickable tick buttons.

Inputs: none.

Output: `{ tsMs: number, data: Message }[]`, oldest first.

Errors: none.

### stateAt(tsMs)

What it does: builds a fresh state from `createState()` and replays every entry whose timestamp is at or before `tsMs`, passing each entry's recorded arrival time so placeholders are created as they were. The returned state has a negative, unique `snapshotSeq`, so the renderer treats each replay as a rebuild and never animates particles for it.

Inputs: `tsMs` (number).

Output: a state object as described in `state.md`.

Errors: none.

### size

What it does: getter for the number of recorded entries.

Inputs: none.

Output: number.

Errors: none.

Example for all methods above, with `frontend/fixtures/messages.json` and `now = Date.parse("2026-10-05T22:01:00Z")`:

```js
const timeline = createTimeline();
timeline.recordSnapshot(fixture.snapshot, now);
for (const step of fixture.events) timeline.record(step.event, step.data, now);
timeline.size                      // 16
timeline.range()                   // { startMs: Date.parse("2026-10-05T21:59:00Z"), endMs: Date.parse("2026-10-05T22:00:29Z") }
timeline.messageTimes().length     // 7
timeline.messages().at(-1).data.from // null

const at13 = timeline.stateAt(Date.parse("2026-10-05T22:00:13Z"));
liveSessions(at13).map(s => `${sessionLabel(s)}:${s.state}`)
// ["listings-bc:idle", "path-finder-0d:idle", "path-finder-18:busy", "path-finder-e5:busy", "tag-analyzer-63:waiting"]
at13.threads.map(t => t.status)    // ["waiting"]
at13.snapshotSeq                   // -1 (each later call is one lower)

const atEnd = timeline.stateAt(timeline.range().endMs);
liveSessions(atEnd).map(s => `${sessionLabel(s)}:${s.state}`)
// ["nobody-99:placeholder", "path-finder-0d:idle", "path-finder-18:busy", "path-finder-e5:idle", "tag-analyzer-63:busy"]
atEnd.threads.map(t => t.status)   // ["snapped", "waiting", "dropped"]
liveSessions(timeline.stateAt(0)).length // 0
```

## mountTimelineStrip(container, timeline, { onScrub, onLive, onTick })

What it does: binds the strip markup in `index.html` (a Live button `[data-role=live]`, a range input `[data-role=scrubber]`, a tick container `[data-role=ticks]`, and a time label `[data-role=time]`). Moving the slider leaves live mode and calls `onScrub(tsMs)`; clicking Live returns and calls `onLive()`. Each message becomes a `<button class="tick">` positioned by time, with `aria-label` "Message from `<sender>` to `<recipient>` at `HH:MM:SS`" (`unknown sender` for a null sender) and a matching tooltip; clicking or activating a tick calls `onTick(message, tsMs)`, which `app.js` uses to open the side panel, so history is browsable even while scrubbed. Ticks are in the tab order between the Live button and the slider. `refresh()` re-reads the timeline range: in live mode the knob follows the newest event, in scrub mode it stays where the user left it while the range still grows, so nothing from the live stream is lost. With fewer than two distinct timestamps the slider is disabled. `container.dataset.mode` is `live` or `scrub` for styling.

Inputs:
- `container` (HTMLElement): the footer holding the four `data-role` elements.
- `timeline` (object from `createTimeline`).
- `onScrub` (function(tsMs)), `onLive` (function()), `onTick` (function(message, tsMs), optional).

Output: `{ refresh(), isLive }`.

Errors: throws if any of the four `data-role` elements is missing.

Example: open `?fixture=messages`, wait 15 s. The strip shows 7 ticks and the label `Live`. Drag the knob to about a third: the label shows a clock time, the Live button becomes enabled, the ring shows the state at that moment (for example `listings-bc` alive again and a single thread between `path-finder-18` and `path-finder-e5`). Click Live: the current state returns, `listings-bc` is gone, the knob snaps to the right edge. Click the second tick: the panel opens with From `path-finder-18`, To `path-finder-e5`, the `notify on idle` badge. In the DOM, `document.querySelectorAll("button.tick").length` is 7 and the first tick's `aria-label` starts with `Message from path-finder-0d to path-finder-18 at`.

## formatClock(tsMs)

What it does: formats a millisecond timestamp as local `HH:MM:SS`.

Inputs: `tsMs` (number).

Output: string, or `""` for an invalid timestamp.

Errors: none.

Example:

```js
formatClock(Date.parse("2026-10-05T22:00:13Z")) // "22:00:13" in UTC, "15:00:13" in US Pacific
formatClock(NaN)                                 // ""
```
