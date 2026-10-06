# render.js

Draws the Orbit ring into an `<svg>`. All geometry is in a fixed `0 0 1360 1000` viewBox, ring radius 340 centered at (680, 500). The extra width leaves room for a 24-character side label on each side (about 290 units of text plus the 32-unit gap) without reaching the edge, so nothing clips at narrow viewports. The browser scales the box to the available space.

## createRenderer(svg, { ghostMs })

What it does: sets the viewBox, adds the ring circle, the "No sessions running" label, and an empty bodies layer, and returns a `draw(state)` function. Each call to `draw` reconciles one `<g class="body" data-pid data-state data-folder>` per live session: creating, moving, and relabeling nodes as needed. Each body has a `<circle class="halo">` (visible and pulsing only while busy), a `<circle class="core">`, a `<title>` tooltip with the full name, role, and folder, a `<text class="name">` truncated to 24 characters, and a `<text class="role">` that is hidden unless the session declared a role. Label offsets come from `labelPlacement`. Bodies are positioned with a CSS `transform`, so a position change animates over 600 ms unless the user prefers reduced motion.

State visuals (F3) are all CSS keyed on classes and `data-state`:

- A new body is created with class `entering` (opacity 0) and loses it on the next animation frame, so it fades in.
- When a session stops being live, its node is not removed. It gets `data-state="ended"` and class `leaving`, fades to a faint mark at its last position, and is removed after `ghostMs`. If the same PID becomes live again before then, the timer is cancelled and the node is reused.
- `busy`: yellow core with a drop-shadow glow and a pulsing halo. `idle`: dim core and muted label. `started`: light blue core. `ended`: ring-colored core.

The empty label is shown and the ring becomes dashed when there are no live sessions. Ghosts do not count as live.

Inputs:
- `svg` (SVGSVGElement): the target element. It should start empty.
- `ghostMs` (number, optional, default 8000): how long an ended body stays as a faint mark.

Output: `draw(state)`, a function taking the state from `state.js` and returning nothing.

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

With `frontend/fixtures/many.json` the body for pid 41008 shows the name `add-semantic-similarity…` and its title holds `add-semantic-similarity-scores-28 in add-semantic-similarity-scores`.

Styling hooks in `orbit.css`: `.body[data-state="busy"|"idle"|"started"|"ended"]`, `.body.entering`, `.body.leaving`, `.body .halo`, `.body .core`, `.ring.empty`, `.empty-label`, `.hidden`. Under `prefers-reduced-motion: reduce` all transitions are off and the busy halo is a static glow with no pulse.
