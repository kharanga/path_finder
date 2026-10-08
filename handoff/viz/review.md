# Review: V4 2026-10-08

PASS (overnight acceptance; the live round-trip check against frames 1 to 4 is deferred to the user)

## Checked against the overnight acceptance

Replaying the fixtures through `serve --fixture` on spare ports, every `/state` snapshot and every `/events` session frame carries `pid`, `label`, `role`, `name`, `cwd`, `status`, `inbox`, `last_text`, and `watching`.

Stepping `replay --until` through the round trip and sampling `/state` at each stop:

| Frame | 32813 fake manager | 33993 fake builder |
| :- | :- | :- |
| 1 (empty) | IDLE, inbox 0, no last line, watching [] | IDLE, inbox 0, no last line |
| 2 (after send 10.318) | WORKING, last "second hello to fake-session-builder", watching [33993] | IDLE, inbox 0 |
| 3 (after enqueue 10.817) | unchanged | IDLE, inbox 1, no last line |
| 4 (after delivery 11.097) | unchanged | WORKING, inbox 0, last "Hi again from fake-session-manager…" |
| final | IDLE, watching [], last "Hi again from fake-session-builder…" | IDLE, last "Second hi back to fake-session-manager" |

The continuous run (`--speed 10 --max-gap 0.5`) produced 24 frames: statuses IDLE and WORKING, inbox values 0 and 1, 8 frames with a non-empty `watching`, all fields present. The replayed files are in timestamp order with the untimestamped `agent-name` lines carried at the previous line's time.

Page: neither the Claude in Chrome extension nor headless Chrome worked from this session (headless Chrome hangs on the page's EventSource under this sandbox), so the page script was run as-is in Node against a DOM stub fed with the real snapshots and event frames (`tests/page/render_page.mjs`). At each frame the capsules show what ready.md describes: label from identity, Working or Idle pill with the green class, the inbox badge only when `inbox` > 0, the last line truncated at 90 characters with the full text as the tooltip, "👁 watching fake builder" resolved from the PID, dashed border for an unidentified session, `id="session-<pid>"` and `data-pid` on every capsule, header counts and the live or reconnecting indicator. Applying the event stream as deltas to the frame 1 snapshot renders identically to the final snapshot; a `snapshot` frame replaces state; `session_removed` drops the capsule.

Nothing under `~/.claude` or `discovery/` is written. `viz/index.html` is new, `viz/watcher.py` changed.

## Tests

`python3 -m pytest tests` runs 181 tests (17 new for V4), all passing, in about 6 s.

- `tests/unit/test_replay.py`: time ordering across files, carry of untimestamped lines, malformed lines kept, fixture order matches the doc timeline (45 lines), `--speed 0`, `--until` freezing and output truncation, sleep scaling and cap, parser defaults.
- `tests/integration/test_page_render.py` with `tests/page/render_page.mjs`: frames 1 to 4 and final, delta stream equals final snapshot, snapshot frame, `session_removed`, unidentified session with badge 3 and a 120 character last line, empty state and reconnecting indicator. Skipped when `node` is absent.

## Notes, not failures

1. Frame count depends on the live registry: ready.md expects 25 frames, this run gave 24. The difference is the manager's `agent-name` change, which only appears when PID 32813 is not live in the real registry under the same name (fixture mode reads the registry for names). Both counts are correct for their environment; the assertion that matters is the field set, which held.
2. Morning live check for the user, as the builder wrote: stop the D2 server, run `watcher.py serve --root fake_session` on 4780, open the page, send one message with `notify_when_idle` between the fake sessions, compare with frames 1 to 4.
3. For the manager: the "nine UI flow frames" named in plan §6 and SPEC do not exist in `docs/`. The frames used tonight are derived from §6 and the round-trip timeline. If the user has the original frames, they belong in `docs/` before V5 is judged.
4. Port handover and `discover.py ui` retirement remain in the builder's Requests for the manager and the discovery-builder.
