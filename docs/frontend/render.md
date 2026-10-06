# render.js

Draws the Orbit ring into an `<svg>`. All geometry is in a fixed `0 0 1360 1000` viewBox, ring radius 340 centered at (680, 500). The extra width leaves room for a 24-character side label on each side (about 290 units of text plus the 32-unit gap) without reaching the edge, so nothing clips at narrow viewports. The browser scales the box to the available space.

## createRenderer(svg, { ghostMs, travelMs, lingerMs, reducedMotion, onSelect })

What it does: sets the viewBox, adds the ring circle, the "No sessions running" label, and an empty bodies layer, and returns a `draw(state)` function. Each call to `draw` reconciles one `<g class="body" data-pid data-state data-folder>` per live session: creating, moving, and relabeling nodes as needed. Each body has a `<circle class="halo">` (visible and pulsing only while busy), a `<circle class="core">`, a `<title>` tooltip with the full name, role, and folder, a `<text class="name">` truncated to 24 characters, and a `<text class="role">` that is hidden unless the session declared a role. Label offsets come from `labelPlacement`. Bodies are positioned with a CSS `transform`, so a position change animates over 600 ms unless the user prefers reduced motion.

State visuals (F3) are all CSS keyed on classes and `data-state`:

- A new body is created with class `entering` (opacity 0); styles are flushed synchronously and the class removed, so it fades in even when the tab is in the background (where `requestAnimationFrame` is paused).
- When a session stops being live, its node is not removed. It gets `data-state="ended"` and class `leaving`, fades to a faint mark at its last position, and is removed after `ghostMs`. If the same PID becomes live again before then, the timer is cancelled and the node is reused.
- `busy`: yellow core with a drop-shadow glow and a pulsing halo. `waiting` (permission prompt): orange core with a faint static halo, no pulse. `idle`: dim core and muted label. `started`: light blue core. `ended`: ring-colored core. `placeholder` (a name seen only in messages): hollow dashed circle, italic muted label, title "`<name>`, no session event yet (folder guessed: `<folder>`)".

The empty label is shown and the ring becomes dashed when there are no live sessions. Ghosts do not count as live.

Messages (F4). The renderer remembers how many messages it has drawn. On each `draw`, every message added since the last draw gets a particle; when `state.snapshotSeq` changes the counter resets and the particle and thread layers are cleared, so snapshot history is never animated. A particle is `<g class="particle" data-message-index role="button" tabindex="0">` holding an invisible `<path class="particle-path">` from `messageCurve`, a transparent `<circle class="particle-hit" r=16>` at the recipient (hidden until arrival) that is the click target, a `<circle class="particle-dot">` that travels along the path with SMIL `animateMotion` over `travelMs`, a `<title>` with sender, recipient, and text, and an `aria-label`. After arriving it gets class `arrived`, shrinks to a dim dot at the recipient for `lingerMs`, and is removed. Click, Enter, or Space on a particle calls `onSelect(message, index)` when that option is given. Positions come from the last drawn position of the named session or placeholder; a `null` sender (allowed by the contract when the hook could not resolve the name) and a name with no body at all (a ghost already removed) fall back to the ring center, and the title and label say `unknown sender`. Particles for `notify_on_idle` messages carry class `notify` and are tinted like threads.

Threads. For each `state.threads` entry with status `waiting`, a `<path class="thread" data-thread-id>` is drawn along the same curve and re-routed on every draw so it follows bodies that move. It draws on from the sender using `stroke-dasharray` equal to the curve length and `stroke-dashoffset` animated from the length to 0 over `travelMs`. When the thread's status becomes `snapped` (recipient went idle) the path gets class `snapping` and its dashoffset returns to the full length, which retracts the line back into the sender over 500 ms before removal. Status `dropped` (recipient ended) fades the path out instead.

Reduced motion. When `reducedMotion` is true (default: `matchMedia("(prefers-reduced-motion: reduce)")`), particles appear directly at the recipient as arrived markers, threads appear fully drawn, and snapping removes them at once.

Inputs:
- `svg` (SVGSVGElement): the target element. It should start empty.
- `ghostMs` (number, optional, default 8000): how long an ended body stays as a faint mark.
- `travelMs` (number, optional, default 1200): particle flight and thread draw-on time.
- `lingerMs` (number, optional, default 15000): how long an arrived particle stays clickable at the recipient.
- `onSelect` (function(message, index), optional): called when a particle is clicked or activated with the keyboard.
- `reducedMotion` (boolean, optional): overrides the media query, useful in tests.

Output: `draw(state, { instant })`, a function taking the state from `state.js` and returning nothing, with one method: `draw.select(index)` adds class `selected` to the particle whose `data-message-index` equals `index` and removes it from all others (`null` clears). With `instant: true` (used by the timeline when scrubbing and when returning to live) bodies that are no longer live are removed at once instead of becoming ghosts, new bodies appear without the fade-in, and threads appear fully drawn. Particles are never spawned for a state whose `snapshotSeq` differs from the previous draw, which is always the case for replayed states.

Errors: throws if `svg` is not an element (DOM calls fail). `draw` never throws on valid state.

Example, in a browser with `frontend/fixtures/few.json` applied:

```js
const draw = createRenderer(document.getElementById("orbit"));
draw(state);
document.querySelectorAll(".body").length                           // 5
document.querySelector('.body[data-pid="30111"]').dataset.state     // "busy"
document.querySelector('.body[data-pid="30111"]').dataset.folder    // "tag-analyzer"
document.querySelector('.body[data-pid="30111"] .role').textContent // "validator"
document.querySelector('.body[data-pid="30111"] title').textContent // "tag-analyzer-63 (validator) in tag-analyzer"
document.querySelector(".empty-label").classList.contains("hidden") // true
draw(createState());
document.querySelectorAll(".body").length                           // 5, still present as ghosts
document.querySelector('.body[data-pid="30111"]').dataset.state     // "ended"
document.querySelector('.body[data-pid="30111"]').classList.contains("leaving") // true
document.querySelector(".empty-label").classList.contains("hidden") // false
// after ghostMs (8 s by default, pass { ghostMs: 10 } in tests):
document.querySelectorAll(".body").length                           // 0
```

Reviving a ghost: with `createRenderer(svg, { ghostMs: 10000 })`, `draw(createState())` then `draw(state)` again within 10 s gives 5 bodies, none with class `leaving`, pid 30111 back to `data-state="busy"`.

Messages and threads, with `frontend/fixtures/messages.json` and `createRenderer(svg, { reducedMotion: true, lingerMs: 60000 })`:

```js
draw(applySnapshot(createState(), fixture.snapshot));
document.querySelectorAll(".particle").length // 0, snapshot history is not animated
document.querySelectorAll(".thread").length   // 0
applyEvent(state, "message", fixture.events[0].data); draw(state);
document.querySelectorAll(".particle").length                     // 1
document.querySelector(".particle").dataset.messageIndex          // "1"
document.querySelector(".particle").classList.contains("notify")  // true
document.querySelector(".particle").classList.contains("arrived") // true, reduced motion skips the flight
document.querySelectorAll(".thread").length                       // 1
document.querySelector(".thread").dataset.threadId                // "1"
applyEvent(state, "session", fixture.events[1].data); draw(state); // recipient busy
document.querySelectorAll(".thread").length                       // 1, still waiting
applyEvent(state, "session", fixture.events[4].data); draw(state); // recipient idle
document.querySelector(".thread").classList.contains("snapping")  // true, removed on the next macrotask under reduced motion
document.querySelector('.body[data-pid="30111"]').dataset.state   // "waiting" before event 3, "busy" after
```

Without `reducedMotion`, the dot has an `animateMotion` child whose `mpath` references the particle's own path id, and the thread starts with `stroke-dashoffset` equal to its length.

Selection, with `createRenderer(svg, { reducedMotion: true, onSelect })` and the last event of `messages.json` (sender `null`) applied:

```js
const particle = document.querySelector('.particle[data-message-index="7"]');
particle.querySelector("title").textContent // "unknown sender → path-finder-18: sender unknown: hook could not resolve the session name"
particle.dispatchEvent(new Event("click")); // onSelect called with (state.messages[7], 7)
draw.select(7); particle.classList.contains("selected") // true
draw.select(null); particle.classList.contains("selected") // false
```

With `frontend/fixtures/many.json` the body for pid 41008 shows the name `add-semantic-similarity…` and its title holds `add-semantic-similarity-scores-28 in add-semantic-similarity-scores`.

Styling hooks in `orbit.css`: `.body[data-state="busy"|"waiting"|"idle"|"started"|"ended"|"placeholder"]`, `.body.entering`, `.body.leaving`, `.body .halo`, `.body .core`, `.particle`, `.particle.notify`, `.particle.arrived`, `.particle.selected`, `.particle-dot`, `.particle-hit`, `.thread`, `.thread.drawing`, `.thread.snapping`, `.thread.dropping`, `.ring.empty`, `.empty-label`, `.hidden`. Under `prefers-reduced-motion: reduce` all transitions are off and the busy halo is a static glow with no pulse.
