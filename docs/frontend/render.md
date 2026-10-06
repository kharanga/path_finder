# render.js

Draws the Circuit board into an `<svg>`. Geometry is in the fixed `0 0 1360 1000` viewBox from `layout.js`, so the browser scales it to the available space.

## createRenderer(svg, { ghostMs, travelMs, lingerMs, reducedMotion, onSelect, onRemove, portrait })

What it does: sets the viewBox (landscape `0 0 1360 1000`, or portrait `0 0 760 1100` when `portrait` is true), adds the board rectangle, the "No sessions running" label, and five layers (`rows`, `traces`, `charges`, `capsules`, `pulses`), and returns a `draw(state, { instant })` function.

Capsules. Each `draw` reconciles one `<g class="capsule" data-pid data-state data-folder tabindex="0" role="img" aria-label>` per live session at the box `boardLayout` gives it, with a `<rect class="shell">`, a `<title>` (name, role, folder, `formerly <names>` after a rename), a `<text class="name">` truncated to 21 characters, and a `<text class="role">` hidden unless a role is declared. One `<text class="row-label" data-folder>` per folder sits left of its row, positioned with a transform so it glides with the capsules when rows shift, and is removed when the folder has no live capsule. States are CSS on `data-state`:

- `busy`: yellow shell with a glow that flickers (`@keyframes flicker`). `waiting`: amber shell, steady glow. `idle`: dim shell and muted name. `started`: dim shell; a capsule created in this state gets class `powering` for 1 s, a bright power-on flash. `ended`: footprint, hollow shell and muted text, see below. `placeholder` (a name seen only in messages): dashed hollow shell, italic name, at the end of its guessed folder row.
- A new capsule is created with class `entering` (opacity 0) and its position already set; styles are flushed synchronously and the class removed, so it fades in at its slot, also in a background tab.
- When a session stops being live and its state is `ended` (or it simply left the live set), the capsule stays as a footprint: `data-state="ended"`, class `leaving`, faint, removed after `ghostMs`. If the same PID is live again before then, the node is reused. When the state is `removed` the capsule is removed at once with no footprint. A footprint is also dropped at once when a live capsule's new box overlaps the footprint's box (its slot was reused after a re-flow), so footprints never sit on top of live capsules.
- A label change (rename, or a PID-only capsule receiving its name) updates the text in place and flashes it yellow for 1.8 s (class `renamed`).
- Remove control (F11): when `onRemove` is given, every non-placeholder capsule gets a `<g class="remove" role="button" aria-label="Remove <name>">` (a red × at its top-right corner). It is hidden by CSS unless the svg has class `editing`, and its `tabindex` is `0` only in edit mode so it is skipped by Tab otherwise. Click, Enter, or Space calls `onRemove(session)` with the capsule's latest session object (a footprint reports state `ended`).

Traces. A `<path class="trace" data-trace="<traceKey>" data-lane="<lane>">` is created the first time a message travels between two capsules that both have a box, routed by `tracePath` with the pair's corridor lanes and pins from `assignLanes` (pairs in order of first appearance, columns by capsule index, corridors by `traceCorridors`) through `laneOptions` (positions never change once assigned), kept faint afterwards, and re-routed on every draw; the lane order resets with the trace layer on a snapshot. Pulses and charges of a pair follow the same lane, so two sources into one capsule are separate routes end to end, and the pulse rests at its own pin. When a snapshot arrives (`state.snapshotSeq` changes) all layers are cleared and traces are rebuilt from the snapshot's messages without pulses, so a reload still shows who talks to whom. A trace is dropped when either capsule is gone.

Pulses. Every message added since the last draw gets a `<g class="pulse" data-message-index role="button" tabindex="0">` with an invisible `<path class="pulse-path">` (sender → recipient route), a transparent `<circle class="pulse-hit" r=18>` at the route's arrival point, the recipient's pin (the click target, hidden until arrival), a `<circle class="pulse-dot">` that travels along the route with SMIL `animateMotion` over `travelMs`, a `<title>`, and an `aria-label`. On arrival it gets class `arrived`, rests dimly at the recipient for `lingerMs`, and is removed. Click, Enter, or Space calls `onSelect(message, index)`. A `null` or unknown sender starts at `edgeBox(recipient)`, the left edge of the recipient's line, and the title says `unknown sender`; a message whose recipient is also missing uses the board center.

Charges. For each `state.threads` entry with status `waiting`, a `<path class="charge" data-thread-id>` along the sender → recipient route is drawn on with `stroke-dasharray` equal to the route length and `stroke-dashoffset` animated from the length to 0 over `travelMs`, and glows until resolved. `snapped` (recipient went idle) adds class `draining` and sets the dashoffset back to the full length, so the charge drains back into the sender over 500 ms before removal. `dropped` (recipient ended) fades out.

Reduced motion. When `reducedMotion` is true (default: `matchMedia("(prefers-reduced-motion: reduce)")`, watched for changes) pulses appear at the recipient as arrived markers, charges appear fully drawn and are removed at once when resolved. The CSS media query stops the flicker, the power-on flash, the rename flash, and all transitions.

Inputs:
- `svg` (SVGSVGElement): the target element. It should start empty.
- `ghostMs` (number, optional, default 8000): how long an ended capsule stays as a footprint.
- `travelMs` (number, optional, default 1200): pulse flight and charge draw-on time.
- `lingerMs` (number, optional, default 15000): how long an arrived pulse stays clickable.
- `reducedMotion` (boolean, optional): overrides the media query for the JavaScript behavior; `app.js` passes `true` for `?motion=reduce`, `false` for `?motion=full`.
- `onSelect` (function(message, index), optional).
- `onRemove` (function(session), optional): enables the remove controls.
- `portrait` (boolean, optional, default false): start with the portrait board.

Output: `draw(state, { instant })`, returning nothing, with three methods: `draw.select(index)` adds class `selected` to the pulse whose `data-message-index` equals `index` and removes it elsewhere (`null` clears); `draw.setPortrait(boolean)` switches the viewBox and board size, the next `draw` re-lays everything out; `draw.setEditing(boolean)` toggles class `editing` on the svg and the remove controls' `tabindex`. `instant: true` (used by the timeline when scrubbing and when returning to live) removes non-live capsules at once, skips fade-in and power-on, and shows charges fully drawn. Pulses are never spawned for a state whose `snapshotSeq` differs from the previous draw, which is always the case for replayed states.

Errors: throws if `svg` is not an element. `draw` never throws on valid state.

Example, in a browser or DOM stub with `frontend/fixtures/few.json` applied and `createRenderer(svg, { ghostMs: 10 })`:

```js
draw(state);
svg.getAttribute("viewBox")                                            // "0 0 1360 1000"
document.querySelectorAll(".capsule").length                           // 5
document.querySelectorAll(".row-label").length                         // 4
document.querySelector('.capsule[data-pid="30111"]').dataset.state     // "busy"
document.querySelector('.capsule[data-pid="30111"]').dataset.folder    // "tag-analyzer"
document.querySelector('.capsule[data-pid="30111"] .role').textContent // "validator"
document.querySelector('.capsule[data-pid="30111"] title').textContent // "tag-analyzer-63 (validator) in tag-analyzer"
document.querySelector('.capsule[data-pid="30111"]').getAttribute("aria-label") // "tag-analyzer-63, busy, validator, folder tag-analyzer"
document.querySelector('.capsule[data-pid="30111"]').getAttribute("tabindex")   // "0"
document.querySelector('.capsule[data-pid="30222"]').style.transform   // "translate(230.0px, 412.0px)"
document.querySelector('.capsule[data-pid="29904"] .role').classList.contains("hidden") // true
document.querySelector('.capsule[data-pid="30444"] .name').textContent // "pid 30444"
document.querySelector('.capsule[data-pid="30444"]').classList.contains("powering") // true, created in state started
document.querySelector(".empty-label").classList.contains("hidden")    // true
draw(createState());
document.querySelectorAll(".capsule").length                           // 5, footprints
document.querySelector('.capsule[data-pid="30111"]').dataset.state     // "ended"
document.querySelector('.capsule[data-pid="30111"]').classList.contains("leaving") // true
document.querySelector(".empty-label").classList.contains("hidden")    // false
document.querySelector(".board").classList.contains("empty")           // true
// after ghostMs (pass { ghostMs: 10 } in tests):
document.querySelectorAll(".capsule").length                           // 0
```

Revive: with `{ ghostMs: 10000 }`, `draw(state)`, `draw(createState())`, `draw(state)` within 10 s gives 5 capsules, none `leaving`, pid 30111 back to `busy`.

Removed, with `frontend/fixtures/removed.json`: after the snapshot and event 1 (`listings-bc` ended) there are 4 capsules, pid 29904 `ended` and `leaving`; after event 2 (pid 40707 `removed`) pid 40707 has no capsule at all while pid 29904 is still a footprint; after event 3 (a message from `path-finder-e5`) pid 40707 is back as an `idle` capsule with no placeholder; after event 4 it is `busy`. The snapshot message created one `.trace` (`data-trace="30111|30222"`).

Slot reuse, with `frontend/fixtures/many.json`: on the `liveness` end of pid 41001 (`listings-25`, second of three in the listings row) the row closes up, `listings-4a` slides into the second slot, and the footprint is dropped in that same draw because its box is now occupied, so `document.querySelector('.capsule[data-pid="41001"]')` is `null` and `document.querySelectorAll('.capsule.leaving').length` is 0. A footprint survives only while nothing moves into its box, for example the last capsule of a row (`few.json`: `tag-analyzer-63` is alone in its row and stays as a footprint).

With `many.json` the capsule for pid 41008 shows `add-semantic-similar…` and its title holds `add-semantic-similarity-scores-28 in add-semantic-similarity-scores`.

Rename, with `frontend/fixtures/rename.json`: after the snapshot and event 2, the capsule for pid 29248 has `.name` text `manager-drives-featu…` (27 characters truncated to 21), class `renamed`, and title `manager-drives-feature-work (manager) in path_finder, formerly path-finder-0d`. Still exactly 3 capsules and no `placeholder:path-finder-0d`. The pulse for event 3 (sent as `path-finder-0d`) starts at that capsule's bottom edge: its path `d` begins with `M <cx> <y + height>` of the capsule.

Messages and charges, with `frontend/fixtures/messages.json` and `createRenderer(svg, { reducedMotion: true, lingerMs: 60000 })`:

```js
draw(applySnapshot(createState(), fixture.snapshot));
document.querySelectorAll(".pulse").length  // 0, snapshot history is not animated
document.querySelectorAll(".trace").length  // 1, rebuilt from the snapshot message
document.querySelectorAll(".charge").length // 0
applyEvent(state, "message", fixture.events[0].data); draw(state);
document.querySelectorAll(".pulse").length                     // 1
document.querySelector(".pulse").dataset.messageIndex          // "1"
document.querySelector(".pulse").classList.contains("notify")  // true
document.querySelector(".pulse").classList.contains("arrived") // true, reduced motion skips the flight
document.querySelectorAll(".trace").length                     // 2
document.querySelectorAll(".charge").length                    // 1
document.querySelector(".charge").dataset.threadId             // "1"
applyEvent(state, "session", fixture.events[1].data); draw(state); // recipient busy
document.querySelectorAll(".charge").length                    // 1, still waiting
applyEvent(state, "session", fixture.events[4].data); draw(state); // recipient idle
document.querySelector(".charge").classList.contains("draining") // true, removed on the next macrotask under reduced motion
document.querySelector('.capsule[data-pid="30111"]').dataset.state // "waiting" before event 3, "busy" after
```

Without `reducedMotion`, the dot has an `animateMotion` child whose `mpath` references the pulse's own path id, and the charge starts with `stroke-dashoffset` equal to its length.

Selection, with the last event of `messages.json` (sender `null`) applied:

```js
const pulse = document.querySelector('.pulse[data-message-index="6"]');
pulse.querySelector("title").textContent // "unknown sender → path-finder-18: sender unknown: hook could not resolve the session name"
pulse.querySelector(".pulse-path").getAttribute("d").startsWith("M 194 ") // true, starts at the edge of the recipient's line
pulse.dispatchEvent(new Event("click")); // onSelect called with (state.messages[6], 6)
draw.select(6); pulse.classList.contains("selected") // true
draw.select(null); pulse.classList.contains("selected") // false
```

Edit mode, with `few.json` and `createRenderer(svg, { onRemove })`:

```js
draw(state);
document.querySelectorAll(".capsule .remove").length                       // 5 (placeholders get none)
document.querySelector('.capsule[data-pid="30111"] .remove').getAttribute("aria-label") // "Remove tag-analyzer-63"
document.querySelector('.capsule[data-pid="30111"] .remove').getAttribute("tabindex")   // "-1"
draw.setEditing(true);
svg.classList.contains("editing")                                           // true
document.querySelector('.capsule[data-pid="30111"] .remove').getAttribute("tabindex")   // "0"
document.querySelector('.capsule[data-pid="30111"] .remove').dispatchEvent(new Event("click")); // onRemove called with the session for pid 30111
draw.setPortrait(true); svg.getAttribute("viewBox")                        // "0 0 760 1100"
draw(state); document.querySelectorAll(".row-label").length                 // 4, now above their rows
```

Styling hooks in `orbit.css`: `.board`, `.board.empty`, `.row-label`, `.capsule[data-state="busy"|"waiting"|"idle"|"started"|"ended"|"placeholder"]`, `.capsule.entering`, `.capsule.leaving`, `.capsule.powering`, `.capsule.renamed`, `.capsule .shell`, `.trace`, `.charge`, `.charge.drawing`, `.charge.draining`, `.charge.dropping`, `.pulse`, `.pulse.notify`, `.pulse.arrived`, `.pulse.selected`, `.pulse-dot`, `.pulse-hit`, `.capsule .remove` (shown under `.orbit.editing`), `.empty-label`, `.hidden`.
