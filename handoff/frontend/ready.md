# Ready: F4 round 2 (null sender) and F6 side panel

## Done

`frontend/panel.js` (new)
- `describeMessage(message)` → `{ from, fromKnown, to, time, iso, text, notify }`; a `null` sender becomes `unknown sender` with `fromKnown: false`. `formatTimestamp(ts)` → local `YYYY-MM-DD HH:MM:SS` or `unknown time`.
- `createPanel(element, { onClose })` → `{ show(message, index), hide(), selectedIndex }`. Fills the `<aside id="panel">` fields, italic sender when unknown, `notify on idle` badge only when set, ISO timestamp as tooltip on the time, focuses the close button on open.

`frontend/render.js`
- Particles are focusable buttons (`role="button"`, `tabindex="0"`, `aria-label`) with a transparent 16-unit hit circle at the recipient, enabled on arrival. Click, Enter, or Space calls the new `onSelect(message, index)` option. `draw.select(index)` toggles class `selected` (visible ring) on the matching particle; `null` clears.
- Default `lingerMs` raised from 6 s to 15 s so a particle stays clickable long enough.
- Null sender: particle starts at the ring center; title and label say `unknown sender`.

`frontend/state.js` (F4 review failure 1): `applyMessageEvent` keeps messages with `from: null` or absent `from` (stored as `null`), still requires string `to`, drops other `from` types. No placeholder for a null sender. `sessionByName(state, null)` returns `undefined`.

`frontend/app.js`: creates the panel, passes `onSelect` to the renderer, Escape closes the panel, closing clears the highlight.

`frontend/index.html`, `frontend/orbit.css`: panel markup (header with close button, From/To/Time list, badge, text) and styles. Floats top-right over the ring at desktop width, docks to the bottom under 600 px. `[hidden]` inside the panel is forced to `display: none` so the badge really hides.

`frontend/fixtures/messages.json`: one more event at the end, a message with `from: null` to `path-finder-18` (now 10 events, 8 messages, 7 ticks).

Docs: `docs/frontend/panel.md` (new); `render.md` (onSelect, select, hit area, linger, null sender, selection example), `state.md` (null sender rules and examples, counts), `timeline.md` (counts), `app.md` (panel), `README.md`.

SPEC.md §8.2 F6 marked `[~] path-finder-18`.

## How to test

```
python3 -m http.server 8787 --bind 127.0.0.1 --directory frontend
```

1. `?fixture=messages`, wait 17 s. At ~16 s a particle flies from the ring center to `path-finder-18` (null sender). Click the small dot resting on `path-finder-18`: the panel opens top-right with From `unknown sender` (italic), To `path-finder-18`, local time with the ISO on hover, no badge, full text. The particle gets a highlighted ring.
2. Click the dot resting on the `nobody-99` placeholder at the top: panel shows From `path-finder-0d`, the `notify on idle` badge, and the text. Two `path-finder-0d` notify particles rest there (the one to `nobody-99`, and the one to `listings-bc`, which landed at that spot before `listings-bc` ended and `nobody-99` slid into its slot); arrived particles stay where they landed, so the later one is on top. Particles are clickable from arrival for 15 s; a click during flight does nothing.
3. Press Escape or the × button: panel closes, highlight clears. Tab to a particle and press Enter: panel opens (keyboard path).
4. Narrow the window under 600 px: the panel docks to the bottom instead of the right.
5. Node: `docs/frontend/panel.md` examples (`describeMessage` for a null and a known sender, `formatTimestamp(null)`), `state.md` null-sender examples (`from: null` kept, `from: 5` dropped, thread list unchanged after the tenth event, 8 messages), `timeline.md` counts (16 entries, 7 message times, end 22:00:29Z).
6. DOM stub: `render.md` selection example (title text with `unknown sender`, click dispatch calls `onSelect` with index 7, `draw.select(7)` / `draw.select(null)` toggles `selected`).
7. `?fixture=generated-mid`: the generator's `from: null` message now produces a particle from the center and is clickable.

## Requests

1. Validator: `describeMessage(...).time` and `formatTimestamp` are local-time strings; compare against `new Date(ts)` components in the test's zone.
2. Manager: when the user scrubs the timeline, particles are not shown (replays never animate), so there is nothing to click for historical messages. If history should be browsable, F7 or a later task could make the timeline ticks clickable to open the same panel. Not done, awaiting your call.

## Blocked

Nothing.
