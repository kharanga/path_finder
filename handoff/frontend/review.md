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
