# editor.js

The session removal editor (SPEC §4.1): an Edit toggle, a remove control on every capsule, a one-step inline confirmation, "Remove all ended", and the call to `POST /sessions/<pid>/remove`. `removeUrl`, `endedSessions`, and `describeRemoval` are pure; `createEditor` needs the editor markup in `index.html` and a renderer.

## removeUrl(pid)

What it does: builds the server path for removing one session.

Inputs: `pid` (number or string).

Output: string.

Errors: none.

Example:

```js
removeUrl(29904) // "/sessions/29904/remove"
```

## endedSessions(state)

What it does: lists the sessions whose state is `ended`, the targets of "Remove all ended". Removed sessions and footprints that have expired visually but are still `ended` in state are included; live sessions and placeholders are not.

Inputs: `state` (object from `state.js`).

Output: `Session[]`.

Errors: none.

Example, with `frontend/fixtures/removed.json` after event 1:

```js
endedSessions(state).map(s => s.session) // ["listings-bc"]
```

## describeRemoval(targets)

What it does: writes the confirmation sentence.

Inputs: `targets` (Session[]).

Output: `"Nothing to remove."`, `"Remove <name> from the board?"` for one target (`pid <pid>` when unnamed), or `"Remove <n> ended sessions from the board?"`.

Errors: none.

Example:

```js
describeRemoval([])                                   // "Nothing to remove."
describeRemoval([{ pid: 29904, session: "listings-bc" }]) // "Remove listings-bc from the board?"
describeRemoval([{ pid: 1 }, { pid: 2 }])             // "Remove 2 ended sessions from the board?"
```

## createEditor({ toggleButton, removeAllButton, hintElement, confirmElement, getState, draw, request })

What it does: binds the editor. Starts unavailable: the toggle is disabled and the hint reads "Removal needs the server. Fixture mode has none." `setAvailable(true)` (called by `app.js` when the SSE status is `live` or `reconnecting`) enables the toggle. Clicking the toggle enters edit mode: its text becomes `Done`, `aria-pressed` is `true`, `document.body.dataset.mode` is `edit`, `draw.setEditing(true)` shows the capsule remove controls, "Remove all ended" appears (disabled while `endedSessions(getState())` is empty), and the hint explains the mode. The renderer calls `requestRemove(session)` when a remove control is activated; the editor fills the confirmation bar with `describeRemoval`, shows it, and focuses its Remove button. Remove sends `POST removeUrl(pid)` for every target through `request` (default `fetch`), then closes the bar and shows either "Removed <name>." or "Removal failed for <name>: <status>." Cancel just closes the bar. "Remove all ended" opens the same bar for every ended session. Leaving edit mode or losing the server closes any open confirmation. Nothing on the page is changed directly by a removal: the server broadcasts the `removed` event and the renderer drops the capsule when it arrives.

Inputs:
- `toggleButton`, `removeAllButton` (HTMLButtonElement), `hintElement` (HTMLElement), `confirmElement` (HTMLElement containing `[data-role=confirm-text]`, `[data-role=confirm-yes]`, `[data-role=confirm-no]`).
- `getState` (function → state): read on every refresh.
- `draw` (renderer): must expose `setEditing(boolean)`.
- `request` (function(url, init) → Promise<Response-like with ok and status>, optional): defaults to `fetch`, injectable for tests.

Output: `{ setAvailable(value), requestRemove(session), refresh(), isEditing, pending }`. `pending` is the array of sessions awaiting confirmation, or `null`.

Errors: throws if a confirmation sub-element is missing. Network errors are caught and reported in the hint.

Example, DOM stub with the markup from `index.html` and a recording `request`:

```js
const calls = [];
const editor = createEditor({ ...elements, getState: () => state, draw, request: async (url) => { calls.push(url); return { ok: true, status: 204 }; } });
toggleButton.disabled                 // true
hintElement.textContent               // "Removal needs the server. Fixture mode has none."
editor.setAvailable(true); toggleButton.disabled // false
toggleButton.click(); editor.isEditing // true
toggleButton.textContent              // "Done"
removeAllButton.hidden                // false
editor.requestRemove({ pid: 29904, session: "listings-bc" });
confirmElement.hidden                 // false
confirmText.textContent               // "Remove listings-bc from the board?"
confirmYes.click(); await new Promise(r => setTimeout(r, 0));
calls                                 // ["/sessions/29904/remove"]
confirmElement.hidden                 // true
hintElement.textContent               // "Removed listings-bc."
// with state holding two ended sessions:
removeAllButton.click(); confirmText.textContent // "Remove 2 ended sessions from the board?"
confirmNo.click(); editor.pending     // null
// a failing server:
// request → { ok: false, status: 404 } gives hint "Removal failed for listings-bc: 404."
toggleButton.click(); editor.isEditing // false, and draw.setEditing(false) hides the controls
editor.setAvailable(false); toggleButton.disabled // true, edit mode left
```
