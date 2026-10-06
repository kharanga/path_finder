# Review: F10 2026-10-06 (round 2)

PASS

Round 1 failure 1 closed: no `ring`, `body`, `bodies`, or `particle` wording remains in `docs/frontend/*.md` (the only hit is layout.md's own "Removed in v2" line). `timeline.md` and `panel.md` were cleaned too. README now states that `id="orbit"` and `orbit.css` are kept v1 identifiers. No code change since round 1; the round 1 functional checks stand.

# Review: F10 2026-10-06

1. Docs naming (acceptance: "Docs updated, including `docs/frontend/README.md` naming")  input: grep for ring-era wording in `docs/frontend/`  expected: capsule and board wording  actual: `README.md:39` "not on the ring (placeholder body)", `README.md:41` "the renamed body goes idle"; `app.md:7` "draws the empty ring", "the ring keeps showing", "particle highlight" (twice); `app.md:10` "the ring target"; `app.md:25` "the ring is dashed", "five bodies appear", "left the ring"; `connect.md:28` "the empty ring"; `state.md:11` "a body for a name", `state.md:256` "live body", `state.md:263` "drawn next to a body". `layout.md` and `render.md` are clean.

## What passed

Acceptance against SPEC §4 and §8.2, with `boardLayout`, `tracePath`, and the renderer through the DOM stub:

- Rows and capsules at 1, 5, 15 sessions (`one`, `few`, `many`) and the generator fixtures (`generated-many` 15 sessions on 11 lines, `generated-mid`): zero overlapping capsule boxes, every box inside the 1360×1000 board, one row per folder with `_` and `-` merged, wrapping at 4 per line (6 sessions in one folder give 2 lines), a capsule keeps its slot when a newer session joins its row, placeholders go last, empty input gives no capsules, rows, or lines.
- Traces never cross a capsule: every ordered pair of capsules on each fixture (up to 210 routes per fixture) routed with `tracePath`, and no horizontal or vertical segment passes through the interior of any third capsule, including the compressed 11-line layout where the channel gap shrinks to 12 units.
- Every `layout.md` example matches: the `few.json` layout (5 capsules, 4 rows, pid 30222 at `[230, 412, 340, 440, 1, 0]`), the same-line route `d`, points, and length 290, the straight route of length 64, the two-lines-apart route with 6 points through the bus at x 468, `traceKey` order independence, `edgeBox` at x 194.
- Every message produces a pulse: `messages.json` yields 6 pulses for 6 message events, each with a route path, hit circle, title, aria-label; the null-sender pulse starts at the row edge (x 194); the unknown recipient appears as a dashed placeholder capsule in its own row; traces are created once per pair and rebuilt from snapshot messages without pulses.
- Notify charge drains on idle: the charge for thread 1 is drawn after event 1, survives the recipient's busy event, and gets class `draining` with its dashoffset reset to the full length after the idle event.
- Reduced motion: with the option on, every pulse is created already `arrived`, no `animateMotion` elements exist, charges start at dashoffset 0; the CSS media block turns off the flicker, power-on, and rename animations and all transitions.
- `removed.json`: after the snapshot one trace (`30111|30222`) and no pulses; `listings-bc` ended becomes a footprint; pid 40707 `removed` disappears at once while the footprint remains (3 capsules); it returns busy (4 capsules) and its message produces a pulse and a second trace.
- The builder's example runner against the current code: 164 passed, 0 failed.
- Suite, unit and integration only: 124 tests, 107 pass. The 17 failures are the old ring tests in `tests/unit/frontend/layout.test.js` (import of removed functions) and `render.test.js` (11 tests asserting `.body`, ring viewBox, and particle classes), which V7 replaces, plus 5 webhook tests already broken by W9's in-flight changes (`SESSION_STATES` now has six states, the error message lists `removed`, the hub and the generator scenario changed). Nothing else fails. Timeline, panel, and state tests still pass against the new renderer's inputs.

## Notes, not failures

1. `tests/docs-examples/webhook-docs.test.js` now stalls the full suite: a W9-changed example (`server startServer`) fails its assertion before calling `stop()`, so the listening server keeps the process alive. I will wrap it in try/finally in V7; until then run the suite without `tests/docs-examples/`.
2. `index.html` keeps `id="orbit"` and the stylesheet keeps its `orbit.css` name. Fine as identifiers, but the README row for `index.html` could say so to avoid confusion.

# Review: F9 2026-10-05 (round 2, post-PASS render fix and regenerated fixtures)

PASS

- Builder's example runner against the current `render.js`: 161 passed, 0 failed.
- `generated-many.json`, `generated-mid.json`, `generated-fast.json` are byte-identical to fresh `webhook/fake.js` output with the documented commands. All three validate against `webhook/schema.js` (0 invalid), and replaying each through `frontend/state.js` shows the generator's rename (pid 70052, `listings-2c` → `manager-drives-feature-work`) recorded in `formerNames`, the former name resolving to the live body, and no placeholder for it at any point. Raw instant mode shows the same pid with both names.
- The render fix (new bodies get their transform before the first style flush) is covered by `tests/unit/frontend/render.test.js`: new bodies are created without the `entering` class under instant draws and positioned on creation.

Note: `render.md` line 80 says the thread "starts with `stroke-dashoffset` equal to its length". With the synchronous style flush, the attribute is already 0 by the time `draw` returns; the sentence is true only for the instant before the flush. Reword it when convenient.

# V3: unit tests for frontend 2026-10-05

Done. `tests/unit/frontend/`: `state.test.js` (reducer, threads, placeholders, pruning, former-name resolution, rename bookkeeping), `layout.test.js` (ring positions for 1 to 15, label sides and placement, no-overlap and in-viewBox geometry, message curves, truncation), `render.test.js` (empty ring, body attributes, reduced-motion versus full-motion particles and threads, `matchMedia` default, ghosts and revival, instant draws, snapshot reset, placeholders, null sender, renames, selection), `timeline-panel.test.js` (recording, `stateAt`, clock, strip modes and ticks, panel fields). 40 tests, all through `tests/helpers/dom-stub.js`, no browser. Whole suite: 123 tests, 121 pass, 2 todo.

# Review: F9 2026-10-05

PASS

## What was checked

`rename.json` replayed through the reducer and the renderer (DOM stub, reduced motion, long linger):

- After event 2: `formerNames` is `["path-finder-0d"]`; `sessionByName` resolves both the old and the new name to pid 29248; still 3 bodies, none `placeholder:path-finder-0d`; the body's label is `manager-drives-feature-…`, it carries class `renamed`, its title ends with `formerly path-finder-0d`, and its position is unchanged.
- Event 3 (sent as the former name): the particle path starts at the renamed body's translate position, no placeholder created.
- Event 4 (notify to the former name): one thread, status `path-finder-0d:waiting`, its path ends on the renamed body, `placeholders.size` 0.
- Event 5 (renamed body idle): thread `snapped`, path gets class `snapping`.
- Event 6: 4 bodies, `nobody-99` is the only placeholder, final labels `["listings-bc", "nobody-99", "manager-drives-feature-work", "path-finder-18"]` as documented.
- Bookkeeping: `a → b → a → c` gives `["a", "b"]`; `null → name` is not a rename; an ended session is not matched by a former name but still by its current name.
- Timeline: `stateAt` just before event 2 shows `path-finder-0d` and just after shows `manager-drives-feature-work`, one body for pid 29248 each time.
- `state.md` rename examples and the `render.md` rename paragraph match. The builder's example runner: 161 passed, 0 failed (the truncation mismatch from the F8 note is resolved by documenting the truncated label).

# Review: F8 2026-10-05 (includes F4 round 2 / F6 docs fix)

PASS

## What was checked

- F4 round 2 / F6 failures closed: `render.md` selection example uses index 6 and `state.md` says `state.messages.length // 7`; both verified against `messages.json`.
- Inventory script from ready.md: 26 exports across 7 modules (ready.md says 25; `start` in `app.js` makes 26), every one preceded by a one-line summary. The only other comments are one-line summaries on the public methods returned by `createTimeline`, `createPanel`, and `draw.select`, which fit the project rule.
- Label check over every `##`/`###` section in `docs/frontend/*.md` except README: all have What it does, Inputs, Output, Errors. Seven `createTimeline` sub-sections share the single example under `size`, as ready.md states, and `createTimeline` itself has no separate example. Every other section has its own.
- `docs/frontend/README.md` table names every file in `frontend/` and `frontend/fixtures/`, including `rename.json`.
- The builder's example runner (scratchpad copy, reads nothing outside the repo) run from a clean directory: 160 passed, 1 failed. The failure is `render rename name`, an F9 check expecting the full name `manager-drives-feature-work` while `truncateLabel` cuts at 24 characters. That is F9 work in progress, not F8.
- My own stub-based verification of every example in `state.md`, `layout.md`, `timeline.md`, `panel.md`, and `render.md` from the F4 to F7 reviews still holds.

## Notes, not failures

1. For F9: the rename example above will keep failing unless the docs show the truncated label (`manager-drives-feature-…`) or the renderer lengthens the label limit.
2. For V5 I will fold the builder's runner into `tests/docs-examples/` alongside the webhook one.

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
