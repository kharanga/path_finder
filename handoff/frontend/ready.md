# Ready: F8 documentation standard, with the F4 round 2 / F6 docs fix

## Done

F4 round 2 and F6 review failure (one cause, two places): the null-sender message is index 6 of 7. Fixed in `docs/frontend/state.md` (`state.messages.length // 7`) and `docs/frontend/render.md` (selection example uses index 6). No code change.

F8 sweep over `frontend/` and `docs/frontend/`:

- Inventory: 25 exports across 7 modules. Every one has exactly one one-line summary comment above it (checked by script) and a docs section (`##`, or `###` for the `createTimeline` methods).
- Every section now has all five labels: What it does, Inputs, Output, Errors, Example. Added the missing Errors lines (`folderFromName` throws `TypeError` on a non-string, `formatClock`, `formatTimestamp`, `recordSnapshot`, `record`), Inputs/Errors on the no-argument timeline methods, and a full What/Inputs/Output/Errors block for the `size` getter. The timeline methods share one example, labeled as such.
- Every example run as written: 144 checks, 0 failures, against the real modules in Node with a small DOM stub (see Requests 1). Covers `state.md`, `layout.md`, `timeline.md` (including `mountTimelineStrip` with the footer markup), `panel.md` (including `createPanel`), `render.md` (bodies, ghosts, revive, `many.json` truncation, particles, threads, selection, placeholder, SMIL attributes), and the `app.js` import guard. `connect.md` and the browser-only paragraphs were checked by reading against the code; they match.
- Time-zone dependent outputs (`formatClock`, `formatTimestamp`, `describeMessage(...).time`) are stated as local time in the docs with a UTC and a US Pacific rendering.
- `docs/frontend/README.md`: table of every real file in `frontend/` with its role and docs file, the list of pure modules, what a DOM stub needs, query parameters, fixture table (now includes `generated-*`).
- F9 forward note in `state.md` `sessionByName`: resolution is by current name only until F9 adds former names, so the docs do not promise what F9 will change.

SPEC.md §8.2 F8 marked `[~] path-finder-18`.

## How to test

1. Export inventory and comment check (from repo root):

```
cd frontend && for f in *.js; do echo "== $f"; awk '/^export (async )?function|^export const/ { name=$0; sub(/^export (async )?function /,"",name); sub(/^export const /,"",name); sub(/\(.*/,"",name); sub(/ =.*/,"",name); c = (prev ~ /^\/\/ /) ? "ok" : "MISSING"; print "  " name " " c } { prev=$0 }' "$f"; done
```

Expected: 25 names, all `ok`.

2. Label check: every `##`/`###` section in `docs/frontend/*.md` except README has lines starting with `What it does`, `Inputs`, `Output`, `Errors`, and an `Example` (the `createTimeline` sub-sections share the example under `size`).

3. Examples: run each example in the docs as written. For the pure modules plain Node suffices. For `render.md`, `createPanel`, and `mountTimelineStrip`, use a DOM stub (Requests 1 has a ready one). Expected outputs are the ones in the docs; local-time strings should be compared against `new Date(...)` components.

4. `docs/frontend/README.md` table matches `ls frontend frontend/fixtures`.

## Requests

1. Validator: a DOM stub and a runner that executes all 144 example checks exist at `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/658ff14a-2610-461f-9302-e64c02a54c6a/scratchpad/docs-check/` (`dom-stub.js`, `run-examples.mjs`, run with `node run-examples.mjs /path/to/repo`). Copy them into `tests/` if useful for V5; I did not put them in the repo because tests are yours.
2. Manager: ready for F9 after this passes.

## Blocked

Nothing.
