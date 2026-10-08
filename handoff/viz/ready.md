# Ready: V2 2026-10-08

## Done

`viz/watcher.py` gains `StateModel` and a `state` command.

State (plan §5): `sessions` keyed by PID with `status`, `inbox`, `last_text`, `watching`, plus registry and identity fields; `messages` keyed by `msg_id` with `stage` PENDING, IN_INBOX, READ, FAILED and the four timestamps `sent_at`, `accepted_at`, `enqueued_at`, `read_at`; `kind` is `message` or `idle_notice`. Socket to PID: the socket embeds the PID (`uds:/tmp/cc-socks/<pid>.sock`), so `pid_from_socket` parses it; names resolve through `pid_by_name`, filled from the registry, `agent-name` entries, `origin.name` on deliveries, and `from-name` on enqueues. A `name [ref]` target is stripped to the bare name.

Transitions, with the PID of the transcript being read as "this session":

- `assistant` entry: this session WORKING. Each `SendMessage` tool_use creates a PENDING message under key `pending:<tool_use id>`, `last_text` = summary; `notify_when_idle` adds the target PID to `watching`.
- `user` tool_result matching that tool_use: `success` true re-keys the message to `toolUseResult.msg_id`, stage IN_INBOX, `accepted_at`; false sets FAILED with `reason`. If the receiver's side already created the message under that `msg_id`, the two merge: sender-owned fields (summary, body, sent_at, notify flag, pending_key) come from the sender, stage stays READ.
- `queue-operation` enqueue: `inbox` +1; a peer-message enqueue stamps `enqueued_at` on the oldest unenqueued message from that sender to this session, or is held in `unmatched_enqueues` until the message appears. `dequeue` and `remove`: `inbox` −1, floored at 0.
- `user` with `origin.kind == peer`: message READ with `read_at`, created from `origin` when the sender's file has not been read yet; receiver `last_text` = `origin.body`, status WORKING.
- `user` with `turnOrigin == system` and the idle-notice prefix: one `idle_notice` message, stage READ, from the quoted session's PID to this session, key `idle:<entry uuid>`; the watched PID is removed from `watching`.
- `system` `turn_duration`: IDLE. `agent-name`: name update, emitted only when it changes.

Every `apply(pid, entry)` returns one deep-copied change per touched object: `{"event": "session" | "message", "at": <entry timestamp>, ...object}`. Messages carry `key` and `pending_key`; when they differ, the row under `pending_key` is superseded. This is the line format V3 streams on `/events`.

Decision taken on `remove` (validator V1 note 2): every `remove` in the fake transcripts carries `reason: absorbed_mid_turn`, and per session enqueues equal dequeues plus removes exactly (26 = 14 + 12, 28 = 18 + 10). A `remove` is a queued message consumed mid-turn, so it counts as inbox −1. The receiver-side informational entry "A process claiming the address … asked to be told when this session is next idle" is not used: the sender's `notify_when_idle` already sets `watching`, and reading the receiver's file after the notice would re-add a watch the notice had cleared.

`state PID=PATH [PID=PATH ...] [--events]` registers each PID from the live registry when present (bare session otherwise), feeds each file whole in the given order, and prints the snapshot or the change stream.

Files: `viz/watcher.py`. Nothing else touched.

## How to test

The captured fixtures are the 2026-10-08 round trip in the two fake-session transcripts (the timeline in `docs/cross-session-message-format.md` §1). Extract them:

```
python3 - <<'PY'
import json, os, tempfile
src = os.path.expanduser("~/.claude/projects/-Users-khangnguyen-Documents-path-finder-fake-session/")
out = tempfile.mkdtemp()
for sid, name in (("ab5e0a7a-abdf-48ae-b34a-85aebcb80f95", "manager"), ("67139bc5-30c6-43e1-aa4c-71415790bb63", "builder")):
    with open(f"{out}/{name}.jsonl", "w") as fh:
        for line in open(src + sid + ".jsonl"):
            e = json.loads(line)
            if e.get("type") == "agent-name" or "2026-10-08T04:31:00" <= e.get("timestamp", "") <= "2026-10-08T04:31:30":
                fh.write(line)
print(out)
PY
```

Expected: manager 29 lines, builder 16 lines. Then, with `F` set to that folder:

```
python3 viz/watcher.py state 32813=$F/manager.jsonl 33993=$F/builder.jsonl
```

Expected in `messages` (three entries):

| kind | stage | from → to | sent_at | accepted_at | enqueued_at | read_at |
| :- | :- | :- | :- | :- | :- | :- |
| message `693b9bd4-…` | READ | 32813 → 33993 | 04:31:10.318 | 04:31:11.281 | 04:31:10.817 | 04:31:11.097 |
| message `f5ac2c3a-…` | READ | 33993 → 32813 | 04:31:16.750 | 04:31:17.811 | 04:31:17.590 | 04:31:17.638 |
| idle_notice `idle:97bc…` | READ | 33993 → 32813 | 04:31:21.055 | null | null | 04:31:21.055 |

All timestamps on 2026-10-08. Expected in `sessions`: both IDLE, inbox 0, `watching` empty (32813 watched 33993 from 10.318 until the notice at 21.055), 32813 `last_text` starts "Hi again from fake-session-builder", 33993 `last_text` is "Second hi back to fake-session-manager".

Order independence: `state 33993=$F/builder.jsonl 32813=$F/manager.jsonl` gives the same snapshot apart from `last_seen_at` and message order.

Change stream: `... --events` prints 23 lines; the first is 32813 WORKING with `watching [33993]` at 10.318, and the 32813 line at 21.055 has `watching []`. Inbox goes 0, 1, 0 around each enqueue and dequeue.

## Requests

- `docs/cross-session-message-format.md` §3.1: add `remove` with `reason: absorbed_mid_turn`, `commandUuid`, `deliveryId`, and the wrapped content; it replaces `dequeue` when the message is consumed mid-turn. Inbox = enqueues − dequeues − removes.
- `docs/plan-visualization.md` §5 says inbox −1 both on `dequeue` and on the peer `user` entry. Observed sequence is enqueue, dequeue (or remove), then the peer entry, so decrementing on both would double count. The model decrements on dequeue and remove only.
- `tests/fixtures/`: the two slices above are the V2 fixtures; V6 commits them sanitized. If the validator wants them earlier, the extraction script is deterministic.

## Blocked

Nothing.
