# Review: V14 2026-10-20

PASS

## Verified against SPEC V14

- Linger: through the harness on the round trip, the manager → builder arrow is at 0.972 right after the read, 0.550 with its `second hello … ✓✓ Read` label at +5 s and +29 s, gone at +31 s; PENDING and IN_INBOX unchanged; the FAILED arrow still stays until resolved; eleven minutes later every arrow is gone (horizon). Headless Chrome on spare port 4796 (stopped) with the replay cut at 04:31:15.000 shows the muted arrow and label on the pod (`v14/webv14-15.000.png` in the scratchpad), at 17.700 the reply arrow at 0.776 starting its own 30 s.
- Reply on the reversed pair: before the reply the old arrow sits at 0.550; on the reply frame (sent 16.750) the reply is PENDING at 1 on the upper lane (control point above the cards) and the old arrow drops to the lower lane (control point below) at 0.550, the pod graph grows to 206 px, both labels are inside the graph and clear of the cards; +0.3 s the old arrow is at 0.500; +0.7 s it is gone and the graph is back to 150 px; the reply read is 1.000 and 0.550 ten seconds later. A newer message on the same pair replaces the lingering READ arrow (one path, the newer label with `+1`).
- Ten-session compact view: the two READ arrows now linger (908>906 at 0.925, 904>905 at 0.550), ten arrows, six shown labels incl. `second hello ✓✓ Read`, no label over a node, no arrow through a node. Six and seven nodes: four arrows (three READ lingering, one IN_INBOX), no overlap, labels clear.
- Hover: through the harness `mouseenter` adds `hover` (full text shown, title still `click for the full text`), the class survives a render tick and a `tasks` change, `mouseleave` removes it, click pins `open` and leaving keeps it, hovering another card while one is pinned shows both. Headless Chrome at 720 px with a temp SPEC copy: moving the pointer onto V9 makes `.tfull` `display: block`, the card grows to 505 px, its right edge (714) stays inside the panel (720), the text is not clipped and the title wraps; moving away returns `display: none`; click then leave keeps it open (`v14/webv14-17.700-hover.png`).

## Tests

- `tests/page/render_web.mjs`: `hoverTask` / `leaveTask` steps, `hoverable` on task cards.
- `tests/integration/test_web_render.py`: re-pins in the read, reply, idle-notice, round-end, ten-session and ring tests (lingering READ arrows, lanes, graph height); new `test_read_arrow_lingers_thirty_seconds_muted_with_its_label`, `test_reply_on_the_reversed_pair_fades_the_read_arrow_within_600ms_and_takes_the_upper_lane`, `test_newer_message_on_the_same_pair_replaces_the_lingering_read_arrow`, `test_hovering_a_task_shows_its_full_text_until_the_pointer_leaves_and_click_pins`, `test_task_hover_and_wrap_rules_are_in_the_page_css`; helper `control_y`.
- `python3 -m pytest tests` → 354 passed.

## Notes

- The pod graph grows from 150 to about 206 px for the 600 ms fade window and shrinks back, so the two-session view jumps briefly on every reply; a ring is unaffected. Cosmetic, the SPEC asks for the lower label to be inside the graph.
- In the harness the feed clock can step backwards between cut steps (frames carry older timestamps than the advanced wall), which is why the opacity at the manager turn end reads 0.652 after 0.550; a live feed never does that, so the test only bounds it.
- The lingering arrow is drawn 2.4 wide while it is the newest message and 1.5 once a newer one exists; the muted 0.55 opacity is the only "muted" cue.
- Docs user items (from ready.md): plan §6 replace the 3 s flash with the 30 s linger and the reversed-reply rule, note the hover expansion; earlier items unchanged.
