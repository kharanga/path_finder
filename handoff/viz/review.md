# Review: V1 2026-10-08

PASS

## Checked against SPEC.md V1

- Tail by byte offset: `TranscriptTailer.poll()` reads only bytes past the stored offset, advances by what it read, and returns nothing on a second poll with no change.
- Complete lines only: a line appended in pieces stays in `partial_line` (offset still advances) and parses once the newline lands. Verified with two-piece and three-piece splits.
- Unknown types skipped without error: recorded once in `unknown_types`, dropped, no exception. A missing `type` lands as `None`.
- `isMeta` rule: kept for `turnOrigin` `peer` and `system`, dropped for `human` and for absent `turnOrigin`. Matches `docs/cross-session-message-format.md` §0 rule 1 and the census of both fake transcripts (30 peer, 2 system, 2 absent).
- Real transcript: `tail <fake manager transcript> --stats` prints 440 lines; stats are `offset 910321, buffered 0, unknown [atis-latch, file-history-snapshot], malformed 0, skipped 110`, exactly as ready.md states.
- The fixture script in ready.md reproduces all seven expected lines.
- `--follow` prints an appended peer entry well within 1 s (integration test, 250 ms poll).
- A file that shrinks resets offset and buffer. `--from-end` starts at the current size and prints nothing for existing content.
- Malformed JSON and non-object JSON (list, string, number) are counted in `malformed_lines` and skipped.
- `map --json` now exits 1 on an empty match, matching text mode. The pinned test is updated to 1 per the builder's request.
- Nothing under `~/.claude` or `discovery/` is written. Only `viz/watcher.py` changed.

## Tests

`python3 -m pytest tests` runs 106 tests (25 new for V1), all passing, in about 3.5 s.

- `tests/unit/test_tailer.py`: empty and missing files, offset advance, partial lines over two and three polls, many lines per chunk, unknown and untyped entries, malformed and non-object lines, blank lines, every `isMeta`/`turnOrigin` combination, sidechain, every attachment kind kept and two dropped, all eleven kept types, the three `queue-operation` values, rewrite detection, `--from-end`, `command_tail` output and stats.
- `tests/integration/test_tail_follow.py`: `tail --follow --from-end` as a subprocess, append one peer entry, expect it on stdout within 1 s.

## Notes, not failures

1. User item (docs/): `docs/jsonl-transcript-spec.md` §4.11 lists `progress` under INCLUDE and §7 derives WORKING from it. The tailer drops it, which is consistent with `docs/plan-visualization.md` §5 (status from `assistant` and `turn_duration`). No `progress` entry exists in any transcript on this machine. The jsonl spec should say `progress` is not used by the visualizer.
2. User item (docs/): `queue-operation` has a third `operation` value, `remove`, in 22 entries across the two fake transcripts (54 enqueue, 32 dequeue, 22 remove). `docs/cross-session-message-format.md` §3.1 lists only two. V2's inbox count depends on how `remove` is treated; the manager should decide before V2 is reviewed.
3. User item (docs/): `docs/jsonl-transcript-spec.md` §2 item 7 still says skip every `isMeta` entry. The message-format doc §0 overrides it. Builder's request stands.
4. User item: both fake transcripts hold 82 `hook_non_blocking_error` attachments from `dashboard-hook.js` style plugin hooks (`run-node.sh … webhook/hook`). Per CLAUDE.md the plugin is still installed and agents do not fix it.
5. Minor: a file rewritten to exactly its previous size is not detected as rewritten. Not a case the visualizer meets (transcripts are append-only).
