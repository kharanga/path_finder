# app.js and index.html

`index.html` is the only page. It has a top bar with the title and a connection status badge, a `<main>` holding `<svg id="orbit">`, and loads `app.js` as an ES module. `orbit.css` holds all styles. No build step.

## start({ svg, statusElement })

What it does: creates the state and renderer, draws the empty ring at once, then calls `connect` so each snapshot or event is reduced into the state and redrawn. Connection status is written into `statusElement` as text and as `data-status` for styling.

Inputs:
- `svg` (SVGSVGElement): the ring target.
- `statusElement` (HTMLElement): where the status word is shown.

Output: the disconnect function returned by `connect`.

Errors: none thrown directly. DOM errors surface if the elements are missing.

Example: open `http://127.0.0.1:8787/?fixture=empty` served from `frontend/`. The status badge reads `fixture`, the ring is dashed, and the text "No sessions running" is centered. With `?fixture=few` five bodies appear, and after about seven seconds one has left the ring (tag-analyzer-63 ended), one is renamed from `pid 30444` to `scratch-7a`, and `listings-bc` has turned busy.
