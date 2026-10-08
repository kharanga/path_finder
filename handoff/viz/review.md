# Review: V6 2026-10-08

PASS

## Checked against SPEC.md V6

- Event log written during the V3-style test: `serve --fixture … --log $L/events.jsonl` on a spare port, `/state` returned 2 sessions, one line appended to the builder transcript, and the log held 26 lines ending with `session 33993 WORKING 2026-10-08T05:00:01.000Z`. Every line has `event` and `at` plus the full object. The last SSE frame received by a subscriber equals the last log line. A second run appended 26 more (52 total). `--no-log` writes nothing. Without `--log` the file is `viz/events.jsonl` next to the script (verified in the integration sandbox, not in the repo).
- Sanitized fixtures under `tests/fixtures/`: `tests/fixtures/viz/round_trip_manager_32813_33993.jsonl` and `round_trip_builder_32813_33993.jsonl`, plus `tests/fixtures/discovery/`. No home path, user name, or email remains. All are tracked in git already (`git ls-files tests/fixtures`), as are `viz/index.html`, `viz/watcher.py`, and every test file. `viz/events.jsonl` is in the uncommitted `.gitignore` change and is not in the tree.
- V5 note 1 fixed: with the fixtures replayed to 11.200, `state` shows one row `693b9bd4 READ "second hello to fake-session-builder" pending:toolu_ accepted_at null`; the full replay sets `accepted_at` 11.281 on that same row. The page label no longer flips to the body. Snapshots stay identical in both feed orders.
- Nothing under `~/.claude` or `discovery/` is written. Only `viz/watcher.py` changed.

## Tests

`python3 -m pytest tests` runs 201 tests (10 new for V6), all passing, in about 7 s.

- `tests/unit/test_state_model.py`: receiver read adopts the sender's pending row (one row, summary and `sent_at` present from the first READ, tool result still sets `accepted_at`), oldest unmerged send to that receiver is chosen, failed and already-merged sends are skipped, the fixture round trip never has more than one row per message at any step.
- `tests/unit/test_watcher_server.py`: `emit` writes one JSON line per change and publishes, lazy open and `close`, no file without a log path, log equals stream for the fixture round trip and is append-only across watchers, parser defaults for `--log` and `--no-log`.
- `tests/integration/test_serve.py`: the V3-style test with `--log` (last log line equals the streamed change, 27 lines, doubled on a second run), default log next to the script, `--no-log` disables it.
- The two page tests pinning the old transient label are updated to the adopted summary; the V5 frozen-frame row for 11.200 now holds as the builder wrote it.

## Notes, not failures

1. For the manager: commit the `.gitignore` change (`viz/events.jsonl`, `__pycache__/`, `.hypothesis/`, `.pytest_cache/`) with V6.
2. The log count (26 here) varies with the live registry exactly as the V4 frame count does; the integration test runs with an empty registry and pins 27 including the appended line.
3. Unchanged user and manager items: port handover (`discover.py ui --stop`, `watcher.py serve` on 4780, delete `discovery/index.html`), `discover.py ui` retirement, docs items (plan §5 enqueue promotion, message-format §3.1 `remove`, jsonl spec `progress` and `isMeta`, nine UI flow frames), and the morning live checks for V4 and V5.
