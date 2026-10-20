# Ready: V10 2026-10-20

## Done

Task panel folders on `viz/web.html`, one per series, fed by an `area` field from the watcher.

`viz/watcher.py`:

- `TASK_AREAS = {"D": "Discovery", "V": "Visualization"}` and `task_area(task_id)` (the series letter when it is not in the map). `parse_spec_tasks` adds `area` to every task, so `/state` tasks and the `tasks` change carry it. Nothing else changed.

`viz/web.html`:

- `renderPanel` groups `state.tasks` by `area` in first-seen order into `.folder[data-area][data-closed]` elements: a `.fhead` header (`<b>` name, `.fcounts` with the folder's own non-zero counts joined by ` · `, e.g. `Discovery · 4 done` or `Visualization · 10 done · 1 in progress`, and a chevron) and a `.fbody` holding the V9 task cards unchanged (ID, title, state, click to expand, owner line, owner highlighting on node and row).
- Clicking a header toggles the folder; `.folder.closed .fbody` is hidden so only the header shows. The choice is stored per folder under `localStorage` key `viz-web-folder-closed:<area>` (`1` closed, `0` open; reads and writes guarded, missing or blocked storage means open). Folders start open.
- A task without `area` (an older watcher) falls back to the ID's first letter through the same map, so the page groups correctly against the un-restarted 4780 watcher.
- The panel tab, its counts text, and the collapsed tab are unchanged; `tasks` changes re-render the folders with the stored open/closed choices kept.

Files: `viz/watcher.py`, `viz/web.html`.

## How to test

Fixture replay with a temp copy of SPEC.md, spare port (4780 is the manager's):

```
S=$(mktemp -d); cp SPEC.md $S/SPEC.md
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
python3 viz/watcher.py replay $F --out-dir $S --speed 0
python3 viz/watcher.py serve --port 4792 --no-log --spec $S/SPEC.md --fixture 32813=$S/32813.jsonl --fixture 33993=$S/33993.jsonl &
open http://127.0.0.1:4792/web
curl -s http://127.0.0.1:4792/state | python3 -c "import sys,json; s=json.load(sys.stdin); print(s['task_counts'], [(t['id'], t['area'], t['state']) for t in s['tasks']])"
```

Expected: `/state` tasks carry `area` (`Discovery` for D1, D3, D2, D4; `Visualization` for V0 to V10). The panel shows a `Discovery · 4 done` folder with the four D tasks and a `Visualization · 10 done · 1 in progress` folder with the eleven V tasks, in SPEC order inside each folder; the tab still reads `14 done · 1 in progress · 0 to do`. Clicking the Discovery header hides its four cards and flips the chevron; reloading the page keeps it closed (`localStorage["viz-web-folder-closed:Discovery"] === "1"`); clicking again reopens it. Clicking a V card still expands its text; the tab still collapses the panel. Editing the temp SPEC (`sed -i '' 's/^- \[~\] V10:/- [x] V10:/' $S/SPEC.md`) updates the Visualization header to `11 done` and the tab to `15 done · 0 in progress · 0 to do` within a second, with the folders' open/closed state kept.

Checked here: `/state` as above; screenshots `webfolders-wide.png` (720 px, panel on the right with both folders) and `webfolders-narrow.png` (380 px through the iframe wrapper, panel under the rows) in my scratchpad; the Node harness (`web_harness.mjs` with `web_folders.json` and `web_folders_reload.json`, which seeds `localStorage`) shows: both folders with their counts and all 15 cards, V10 card expanding on click, closing Discovery (`data-closed="1"`, storage key written, header title `show the Discovery tasks`), panel collapse and expand leaving the folder closed, a `tasks` change re-rendering the counts (`Visualization · 11 done`, tab `15 done`) with Discovery still closed and the owner highlight cleared, reopening Discovery; a fresh run with `viz-web-folder-closed:Visualization = "1"` seeded starts with Visualization closed; tasks without `area` plus an `X1` task produce `Discovery`, `Visualization`, and `X` folders.

Suite: `python3 -m pytest tests` → 304 passed, 8 failed, all expected pins:

- `tests/integration/test_web_render.py` (7): `tests/page/render_web.mjs` reads `#plist` children as task cards; they are now `.folder` elements with `.fhead` + `.fbody` (cards inside `.fbody`), so `taskView` crashes on a missing `.tid`. My scratchpad harness has `folderView`, a `clickFolder` step, and an input `localStorage` seed.
- `tests/unit/test_watcher_server.py::test_parse_spec_tasks_without_a_section_or_text` (1): the expected dicts need `"area": "Visualization"`.

## Requests

- Manager: restart the 4780 watcher on the new `viz/watcher.py` so `/state` tasks carry `area` (the page falls back to the ID letter until then, so folders already show).
- Validator: update the web harness for folders (folder view, `clickFolder`, `localStorage` seed), pin the one parser test, add tests for `task_area` (D, V, other letter), folder grouping and counts, closed folder hiding its tasks and persisting through a re-run with seeded storage, blocked storage meaning open.
- Docs (user): plan §4 add `area` to the task fields; plan §6 note the folders and the per-folder `localStorage` keys.

## Blocked

Nothing.
