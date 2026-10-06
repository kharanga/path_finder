# Review: F7 2026-10-05

PASS

## What was checked

Acceptance: `prefers-reduced-motion` disables pulse and particles become instant markers; works at phone width.

- Reduced motion, CSS (read): the media block turns off body, halo, particle, and thread transitions and stops the busy halo animation with a static opacity. JavaScript: `createRenderer` defaults from `matchMedia` and `watchReducedMotion` updates the option on change; with a stubbed `matchMedia` reporting `matches: true` and no override, a new message's particle is created already `arrived` and its thread has `stroke-dashoffset` 0. `app.js` maps `?motion=reduce` to `true` and `?motion=full` to `false` (read).
- Keyboard and screen readers: bodies carry `tabindex="0"`, `role="img"`, and the documented `aria-label` (`tag-analyzer-63, busy, validator, folder tag-analyzer`; role segment omitted when null). Particles keep `role="button"` and `tabindex="0"` from F6.
- Timeline ticks: `timeline.messages()` returns 7 entries with the last sender `null`; `mountTimelineStrip` renders 7 `button` ticks, the first `aria-label` starts with `Message from path-finder-0d to path-finder-18 at`, the null-sender tick says `unknown sender`; clicking the second tick calls `onTick` with that message and its timestamp. `app.js` routes `onTick` to `panel.show` (read).
- Phone width (read): `overflow-x: hidden` on the page, `.stage` clips, two `max-width: 600px` blocks dock the panel to the bottom, keep 16 px gutters, and enlarge ring labels. The 390 px measurement in ready.md is browser-only and not reproduced here.

# Review: F4 (round 2), F6 2026-10-05

1. `docs/frontend/render.md`, "Selection, with ..." example  input: `messages.json` fully replayed, `document.querySelector('.particle[data-message-index="7"]')`  expected (per docs): the null-sender particle, `onSelect` called with `(state.messages[7], 7)`, `draw.select(7)`  actual: no particle has index 7. The fixture has 7 messages (1 in the snapshot, 6 in events), so the null-sender message is `state.messages[6]` and its particle has `data-message-index="6"`.
2. `docs/frontend/state.md`, `applyEvent` example "after all 10 events"  input: same replay  expected (per docs): `state.messages.length // 8`  actual: `7`. Same off-by-one as failure 1.

## What passed

F4 round 1 failure closed: `applyMessageEvent` keeps `from: null` and absent `from` (stored as `null`), drops non-string, non-null `from` and non-string `to`, creates no placeholder for a null sender. The null-sender particle's path starts at the ring center (680, 500) and the dot rests on the recipient; title and `aria-label` say `unknown sender`. `state.md` describes this; thread sequence after all 10 events is `["1:path-finder-e5:snapped", "4:nobody-99:waiting", "5:listings-bc:dropped"]` with `nobody-99` the only waiting thread and the only placeholder.

F6 `panel.md`: `describeMessage` both examples match (time compared against the local zone), `formatTimestamp` null and `nope` give `unknown time`, missing text gives `""`. `createPanel` through the DOM stub: `show` unhides the panel, fills from/to/time/text, toggles `unknown` on the sender, hides the badge for plain messages and shows it for `notify_on_idle`, sets the ISO tooltip on the time, records `selectedIndex`, focuses the close button; `hide` hides, clears the index, calls `onClose`; the close button click does the same; missing markup throws. `render.js`: particles carry `role="button"`, `tabindex="0"`, an `aria-label`, a hit circle; click and Enter call `onSelect` with the stored message object and index, other keys do not; `draw.select(i)` adds `selected` and `draw.select(null)` clears it. `app.js` wires `onSelect` to `panel.show` plus `draw.select`, Escape to `panel.hide`, and `onClose` to `draw.select(null)` (read only).

# Review: F5 2026-10-05

PASS

## What was checked

`docs/frontend/timeline.md` examples with `messages.json` (now 10 events): `size` 16, range 21:59:00Z to 22:00:29Z, 7 message times, `stateAt` at 22:00:13Z gives the five documented session states and one waiting thread with `snapshotSeq` -1, `stateAt(end)` gives the documented states including the `nobody-99` placeholder and threads `snapped, waiting, dropped`, `stateAt(0)` is empty. Entries without a parsable `ts` fall back to arrival time; an empty timeline has a null range. `formatClock` compared against the local-zone `getHours` etc. per ready.md request 1 (matches, `""` for NaN).

`mountTimelineStrip` through the DOM stub with a fresh container: empty timeline disables the slider and the Live button and shows `Live`; with history the slider spans the range, the knob sits at the end, 7 ticks are rendered with percentage offsets; an `input` event leaves live mode (`data-mode="scrub"`, clock label, Live enabled, `onScrub` with the slider value); a new event recorded while scrubbed grows `max` and leaves the knob where it was; clicking Live restores live mode, the knob jumps to the end, `onLive` fires; a container missing a role throws.

`render.js` `draw(state, { instant: true })` with a replayed state: non-live bodies removed at once (no ghost), no `entering` class, threads at dashoffset 0, no particles spawned; returning to the live state with `instant` also spawns nothing. Normal live draw still produces ghosts.

Generated fixtures: `generated-many.json` and `generated-mid.json` are byte-identical to the generator output from my W4 run. Through the page reducer and timeline: mid keeps 15 messages, many 19, max 10 and 17 live bodies, one `ghost-session-00` placeholder and waiting thread each, and replaying the timeline to its end reproduces the live state's body count for both.

`import("./frontend/app.js")` still resolves in Node (it now also imports `panel.js`, which exists).

Browser-only items (knob drag, yellow border, background-tab fade fix) read only.

## Notes, not failures

1. Files changed during the review again (`panel.js`, `onSelect`, null-sender handling, a tenth `messages.json` event). The timeline.md counts were stale for a moment and are correct now. Reviewed as of the F6 message.

# Review: F4 2026-10-05

1. `frontend/state.js:54` `applyMessageEvent`  input: `{ ts, type: "message", from: null, to: "listings-bc", text: "...", notify_on_idle: true }` (the shape `docs/overview.md:56` now allows and `webhook/hooks/dashboard-hook.js` emits when the sender's name cannot be resolved; `webhook/fake.js` emits one per run)  expected: message appended, thread created, sender drawn from the ring center or a placeholder  actual: `state.messages.length` stays 0 and no thread is created, the message is dropped. `docs/frontend/state.md:114` documents the current behavior ("Requires string from and to"), so docs and code agree with each other but not with the contract. Decide the sender display for `from: null` (ring center, as unknown names already use) and update code, docs, and `messages.json` or `generated-many.json` to cover it.

## What passed

Thread model (`state.md`): the `messages.json` replay gives `["1:path-finder-e5:waiting"]` after event 1, unchanged after the recipient goes busy, `snapped` after idle, and `["1:path-finder-e5:snapped", "4:nobody-99:waiting", "5:listings-bc:dropped"]` after all nine. `waitingThreads` returns `["nobody-99"]`. `resolvedTs` is set from the resolving event. A `waiting` state leaves the thread open; a second idle is a no-op; a name learned on the same idle event resolves. Prune: with 60 finished threads and one waiting, 50 finished remain plus the waiting one. Snapshot messages with `notify_on_idle` create threads, `snapshotSeq` increments.

Placeholders (`state.md`, manager decision): `a-11`/`b-22` example, merge on the real session event, `liveSessions` pid `placeholder:a-11`, `prunePlaceholders` 0 at +59 s and 1 at +60 s, `folderFromName` three examples, underscore and hyphen folders sort adjacent. Rendered placeholder has `data-state="placeholder"` and the documented title. A particle to a placeholder lands on the placeholder body, not the center, and its thread is drawn.

`messageCurve` (`layout.md`): `d`, rounded length 519, and control point match. Reverse direction mirrors the control point. Coincident endpoints do not throw.

Render (`render.md` example with `reducedMotion: true, lingerMs: 60000`): 0 particles and 0 threads after the snapshot; after event 1, one particle with `data-message-index="1"`, classes `notify` and `arrived`, dot placed at the recipient, title "sender → recipient: text", one thread with `data-thread-id="1"` and `stroke-dashoffset` 0; thread survives the busy event; `snapping` after idle and gone on the next macrotask; pid 30111 `waiting` then `busy`; a dropped thread fades and is removed while the `nobody-99` thread stays; `listings-bc` becomes a ghost. A second `applySnapshot` on the same state clears particle and thread layers, and a snapshot containing a waiting notify draws its thread fully. Without reduced motion: `animateMotion` with `dur`, `mpath href="#particle-path-0"` matching the path id, thread starts with dashoffset equal to its length and class `drawing`, both cleared after a frame. Layer order threads, bodies, particles.

`messages.json` validates against `webhook/schema.js` (0 of 20 rejected, including the `waiting` session). CSS read only: busy pulse, waiting static halo, particle and thread transitions, reduced-motion block covers particle dot and thread.

## Notes, not failures

1. `render.js` and `state.js` changed on disk twice during this review (placeholders landed mid-F4). Reviewed against the files as of the F5 message. The review of F5 will re-run these checks.
2. `SNAP_MS` is 600 in `render.js` while the CSS snapping transition and the docs say 500 ms; removal 100 ms after the transition ends is fine, just say so in render.md if you want the numbers to match.
