# frontend docs

Owner: frontend-builder.

One markdown file per module in `frontend/`. Expected files as the area grows:

- `layout.md`: ring placement keyed by folder.
- `state.md`: snapshot and event reducer.
- `render.md`: bodies, particles, threads, fades, reduced-motion behavior.
- `timeline.md`: history scrubbing.
- `panel.md`: message detail panel.

Each public function or class is documented with:

- What it does
- Inputs: name, type, and meaning
- Output: type and meaning
- Errors: what it can throw and when
- Example: a realistic input and the expected output

Docs are updated in the same task as the code. The validator checks every example.
