# Review: V10 2026-10-20

PASS

## Verified against SPEC V10

- Watcher: `task_area` maps `D` to `Discovery`, `V` to `Visualization`, any other letter to the upper-case letter (`X7` → `X`, `q2` → `Q`); `parse_spec_tasks` adds `area` to every task, so `/state` tasks and the `tasks` change carry it. Nothing else in the watcher changed. The repo SPEC.md parses to 16 tasks (D1, D3, D2, D4 under Discovery; V0 to V11 under Visualization), 14 done, V10 in progress, V11 to do.
- `serve --spec` on a temp copy with the fixture replay, spare port 4796 (stopped): `/state` tasks carry `area` as above with counts `{14, 1, 1}`. Driven headless Chrome over the DevTools protocol (scratchpad `cdp_folders.mjs`, profile dir in the scratchpad): the panel shows `Discovery · 4 done` with D1, D3, D2, D4 and `Visualization · 10 done · 1 in progress · 1 to do` with V0 to V11, SPEC order inside each folder; tab `Tasks 14 done · 1 in progress · 1 to do`; both folders start open. Clicking the Discovery header sets `data-closed="1"`, hides `.fbody` (computed `display: none`), flips the chevron to `▸`, sets the title to `show the Discovery tasks` and writes `localStorage["viz-web-folder-closed:Discovery"] = "1"`; a real `Page.reload` comes back with Discovery still closed and Visualization open. Flipping V10 to `[x]` in the copy updated the Visualization header to `11 done · 1 to do` and the tab to `15 done · 0 in progress · 1 to do` 0.1 s after the write, with Discovery still closed; clicking the header again reopened it and wrote `0`. V9 card behaviour inside the folders is unchanged (expand on click, owner line, `.tasked` ring and badge on the viz-builder node and row).
- Screenshots in the scratchpad `v10/`: `webfolders-wide.png` (740 px, both folders open), `webfolders-closed.png` and `webfolders-reloaded.png` (Discovery closed before and after the reload), `webfolders-narrow.png` (380 px, panel under the rows), `webfolders-edited.png`.
- Through the Node harness: tasks without `area` fall back to the ID letter (the un-restarted 4780 case) and an `X1` task gets an `X` folder in first-seen order; folder counts list only non-zero states; closing a folder keeps the panel tab counts, survives expanding a card, collapsing and reopening the panel, and a `tasks` change; a seeded `viz-web-folder-closed:Visualization = "1"` starts that folder closed; blocked storage leaves every folder open.
- Everything from V7 to V9 still renders the same (rows, envelope, arrows, geometry pins, panel tests).

## Tests

- `tests/page/render_web.mjs`: `panel.folders` (`area`, `closed`, `className`, `name`, `counts`, `chevron`, `title`, `clickable`, `tasks`), `panel.tasks` flattened from the folder bodies so the V9 tests read as before, `clickFolder` step, `clickTask` finds cards inside folders.
- `tests/unit/test_watcher_server.py`: `test_parse_spec_tasks_without_a_section_or_text` pinned with `area`; new `test_task_area_maps_the_series_letter` (five cases) and `test_parse_spec_tasks_carries_the_area`; the repo-spec test checks every task's area against its series.
- `tests/integration/test_web_render.py`: `test_panel_groups_tasks_into_folders_with_their_own_counts`, `test_folders_follow_the_area_field_and_name_other_series_after_the_letter`, `test_closing_a_folder_hides_its_tasks_and_the_choice_is_remembered`, `test_folder_state_survives_a_rerun_with_stored_choices_and_blocked_storage_means_open`.
- `python3 -m pytest tests` → 322 passed.

## Notes

- At 740 px the Visualization header's counts are cut with an ellipsis (`10 done · 1 in progress · ...`), so the `1 to do` part is only readable at the narrow width or after the window grows; the header's title is the show/hide hint, not the counts. Counts match SPEC.md, so this is not a failure; a follow-up could wrap the counts or put the full text in the header title.
- With blocked `localStorage` the folders cannot be closed at all (the click writes nothing and the re-render reads open), unlike the panel tab, which keeps its state in a variable. Not in the SPEC; fine for a private-window edge case.
- The 4780 watcher still runs the pre-V10 `viz/watcher.py`, so its `/state` tasks have no `area` and the page groups by the ID letter; the manager restarts it when convenient (builder request).
- Docs user items: plan §4 add `area` to the task fields; plan §6 note the folders and the `viz-web-folder-closed:<area>` keys; earlier items unchanged.
