# Review: V5 2026-10-08

PASS (overnight acceptance; the live round-trip check against frames 2 to 9 is deferred to the user)

## Checked against the overnight acceptance

Replaying the fixtures through `serve --fixture` on spare ports (`--speed 10 --max-gap 0.4`), the `/events` stream carried 8 message frames, every one with `key`, `pending_key`, `kind`, `stage`, `from_pid`, `to_pid`, `to`, `summary`, `body`, `reason`, `sent_at`, `accepted_at`, `enqueued_at`, and `read_at`, alongside the V4 session fields.

Stage sequence on the stream, in order: first message PENDING at 10.318, IN_INBOX on the builder's enqueue at 10.817, IN_INBOX on the manager's result at 11.281, READ at 11.097 (builder file fed after the manager's); reply READ at 17.638 from the manager's read, PENDING at 16.750 and READ at 17.811 from the builder's side merging on `msg_id`; one `idle_notice` READ from 33993 to 32813 at 21.055 with summary "fake-session-builder is idle". Final `/state`: message READ 32813 to 33993, message READ 33993 to 32813, idle_notice READ 33993 to 32813, both sessions IDLE with empty `watching`.

`replay --until 20.100` then `--after 20.100` continues a frozen frame: the second run appends 10 lines without truncating and the page receives them as live deltas (watching cleared, notice READ, manager IDLE). `/events` now answers `HTTP/1.0 200` without a `Connection` header.

Page: the extension and headless Chrome are still unusable from this session, so `tests/page/render_page.mjs` was rebuilt per the builder's shim requirements (SVG layer, `createElementNS`, `createTextNode`, `setAttribute`, `classList`, `getBoundingClientRect`, `window`, timer-based coalescing with controllable timers) and the page script was run unchanged over the real snapshots and event frames:

| Frame | Rendered |
| :- | :- |
| 2 (10.500) | dotted PENDING line manager to builder, tag "… second hello to fake-session-buil…", watch line, manager Working |
| 3 (11.000) | IN_INBOX line, tag "✓ second hello…", builder badge 1 |
| 4 (11.200) | READ line, tag "✓✓ Hi again from fake-session-manage…" (see note 1), builder Working |
| 5 to 7 (17.700) | two READ lines in opposite directions, offset so both are visible, both Working |
| 8 (freeze 20.100, then `--after`) | watch line gone, dashed idle_notice line with "fake-session-builder is idle", gone after 4 s |
| 9 (final) | two READ lines, no watch, no notice |

Also verified: a snapshot whose `generated_at` is within 4 s of the notice's `read_at` shows the notice once and a later load does not; clicking a tag opens the panel with the pair history; a FAILED message draws a red line with "✗" and the reason in the tooltip; a message whose `to_pid` is unresolved is matched by name with a `[ref]` suffix stripped.

Nothing under `~/.claude` or `discovery/` is written. `viz/index.html` and `viz/watcher.py` changed.

## Tests

`python3 -m pytest tests` runs 191 tests (10 new for V5), all passing, in about 7 s.

- `tests/page/render_page.mjs`: rewritten for the SVG layer. Reports capsules, lines (class and coordinates), tags (class, text, tooltip, clickable), and the panel. Supports feeding frames, clicking a tag, and advancing timers.
- `tests/integration/test_page_render.py`: the V4 tests updated for "live · N events" and nine new tests for frames 2 to 9, notice lifetime, panel, failed and unresolved messages.
- `tests/unit/test_state_model.py`: enqueue now asserted to promote PENDING to IN_INBOX and to leave READ alone.

## Notes, not failures

1. Cosmetic, for the builder: between the receiver's read and the sender's tool result (11.097 to 11.281 and 17.638 to 17.811 in the fixtures, under 200 ms live) the pair's latest row is the receiver-created one, which has no `summary`, so the connector label shows the body ("✓✓ Hi again from…") and then switches back to the summary when the sender's result merges. The frozen-frame table in ready.md says "✓✓ second hello…" at 11.200; the page shows the body there. Pinned in `test_frame_4_read_connector_shows_body_until_sender_result_merges`. A page-side fix is to keep the previous label for a pair while the new row has no summary.
2. User item (docs/): `docs/plan-visualization.md` §5 should add "receiver enqueue → IN_INBOX when still PENDING", as the builder requested.
3. Unchanged from V4: port handover, `discover.py ui` retirement, deletion of `discovery/index.html`, and the nine UI flow frames absent from `docs/`.
4. Morning live check for the user: stop the D2 server, run `watcher.py serve --root fake_session` on 4780, open the page, send one message with `notify_when_idle` between the fake sessions, compare with frames 2 to 9; the notice line is the one thing only a real browser shows.
