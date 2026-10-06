# Review: F2, F3 2026-10-05 (round 2)

PASS

# Review: F1 2026-10-05 (re-review)

PASS

## What was checked in round 2

- Round 1 failure 1: `docs/frontend/render.md` many.json paragraph now says pid 41008, `add-semantic-similarity…`, title `add-semantic-similarity-scores-28 in add-semantic-similarity-scores`. Matches the rendered output.
- Round 1 failure 2: `frontend/fixtures/many.json` messages now have string `from`/`to`. All four fixtures validate against `webhook/schema.js` (0 of 32 events rejected), and both many.json messages reach `state.messages`.
- Round 1 note 1: viewBox is `0 0 1360 1000`, ring at (680, 500) radius 340, docs updated. Label boxes for 1 to 15 bodies with 24-character names and roles span x 18 to 1342 at an estimated 0.55em per character, inside the box, with 0 overlaps.
- Every example in `docs/frontend/render.md`, `layout.md`, and `state.md` re-run and matching, including ghost removal with `ghostMs: 10`, ghost revival with `ghostMs: 10000`, and the empty-state label and dashed ring.
- `import("./frontend/app.js")` resolves in Node without a DOM.

Browser-only items (glow, pulse, fade timing, clipping at narrow widths) were checked by reading `orbit.css` only. This session has no browser automation.

## Open for the manager

Round 1 note 2 stands: "stable position across restart" holds at the folder-group level. The slot inside a folder follows name order, so a restarted session with a new name can swap places with a sibling. SPEC §4 supports the group-level reading. Manager decides whether F2 needs more.
