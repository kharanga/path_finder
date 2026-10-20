# Ready: V9 2026-10-20

## Done

Task panel on `viz/web.html`, fed by the watcher from SPEC.md.

`viz/watcher.py`:

- `parse_spec_tasks(text)` reads the `## Tasks` section (until the next `## ` heading) and returns one row per `- [ ] ID: text` / `- [x]` / `- [~]` line: `id`, `state` (`todo`, `done`, `in_progress`), `title` (the text up to the first period followed by a space or the end), `text` (the full line after the ID), `owner` (`discovery-builder` for D-series, `viz-builder` for V-series, otherwise null). `task_counts(tasks)` gives `{done, in_progress, todo}`.
- `SpecTasks` re-reads the file only when its mtime or size changes, checked on every 250 ms poll (`Watcher.refresh_tasks` in `poll_once`). When the parsed list differs it emits one change: `{"event": "tasks", "at", "source": "spec", "source_pid": null, "tasks": [...], "task_counts": {...}, "spec_path"}`. The first poll always emits it, so a fresh `/events` subscriber gets the list after the snapshot.
- `/state` carries `tasks`, `task_counts`, and `spec_path` next to `sessions`, `messages`, `sources`.
- `serve --spec PATH` points the watcher at another file (default `SPEC.md` next to `viz/`); a temp copy is what the tests and the edit check use.

`viz/web.html`:

- The window is now `.main` (bar, web, caption, strip, rows) plus `aside#panel`. On windows 640 px and wider the panel sits on the right (250 px); below that it sits under the activity rows.
- Panel tab: `Tasks · <n> done · <n> in progress · <n> to do` and a chevron; clicking it collapses the panel to the tab alone (a vertical tab on the right on wide windows, a one-line bar on narrow ones) that still shows the counts. The choice is remembered in `localStorage` (guarded; defaults to open).
- List: one card per task with the ID in monospace, the short title (ellipsised on one line), and the state in words: `Done` green, `In progress` blue, `To do` muted. In-progress cards carry the owner line with the owning session's dot and label when that session is live (role, label, or name containing `viz-builder` / `discovery-builder`), otherwise the owner name. Clicking a card expands the full SPEC text under it; clicking again collapses it.
- In-progress tasks highlight the owner's node and activity row (`.tasked`: blue border and ring) and add a small `V9`-style badge next to the label on both.
- A `tasks` change on `/events` replaces the list and re-renders; everything else on the page is unchanged.

Files: `viz/watcher.py`, `viz/web.html`.

## How to test

Fixture replay with a temp copy of SPEC.md, spare port (4780 is the manager's):

```
S=$(mktemp -d); cp SPEC.md $S/SPEC.md
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
python3 viz/watcher.py replay $F --out-dir $S --speed 0
python3 viz/watcher.py serve --port 4792 --no-log --spec $S/SPEC.md --fixture 32813=$S/32813.jsonl --fixture 33993=$S/33993.jsonl &
open http://127.0.0.1:4792/web
curl -s http://127.0.0.1:4792/state | python3 -c "import sys,json; s=json.load(sys.stdin); print(s['task_counts'], [(t['id'], t['state']) for t in s['tasks']])"
sed -i '' 's/^- \[~\] V9:/- [x] V9:/; s/^- \[x\] V8:/- [ ] V8:/' $S/SPEC.md
```

Expected: the panel lists all 14 tasks (D1, D3, D2, V0 to V6, D4, V7, V8, V9) with the states from the file, the tab reads `13 done · 1 in progress · 0 to do`, V9 shows `In progress` with owner `viz-builder`; after the `sed` the panel shows V9 `Done` and V8 `To do` and the tab `13 done · 0 in progress · 1 to do` within a second (one `tasks` frame on `/events`). Clicking V9 expands its full text; clicking the tab collapses the panel to the counts. In the fixture replay no live session matches `viz-builder`, so nothing is highlighted; on 4780 the viz-builder node and row carry a `V9` badge and the blue ring while V9 is `[~]`.

Checked here: `/state` keys and counts as above; the edit produced one `tasks` frame on a subscribed `/events` with `V8 todo, V9 done` (captured by `curl -N` while editing); screenshots `webpanel-wide.png` (720 px, panel on the right), `webpanel-narrow.png` (380 px through the iframe wrapper, panel under the rows), `webpanel-edited.png` (after the edit) in my scratchpad; the Node harness (`web_harness.mjs` with `web_tasks.json`, snapshot with the fake builder relabelled `viz-builder`) shows the tasked node and row with the `V9` badge, the V9 card expanding on click, the panel collapsing and expanding on the tab with the counts kept, and a `tasks` change clearing the highlight and flipping the states.

Suite: `python3 -m pytest tests` → 264 passed, 14 failed, 10 errors, all expected pins:

- `tests/integration/test_web_render.py` (8 failed, 10 errors): `tests/page/render_web.mjs` has no `#panel`/`#ptab`/`#plist` elements and no `localStorage`; my harness in the scratchpad (same name, with `panel`, `clickTab`, `clickTask`) covers it.
- `tests/unit/test_watcher_server.py` (6): the first poll now also emits the `tasks` change (reading the repo SPEC.md by default), so counts rise by one and change lists start with `('tasks', None)`; tests constructing `Watcher(...)` can pass `spec_path=None` to opt out, or pin the new frame.

## Requests

- Manager: restart the 4780 watcher on the new `viz/watcher.py` so `/state` carries `tasks`; until then the panel reads `No tasks in SPEC.md`.
- Validator: re-pin the six watcher tests (or pass `spec_path=None`), replace the web harness for the panel, add tests for `parse_spec_tasks` (states, title cut at the first period, owner by series, section bounds), `SpecTasks.refresh` (mtime change, unchanged content emits nothing), and the `serve --spec` edit check.
- Docs (user): plan §4 add `tasks`, `task_counts`, `spec_path` to `/state` and the `tasks` change; note the `[~]` convention.

## Blocked

Nothing.
