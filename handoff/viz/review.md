# Review: V9 2026-10-20

PASS

## Verified against SPEC V9

- Watcher: `parse_spec_tasks` reads only the `## Tasks` section, one row per `- [ ]`/`[x]`/`[~]` line with `id`, `state` (`todo`, `done`, `in_progress`), `title` cut at the first period followed by a space or the end (`discover.py` and `v1.2` do not cut), `text`, `owner` by series (D → discovery-builder, V → viz-builder, other → null); unknown marks, indented lines and lines without an ID are skipped. `task_counts` gives `{done, in_progress, todo}`. `SpecTasks.refresh` re-reads on mtime or size change only, returns True only when the parsed list differs (a same-content rewrite emits nothing), and goes back to an empty list when the file disappears. The repo SPEC.md parses to 14 tasks (D1, D3, D2, V0 to V6, D4, V7, V8, V9), 13 done and V9 in progress, every one with a title and an owner.
- `serve --spec` on a temp copy with the fixture replay, spare port 4797 (stopped): `/state` carries `tasks`, `task_counts` `{13, 1, 0}` and `spec_path`; the `/events` snapshot frame carries the same; flipping V9 to `[x]` and V8 to `[ ]` in the copy produced exactly one `tasks` frame (`source: spec`, `source_pid: null`) within 0.01 s of the write plus the poll, with V8 `todo`, V9 `done` and counts `{13, 0, 1}`; `/state` agreed; writing the same content again produced no frame. The first poll of a `Watcher` with a spec emits the `tasks` change right after the registry changes; `spec_path=None` opts out and leaves empty tasks in the snapshot.
- Page: screenshots `/private/tmp/claude-501/-Users-khangnguyen-Documents-path-finder/9e6343e0-d664-4782-b79a-a6cac9debb65/scratchpad/webpanel-wide.png` (740 px, panel on the right with all 14 tasks, tab `Tasks 13 done · 1 in progress · 0 to do`, V9 `In progress` with owner `viz-builder`), `webpanel-narrow.png` (380 px through the iframe wrapper, panel under the activity rows), `webpanel-edited.png` (after the edit: V8 `To do`, V9 `Done`, tab `13 done · 0 in progress · 1 to do`). Through the Node harness: the list shows ID, short title and state words with the right classes; an in-progress task shows the owner's dot and label when a live session's role, label or name contains the owner, otherwise the owner name; clicking a card expands its full text and clicking again folds it, independently per card; clicking the tab collapses the panel to the tab with the counts kept and `localStorage` set to `1`, clicking again reopens and sets `0`; a remembered `1` starts collapsed; a throwing `localStorage` leaves the default open and toggling still works; the owner's node and activity row carry the `.tasked` ring and a `V9` badge with the tooltip `in progress: V9`, and a `tasks` change that marks V9 done clears both and updates the list and counts; an empty list reads `No tasks in SPEC.md` and a `snapshot` event fills it.
- Everything from V7 and V8 still renders the same (rows, envelope, arrows, geometry pins).

## Tests

- `tests/unit/test_watcher_server.py`: the transcript-only `Watcher` tests pass `spec_path=None`; new `test_parse_spec_tasks_reads_only_the_tasks_section`, `test_parse_spec_tasks_without_a_section_or_text`, six `task_title` cases, `test_task_counts`, `test_parse_repo_spec_has_every_task_with_a_known_state`, `test_spec_tasks_refresh_follows_the_file`, `test_spec_tasks_payload_is_a_copy`, `test_watcher_emits_the_tasks_change_on_the_first_poll_and_on_edits`, `test_watcher_without_a_spec_emits_no_tasks_change_and_empty_tasks`, `test_watcher_default_spec_path_is_the_repo_spec`; the snapshot-keys pin includes the three new keys.
- `tests/integration/test_serve.py`: `test_serve_spec_exposes_tasks_and_streams_an_edit_within_a_second`, `test_serve_without_a_spec_file_serves_empty_tasks`.
- `tests/page/render_web.mjs`: panel elements, `localStorage` stub (preset or throwing), `clickTab`, `clickTask`, task cards, node and row badges.
- `tests/integration/test_web_render.py`: seven panel tests (list and counts, owner highlight and clearing on a `tasks` change, owner fallback, owner match on role/label/name, expand and collapse, remembered and blocked storage, empty list and snapshot).
- `python3 -m pytest tests` → 312 passed.

## Notes

- A `/events` subscriber that connects after the first poll gets no `tasks` frame; the `snapshot` frame it gets first carries `tasks`, which is what the page uses. ready.md's "a fresh subscriber gets the list after the snapshot" holds only for a subscriber present at the first poll.
- With a missing or unreadable SPEC the watcher never emits a `tasks` frame (no signature change), so the panel reads `No tasks in SPEC.md`; a file that appears later is picked up on the next poll.
- Owner matching is a substring test on role, label and name, first live session wins; a label such as `viz-builder-2` would also match. Fine for this team.
- The collapsed panel keeps the task cards in the DOM (hidden by CSS). Cosmetic.
- The `[~]` convention is the manager's; SPEC.md currently marks V9 `[~]`, which is what the 4780 page will highlight on the viz-builder node and row until the manager flips it on PASS.
- Docs user items: plan §4 add `tasks`, `task_counts`, `spec_path` and the `tasks` change; note the `[~]` convention; earlier items unchanged.
