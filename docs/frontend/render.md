# render.js

Draws the Orbit ring into an `<svg>`. All geometry is in a fixed `0 0 1000 1000` viewBox, so the browser scales it to the available square.

## createRenderer(svg)

What it does: sets the viewBox, adds the ring circle, the "No sessions running" label, and an empty bodies layer, and returns a `draw(state)` function. Each call to `draw` reconciles one `<g class="body" data-pid data-state>` per live session: creating, moving, relabeling, and removing nodes as needed. Each body has a `<circle>`, a `<text class="name">`, and a `<text class="role">` that is hidden unless the session declared a role. Labels sit on the side given by `labelSide`. The empty label is shown and the ring becomes dashed when there are no live sessions.

Inputs: `svg` (SVGSVGElement): the target element. It should start empty.

Output: `draw(state)`, a function taking the state from `state.js` and returning nothing.

Errors: throws if `svg` is not an element (DOM calls fail). `draw` never throws on valid state.

Example, in a browser with `frontend/fixtures/few.json` applied:

```js
const draw = createRenderer(document.getElementById("orbit"));
draw(state);
document.querySelectorAll(".body").length                       // 5
document.querySelector('.body[data-pid="30111"]').dataset.state // "busy"
document.querySelector('.body[data-pid="30111"] .role').textContent // "validator"
document.querySelector(".empty-label").classList.contains("hidden") // true
draw(createState());
document.querySelectorAll(".body").length                       // 0
document.querySelector(".empty-label").classList.contains("hidden") // false
```

Styling hooks in `orbit.css`: `.body[data-state="busy"]`, `.body[data-state="idle"]`, `.body[data-state="started"]`, `.ring.empty`, `.empty-label`, `.hidden`.
