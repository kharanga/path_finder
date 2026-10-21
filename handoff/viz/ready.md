# Ready: V17 2026-10-21

## Done

Task hover shows the title only; P-series tasks get a Packaging folder.

`viz/watcher.py`:

- `TASK_AREAS` adds `"P": "Packaging"`, so `task_area("P1")` is `Packaging` and the `area` field on P tasks puts them in their own folder. Owner stays `null` for the P series (`TASK_OWNERS` unchanged; not in this task).

`viz/web.html`:

- Hovering a task card no longer shows the SPEC text: the `.task.hover .tfull` / `.task:hover .tfull` rules are gone, `.tfull` shows only with `.open` (the V9 click pin). Hover keeps the `hover` class (CSS `:hover` and the `hoveredTaskId` class that survives re-renders) and the only effect is `.ttitle { white-space: normal }`, so a title cut off by the ellipsis wraps inside the card and shows in full; a title that already fits does not change. The wrapped title stays inside the card's grid column, so it is never clipped by the panel edge. Click behaviour is unchanged (`open` toggles the full SPEC text; the card tooltip now reads `click for the full SPEC text`).
- The page's fallback area map (used when a task carries no `area`) also knows `P: "Packaging"`.

Files: `viz/watcher.py`, `viz/web.html`.

## How to test

Fixture replay with a temp copy of SPEC.md, spare port (4780 is the manager's):

```
S=$(mktemp -d); cp SPEC.md $S/SPEC.md
F="--fixture 32813=tests/fixtures/viz/round_trip_manager_32813_33993.jsonl --fixture 33993=tests/fixtures/viz/round_trip_builder_32813_33993.jsonl"
python3 viz/watcher.py replay $F --out-dir $S --speed 0
python3 viz/watcher.py serve --port 4792 --no-log --spec $S/SPEC.md --fixture 32813=$S/32813.jsonl --fixture 33993=$S/33993.jsonl &
open http://127.0.0.1:4792/web
```

Expected: the panel has Discovery, Visualization, and Packaging folders (P1 in progress, P2 to do). Hover V11 (`idle sessions show nothing unless waiting`, cut off at 250 px): the title wraps onto two lines and nothing else appears; move away and it collapses. Hover V9 (`task panel`, fits): nothing changes. Click V11: the full SPEC text opens under it and stays after the pointer leaves; click again to close.

Checked here: `/state` from the replay shows areas Discovery, Packaging, Visualization with P1 `in_progress` and P2 `todo`; `cdp_hover.mjs` in headless Chrome at 720 px: V11 before hover is truncated (`scrollWidth > clientWidth`), on hover `white-space: normal`, title 17 → 35 px, card 32 → 49 px, `.tfull` `display: none`, card inside the panel; after the pointer leaves it is truncated again; after a click `.tfull` is `block` (card 703 px); V9 before, during, and after hover is identical (17 px title, 32 px card, `.tfull` none) and shows the full text only after the click. Harness `web_hover.json`: `hover` class on enter, off on leave, `open` on click, kept across a render tick.

Suite: `python3 -m pytest tests` → 366 passed, 3 failed, all expected pins in `tests/integration/test_web_render.py`: `test_task_hover_and_wrap_rules_are_in_the_page_css` and `test_hovering_a_task_shows_its_full_text_until_the_pointer_leaves_and_click_pins` pin the V14 hover (full text on hover) that V17 replaces; `test_panel_lists_every_task_with_state_words_and_counts` pins the card tooltip text `click for the full text` (now `click for the full SPEC text`).

## Requests

- Manager: restart the 4780 watcher on the new `viz/watcher.py` for the Packaging folder (until then P tasks fall back to the page's own map, so the folder already shows); the page change is live.
- Validator: re-pin the three tests; the hover test should check the `hover` class with `.tfull` hidden and `.open` with it shown; `TASK_AREAS` gains `P` (`task_area("P1") == "Packaging"`).
- Docs (user): plan §6 replace the V14 hover note with title-only hover; plan §4 add Packaging to the area map.

## Blocked

Nothing.
