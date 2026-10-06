# panel.js

The side panel that opens when a message particle is clicked. `describeMessage` and `formatTimestamp` are pure and run in Node; `createPanel` needs the `<aside id="panel">` markup from `index.html`.

## describeMessage(message)

What it does: converts a stored message into display fields. A `null` sender becomes the text `unknown sender` with `fromKnown: false`, which the panel renders in italics.

Inputs: `message` (object from `state.messages`: `{ ts, from, to, text, notify_on_idle }`).

Output: `{ from, fromKnown, to, time, iso, text, notify }`. `time` is local `YYYY-MM-DD HH:MM:SS`, `iso` the original timestamp string (or `""`).

Errors: none.

Example (local time shown in US Pacific; the hour differs by zone):

```js
describeMessage({ ts: "2026-10-05T22:00:29Z", from: null, to: "path-finder-18", text: "sender unknown", notify_on_idle: false })
// { from: "unknown sender", fromKnown: false, to: "path-finder-18", time: "2026-10-05 15:00:29", iso: "2026-10-05T22:00:29Z", text: "sender unknown", notify: false }
describeMessage({ ts: "2026-10-05T22:00:10Z", from: "path-finder-18", to: "path-finder-e5", text: "F4 ready", notify_on_idle: true })
// { from: "path-finder-18", fromKnown: true, to: "path-finder-e5", time: "2026-10-05 15:00:10", iso: "2026-10-05T22:00:10Z", text: "F4 ready", notify: true }
```

## formatTimestamp(ts)

What it does: formats an ISO timestamp as local `YYYY-MM-DD HH:MM:SS`.

Inputs: `ts` (string or null).

Output: string; `"unknown time"` when `ts` is missing or not a valid date.

Errors: none.

Example:

```js
formatTimestamp(null)   // "unknown time"
formatTimestamp("nope") // "unknown time"
```

## createPanel(element, { onClose })

What it does: binds the panel markup: `[data-field=from|to|time|text]`, the `[data-field=notify]` badge, and the `[data-role=close]` button. `show` fills the fields, toggles the `unknown` class on the sender, shows the badge only for `notify_on_idle` messages, sets the ISO timestamp as the time's tooltip, unhides the panel, and moves focus to the close button. `hide` hides the panel, clears the selection, and calls `onClose`. The close button calls `hide`; `app.js` also hides on Escape.

Inputs:
- `element` (HTMLElement): the `<aside id="panel">`.
- `onClose` (function, optional): called after the panel hides, used to clear the particle highlight.

Output: `{ show(message, index), hide(), selectedIndex }`.

Errors: throws if the close button or a field element is missing.

Example, in a browser with `?fixture=messages` loaded for 17 s: click the small dot resting on `path-finder-18`. The panel shows From `unknown sender` (italic), To `path-finder-18`, the local time, no badge, and the full text. Press Escape or the × button: the panel closes and the particle highlight clears. Clicking a dot of a `notify_on_idle` message shows the `notify on idle` badge.
