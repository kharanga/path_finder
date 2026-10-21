# Review: V17 2026-10-21

PASS

## Verified against SPEC V17

- Watcher: `task_area("P1")` and `task_area("p2")` are `Packaging`; `/state` on a temp copy of SPEC.md (spare port 4796, stopped) lists areas Discovery, Packaging and Visualization with P1 `in_progress` and P2 `todo`, owner `null`. The page shows a `Packaging · 1 in progress · 1 to do` folder with P1 and P2 after Discovery and Visualization, and a task without `area` falls back to the page's own map (`P` → Packaging).
- Hover in headless Chrome at 720 px: V11 (`idle sessions show nothing unless waiting`, truncated with the ellipsis before hover) wraps on hover (`white-space: normal`, title 17 → 35 px, card 32 → 49 px, no longer truncated), `.tfull` stays `display: none`, the card stays inside the panel; leaving restores the ellipsis; a click opens the full SPEC text (card 703 px) and it stays after the pointer leaves; a second click closes it. V9 (`task panel`, fits): hover changes nothing (17 px title, 32 px card, `.tfull` none) and the full text appears only after the click. The card tooltip reads `click for the full SPEC text`, `click to collapse` when open. Screenshots `v17/webv17-hover.png` and `webv17-clicked.png` in the scratchpad.
- Through the harness: `mouseenter` adds `hover` without `open`, the class survives a render tick and a `tasks` change, `mouseleave` removes it, click toggles `open` and leaving keeps it; the CSS has `.task.open .tfull { display: block; }` with no `:hover`/`.hover` rule for `.tfull`, the three-selector `white-space: normal` rule for `.ttitle`, and the title's `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` default.

## Tests

- `tests/integration/test_web_render.py`: tooltip re-pin; `test_hovering_a_task_marks_it_hover_without_opening_it_and_click_pins` (was the V14 full-text hover test); `test_task_hover_wraps_the_title_only_and_click_opens_the_text_in_the_page_css`; the folder test gains a `P1` task without `area` landing in a Packaging folder.
- `tests/unit/test_watcher_server.py`: `task_area` cases for `P1`/`p2`; the repo-SPEC pin requires a Packaging area and a `null` owner for P tasks.
- `python3 -m pytest tests` → 396 passed (includes the new P1 tests).

## Notes

- The harness cannot see CSS, so the hover's visual effect (title wrap, full text hidden) is pinned by the CSS rules and by the real-browser check above; the class behaviour is pinned in the harness.
- P-series tasks have no owner, so an in-progress P task highlights no node or row; the SPEC leaves owners unchanged for V17.
- The 4780 watcher still runs the pre-V17 `viz/watcher.py`; its P tasks already land in a Packaging folder through the page's fallback map, and `/state` gains the area after the manager restarts it (builder request).
- Docs user items (from ready.md): plan §6 replace the V14 hover note with title-only hover; plan §4 add Packaging to the area map; earlier items unchanged.
