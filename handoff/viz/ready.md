# Ready: V1 2026-10-08

## Done

`viz/watcher.py` gains `TranscriptTailer` and a `tail` command.

- `TranscriptTailer(path, start_at_end=False)`: keeps a byte offset and a partial-line buffer per file. `poll()` reads only the new bytes, splits on newline, buffers the trailing fragment, parses each complete line, and returns the kept entries as dicts. A file that shrinks below the stored offset is treated as rewritten: offset and buffer reset to zero.
- Filter, in order: a type outside `KEPT_ENTRY_TYPES` is recorded once in `unknown_types` and dropped; `isSidechain` dropped; `isMeta` dropped unless `turnOrigin` is `peer` or `system`; `attachment` kept only for `queued_command` and the four `hook_*` kinds. Malformed JSON is counted in `malformed_lines` and dropped. Nothing raises.
- Kept types: `assistant`, `user`, `system`, `queue-operation`, `attachment`, `agent-name`, `custom-title`, `ai-title`, `permission-mode`, `mode`, `last-prompt`, `summary`. These are everything the V2 state model and the capsule labels read.
- `tail <transcript> [--follow] [--from-end] [--stats]`: prints one JSON line per kept entry. `--follow` polls every 250 ms. `--stats` prints offset, buffered bytes, unknown types, malformed and skipped counts to stderr at exit.
- `map` exit code aligned: text and JSON modes both exit 1 when no session matches the root or one is unmapped. This changes the behaviour pinned by `test_command_map_empty_exit_code_differs_between_text_and_json`; that test now fails by design and needs its JSON assertion changed to 1.

Files: `viz/watcher.py`. Nothing else touched.

## How to test

Real transcript, whole file:

```
python3 viz/watcher.py tail ~/.claude/projects/-Users-khangnguyen-Documents-path-finder-fake-session/ab5e0a7a-abdf-48ae-b34a-85aebcb80f95.jsonl --stats | wc -l
```

Expected: 440 lines on stdout; stderr `{"offset": 910321, "buffered_bytes": 0, "unknown_types": ["atis-latch", "file-history-snapshot"], "malformed_lines": 0, "skipped_entries": 110}` (offset grows if the fake session runs again).

Fixture, appended line by line (run from the repo root; uses a temp file):

```
python3 - <<'PY'
import sys, json, tempfile, os
sys.path.insert(0, "viz")
import watcher
path = os.path.join(tempfile.mkdtemp(), "t.jsonl")
open(path, "w").close()
t = watcher.TranscriptTailer(path)
def add(s): open(path, "a").write(s)
def show(label):
    got = t.poll()
    print(label, [e["type"] for e in got], "buffered", len(t.partial_line), "unknown", sorted(t.unknown_types), "malformed", t.malformed_lines, "skipped", t.skipped_entries)
add(json.dumps({"type": "agent-name", "agentName": "a"}) + "\n"); show("complete")
half = json.dumps({"type": "assistant", "message": {}}); add(half[:20]); show("partial")
add(half[20:] + "\n"); show("completed")
add(json.dumps({"type": "marble-origami-commit"}) + "\n"); show("unknown")
add("{broken\n"); show("malformed")
add(json.dumps({"type": "user", "isMeta": True, "turnOrigin": "peer"}) + "\n" + json.dumps({"type": "user", "isMeta": True}) + "\n"); show("meta rule")
open(path, "w").write(json.dumps({"type": "system", "subtype": "turn_duration"}) + "\n"); show("rewritten")
PY
```

Expected:

```
complete ['agent-name'] buffered 0 unknown [] malformed 0 skipped 0
partial [] buffered 20 unknown [] malformed 0 skipped 0
completed ['assistant'] buffered 0 unknown [] malformed 0 skipped 0
unknown [] buffered 0 unknown ['marble-origami-commit'] malformed 0 skipped 0
malformed [] buffered 0 unknown ['marble-origami-commit'] malformed 1 skipped 0
meta rule ['user'] buffered 0 unknown ['marble-origami-commit'] malformed 1 skipped 1
rewritten ['system'] buffered 0 unknown ['marble-origami-commit'] malformed 1 skipped 1
```

Live follow: `python3 viz/watcher.py tail <transcript> --follow --from-end` in one terminal, then send any message to that session; the enqueue and peer `user` entries print within a poll.

## Requests

- `tests/unit/test_watcher.py`: change the JSON assertion in `test_command_map_empty_exit_code_differs_between_text_and_json` to `== 1` (validator note 3 from the V0 review, now aligned).
- `docs/cross-session-message-format.md` §3.1: `queue-operation` has a third `operation` value, `remove`, seen 22 times across the two fake transcripts (54 enqueue, 32 dequeue, 22 remove). It is not handled yet; V2 will treat it as inbox minus one unless the manager says otherwise.
- `docs/jsonl-transcript-spec.md` §2 item 7 still says to skip every `isMeta` entry; the message-format doc already overrides it, but a one-line pointer there would stop the next reader from following the wrong rule.
- For the user: both fake transcripts hold 82 `hook_non_blocking_error` attachments from a plugin hook (`${CLAUDE_PLUGIN_ROOT}/hooks/run-node.sh … webhook/hook`, on `UserPromptSubmit`, `PostToolUse:SendMessage`, and `Stop`). CLAUDE.md says a leftover hook error means the plugin is still installed and that agents must not fix it. Only noting it.

## Blocked

Nothing.
