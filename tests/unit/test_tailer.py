import json

import pytest


def line(**entry):
    return (json.dumps(entry) + "\n").encode()


@pytest.fixture
def transcript(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_bytes(b"")
    return path


def append(path, data):
    with open(path, "ab") as handle:
        handle.write(data)


def types_of(entries):
    return [e["type"] for e in entries]


def test_poll_on_empty_file_returns_nothing(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    assert tailer.poll() == []
    assert tailer.offset == 0


def test_poll_on_missing_file_returns_nothing_without_error(watcher, tmp_path):
    tailer = watcher.TranscriptTailer(tmp_path / "absent.jsonl")
    assert tailer.poll() == []
    tailer_from_end = watcher.TranscriptTailer(tmp_path / "absent.jsonl", start_at_end=True)
    assert tailer_from_end.offset == 0


def test_appended_complete_line_is_parsed_and_offset_advances(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    data = line(type="agent-name", agentName="a")
    append(transcript, data)
    entries = tailer.poll()
    assert entries == [{"type": "agent-name", "agentName": "a"}]
    assert tailer.offset == len(data)
    assert tailer.poll() == []


def test_partial_line_is_buffered_until_completed(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    full = line(type="assistant", message={"content": []})
    append(transcript, full[:20])
    assert tailer.poll() == []
    assert tailer.partial_line == full[:20]
    assert tailer.offset == 20
    append(transcript, full[20:])
    assert types_of(tailer.poll()) == ["assistant"]
    assert tailer.partial_line == b""


def test_partial_line_split_across_three_polls(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    full = line(type="system", subtype="turn_duration")
    pieces = [full[:5], full[5:12], full[12:]]
    polls = []
    for piece in pieces:
        append(transcript, piece)
        polls.append(tailer.poll())
    assert polls == [[], [], [{"type": "system", "subtype": "turn_duration"}]]


def test_several_lines_in_one_chunk(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    append(transcript, line(type="user", message={}) + line(type="assistant") + line(type="summary", summary="s"))
    assert types_of(tailer.poll()) == ["user", "assistant", "summary"]


def test_unknown_type_is_skipped_once_recorded(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    append(transcript, line(type="marble-origami-commit") + line(type="marble-origami-commit") + line(type="atis-latch"))
    assert tailer.poll() == []
    assert tailer.unknown_types == {"marble-origami-commit", "atis-latch"}
    assert tailer.skipped_entries == 0


def test_entry_without_type_is_recorded_as_unknown(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    append(transcript, line(uuid="x"))
    assert tailer.poll() == []
    assert tailer.unknown_types == {None}


@pytest.mark.parametrize("raw", [b"{broken\n", b"[1, 2]\n", b"\"string\"\n", b"42\n"])
def test_malformed_or_non_object_lines_are_counted_and_skipped(watcher, transcript, raw):
    tailer = watcher.TranscriptTailer(transcript)
    append(transcript, raw + line(type="agent-name", agentName="after"))
    assert types_of(tailer.poll()) == ["agent-name"]
    assert tailer.malformed_lines == 1


def test_blank_lines_are_ignored(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    append(transcript, b"\n\n" + line(type="mode", mode="normal") + b"   \n")
    assert types_of(tailer.poll()) == ["mode"]
    assert tailer.malformed_lines == 0


def test_meta_entries_kept_only_for_peer_and_system_origin(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    append(
        transcript,
        line(type="user", isMeta=True, turnOrigin="peer")
        + line(type="user", isMeta=True, turnOrigin="system")
        + line(type="user", isMeta=True, turnOrigin="human")
        + line(type="user", isMeta=True)
        + line(type="user", isMeta=False, turnOrigin="human"),
    )
    kept = tailer.poll()
    assert [e.get("turnOrigin") for e in kept] == ["peer", "system", "human"]
    assert tailer.skipped_entries == 2


def test_sidechain_entries_are_skipped(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    append(transcript, line(type="assistant", isSidechain=True) + line(type="assistant", isSidechain=False))
    assert len(tailer.poll()) == 1
    assert tailer.skipped_entries == 1


def test_attachments_kept_only_for_queued_command_and_hooks(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    kinds = ["queued_command", "hook_success", "hook_non_blocking_error", "hook_blocking_error", "hook_cancelled", "total_tokens_reminder", "batching_reminder_sent"]
    data = b"".join(line(type="attachment", attachment={"type": kind}) for kind in kinds)
    data += line(type="attachment", attachment="not a dict") + line(type="attachment")
    append(transcript, data)
    kept = tailer.poll()
    assert [e["attachment"]["type"] for e in kept] == kinds[:5]
    assert tailer.skipped_entries == 4


def test_every_documented_kept_type_passes(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    types = ["assistant", "user", "system", "queue-operation", "agent-name", "custom-title", "ai-title", "permission-mode", "mode", "last-prompt", "summary"]
    append(transcript, b"".join(line(type=t) for t in types))
    assert types_of(tailer.poll()) == types


def test_queue_operation_values_including_remove_pass_through(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    append(transcript, b"".join(line(type="queue-operation", operation=op) for op in ("enqueue", "dequeue", "remove")))
    assert [e["operation"] for e in tailer.poll()] == ["enqueue", "dequeue", "remove"]


def test_rewritten_shorter_file_resets_offset_and_buffer(watcher, transcript):
    tailer = watcher.TranscriptTailer(transcript)
    append(transcript, line(type="assistant") * 3 + b'{"partial')
    tailer.poll()
    assert tailer.partial_line == b'{"partial'
    transcript.write_bytes(line(type="system", subtype="turn_duration"))
    assert types_of(tailer.poll()) == ["system"]
    assert tailer.partial_line == b""
    assert tailer.offset == len(line(type="system", subtype="turn_duration"))


def test_start_at_end_skips_existing_content(watcher, transcript):
    append(transcript, line(type="assistant") * 5)
    tailer = watcher.TranscriptTailer(transcript, start_at_end=True)
    assert tailer.poll() == []
    append(transcript, line(type="summary", summary="new"))
    assert types_of(tailer.poll()) == ["summary"]


def test_entry_is_kept_rejects_non_dicts(watcher):
    assert watcher.entry_is_kept(None) is False
    assert watcher.entry_is_kept([]) is False
    assert watcher.entry_is_kept({"type": "user"}) is True


def test_command_tail_prints_kept_entries_and_stats(watcher, transcript, capsys):
    append(transcript, line(type="agent-name", agentName="a") + line(type="atis-latch") + b"{bad\n" + line(type="user", isMeta=True))
    args = watcher.build_parser().parse_args(["tail", str(transcript), "--stats"])
    assert watcher.command_tail(args) == 0
    captured = capsys.readouterr()
    assert [json.loads(l)["type"] for l in captured.out.splitlines()] == ["agent-name"]
    stats = json.loads(captured.err)
    assert stats == {"offset": transcript.stat().st_size, "buffered_bytes": 0, "unknown_types": ["atis-latch"], "malformed_lines": 1, "skipped_entries": 1}


def test_command_tail_from_end_prints_nothing_for_existing_content(watcher, transcript, capsys):
    append(transcript, line(type="assistant") * 2)
    args = watcher.build_parser().parse_args(["tail", str(transcript), "--from-end"])
    assert watcher.command_tail(args) == 0
    assert capsys.readouterr().out == ""


def test_tail_parser_defaults(watcher):
    args = watcher.build_parser().parse_args(["tail", "x.jsonl"])
    assert (args.follow, args.from_end, args.stats) == (False, False, False)
    assert watcher.POLL_INTERVAL_S == 0.25
