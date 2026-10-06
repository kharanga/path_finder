# app.js and index.html

`index.html` is the only page. It has a top bar with the title and a connection status badge, a `<main>` holding `<svg id="orbit">`, a `<footer id="timeline">` with the scrubber strip, and loads `app.js` as an ES module. `orbit.css` holds all styles. No build step.

## start({ svg, statusElement, timelineElement })

What it does: creates the live state, the timeline recorder, and the renderer, mounts the strip, draws the empty ring at once, then calls `connect`. Every snapshot or event is applied to the live state and recorded in the timeline with the same arrival time. If the strip is in live mode the live state is drawn; in scrub mode the ring keeps showing the scrubbed instant while the strip's range still grows. Scrubbing draws `timeline.stateAt(tsMs)` with `instant: true`; clicking Live draws the live state with `instant: true` and resumes. Every 5 s placeholders older than 60 s are pruned and, if any were, the live view is redrawn. Connection status is written into `statusElement` as text and as `data-status` for styling.

Inputs:
- `svg` (SVGSVGElement): the ring target.
- `statusElement` (HTMLElement): where the status word is shown.
- `timelineElement` (HTMLElement): the footer with the four `data-role` elements that `mountTimelineStrip` expects.

Output: the disconnect function returned by `connect`.

Errors: none thrown directly. DOM errors surface if the elements are missing.

`start` runs automatically at module load only when an element with id `orbit` exists, so importing `app.js` in a test without that element does nothing.

Example: open `?fixture=messages`, wait 15 s, drag the knob left to about a third. The label shows a clock time, the border above the strip turns yellow, the ring shows that moment's state with no animation. Click Live: the ring returns to the current state and the label reads `Live`.

Example: open `http://127.0.0.1:8787/?fixture=empty` served from `frontend/`. The status badge reads `fixture`, the ring is dashed, and the text "No sessions running" is centered. With `?fixture=few` five bodies appear, and after about seven seconds one has left the ring (tag-analyzer-63 ended), one is renamed from `pid 30444` to `scratch-7a`, and `listings-bc` has turned busy.
