# Review: V2 2026-10-08

PASS

## Checked against SPEC.md V2

- Sessions keyed by PID, messages keyed by `msg_id`, socket to PID map (`pid_from_socket` parses the socket; names resolve through `pid_by_name` from registry, `agent-name`, `origin.name`, and `from-name`; a `name [ref]` target is stripped). Stages PENDING, IN_INBOX, READ, FAILED. Idle notices as one-shot `idle_notice` messages.
- Captured fixtures (manager 29 lines, builder 16 lines, extracted with the script in ready.md) yield exactly two messages READ and one idle notice:

| kind | stage | from, to | sent_at | enqueued_at | read_at | accepted_at |
| :- | :- | :- | :- | :- | :- | :- |
| message `693b9bd4` | READ | 32813 to 33993 | 10.318 | 10.817 | 11.097 | 11.281 |
| message `f5ac2c3a` | READ | 33993 to 32813 | 16.750 | 17.590 | 17.638 | 17.811 |
| idle_notice | READ | 33993 to 32813 | 21.055 | null | 21.055 | null |

  Every timestamp matches the log in `docs/cross-session-message-format.md` §1.
- Sessions: both IDLE, inbox 0, `watching` empty; manager `last_text` starts "Hi again from fake-session-builder", builder `last_text` is "Second hi back to fake-session-manager". Manager's `watching` holds 33993 from 10.318 until the notice at 21.055.
- Order independence: builder-first and manager-first give the same snapshot apart from `last_seen_at`. Receiver-first merge on `msg_id` keeps sender-owned fields and stage READ.
- `--events` prints 23 change lines; manager inbox goes 0, 1, 0 around each enqueue and dequeue; `remove` counts as inbox minus one per the manager's decision, floored at 0.
- FAILED on `success: false` and on an `is_error` tool_result without `toolUseResult`.
- Nothing under `~/.claude` or `discovery/` is written. Only `viz/watcher.py` changed.

## Tests

`python3 -m pytest tests` runs 146 tests (40 new for V2): 145 pass, 1 strict xfail (note 1), in about 4 s.

- `tests/fixtures/viz/round_trip_manager_32813_33993.jsonl` and `round_trip_builder_32813_33993.jsonl`: the two slices, sanitized (home paths to `/home/user`, user name and email replaced). The sanitized files produce the same snapshot as the raw slices. These are the V2 acceptance fixtures; V6 does not need to re-extract them.
- `tests/unit/test_state_model.py`: fixture round trip in both orders, snapshot equality, change stream shape, deep copies, socket and name resolution, every stage transition, inbox arithmetic with `remove`, enqueue before and after the sender's file, receiver-first merge, delivery without `msg_id`, idle notice by name and by PID, turn boundaries, unhandled entry types, `PID=PATH` parsing.
- `tests/integration/test_state_cli.py`: `state` and `state --events` as a subprocess with an empty registry, plus the bad-argument exit code.

## Notes, not failures

1. Code defect, for the builder in V3: the first `agent-name` entry for a session that was not in the registry sets the name without emitting a change. `learn_name` fills the empty name before `apply_agent_name` compares it, so the comparison sees no change. Repro: `StateModel().apply(1, {"type": "agent-name", "agentName": "a"})` returns `[]` while `sessions[1]["name"]` is `"a"`. V3 would never stream that name. Pinned by a strict xfail in `test_state_model.py`; it flips to a failure once fixed, then remove the marker.
2. Behaviour to know: `success: true` without a `msg_id` (an in-process subagent or teammate send) is marked FAILED with the result text as reason. Out of SPEC scope (cross-session only) but it will show as a red connector if a session in the root uses SendMessage to a subagent.
3. With no registry entry, a send to a name watches by name until an idle notice quoting that name arrives; `watching` then holds a string, not a PID. Documented in ready.md, pinned in the integration test.
4. User item (docs/): `docs/plan-visualization.md` §5 decrements inbox on both `dequeue` and the peer `user` entry; the observed order is enqueue, dequeue or remove, then delivery, so the model decrements only on dequeue and remove. The builder's request is correct.
5. User item (docs/): `docs/cross-session-message-format.md` §3.1 needs `remove` with `reason: absorbed_mid_turn` and inbox = enqueues minus dequeues minus removes, per the manager's decision.
