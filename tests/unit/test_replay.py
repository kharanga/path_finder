import json

import pytest

from conftest import FIXTURES_DIR

MANAGER = str(FIXTURES_DIR / "viz" / "round_trip_manager_32813_33993.jsonl")
BUILDER = str(FIXTURES_DIR / "viz" / "round_trip_builder_32813_33993.jsonl")


def write_lines(path, entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


def test_entries_in_time_order_interleaves_files_and_carries_untimestamped_lines(watcher, tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    write_lines(a, [{"type": "agent-name", "agentName": "a"}, {"type": "assistant", "timestamp": "2026-10-08T00:00:02.000Z"}, {"type": "agent-name", "agentName": "a2"}, {"type": "system", "timestamp": "2026-10-08T00:00:04.000Z"}])
    write_lines(b, [{"type": "user", "timestamp": "2026-10-08T00:00:01.000Z"}, {"type": "user", "timestamp": "2026-10-08T00:00:03.000Z"}])
    ordered = watcher.entries_in_time_order([(1, str(a)), (2, str(b))])
    assert [(t, pid, json.loads(line)["type"]) for t, _i, pid, line in ordered] == [
        ("", 1, "agent-name"),
        ("2026-10-08T00:00:01.000Z", 2, "user"),
        ("2026-10-08T00:00:02.000Z", 1, "assistant"),
        ("2026-10-08T00:00:02.000Z", 1, "agent-name"),
        ("2026-10-08T00:00:03.000Z", 2, "user"),
        ("2026-10-08T00:00:04.000Z", 1, "system"),
    ]


def test_entries_in_time_order_keeps_malformed_lines_and_skips_blank_ones(watcher, tmp_path):
    a = tmp_path / "a.jsonl"
    a.write_text('{"type":"user","timestamp":"2026-10-08T00:00:01.000Z"}\n\n{broken\n')
    ordered = watcher.entries_in_time_order([(1, str(a))])
    assert [line for _t, _i, _p, line in ordered] == [b'{"type":"user","timestamp":"2026-10-08T00:00:01.000Z"}', b"{broken"]
    assert ordered[1][0] == "2026-10-08T00:00:01.000Z"


def test_fixture_order_matches_the_doc_timeline(watcher):
    ordered = watcher.entries_in_time_order([(32813, MANAGER), (33993, BUILDER)])
    timestamps = [t for t, _i, _p, _l in ordered if t]
    assert timestamps == sorted(timestamps)
    assert len(ordered) == 45
    assert [pid for _t, _i, pid, _l in ordered[:2]] == [32813, 32813]


def test_replay_speed_zero_writes_everything_in_order(watcher, tmp_path):
    out = tmp_path / "out"
    args = watcher.build_parser().parse_args(["replay", "--fixture", f"32813={MANAGER}", "--fixture", f"33993={BUILDER}", "--out-dir", str(out), "--speed", "0"])
    assert watcher.command_replay(args) == 0
    manager_lines = (out / "32813.jsonl").read_bytes().split(b"\n")[:-1]
    builder_lines = (out / "33993.jsonl").read_bytes().split(b"\n")[:-1]
    assert len(manager_lines) == 29 and len(builder_lines) == 16
    assert set(manager_lines) == set(open(MANAGER, "rb").read().split(b"\n")[:-1])


def test_replay_until_freezes_a_frame_and_truncates_existing_output(watcher, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "32813.jsonl").write_text("stale\n")
    args = watcher.build_parser().parse_args(["replay", "--fixture", f"32813={MANAGER}", "--fixture", f"33993={BUILDER}", "--out-dir", str(out), "--speed", "0", "--until", "2026-10-08T04:31:11.000Z"])
    watcher.command_replay(args)
    manager = [json.loads(l) for l in (out / "32813.jsonl").read_text().splitlines()]
    builder = [json.loads(l) for l in (out / "33993.jsonl").read_text().splitlines()]
    assert all(not e.get("timestamp") or e["timestamp"] <= "2026-10-08T04:31:11.000Z" for e in manager + builder)
    assert any(e["type"] == "assistant" for e in manager)
    assert [e.get("operation") for e in builder if e["type"] == "queue-operation"] == ["enqueue"]
    assert "stale" not in (out / "32813.jsonl").read_text()


def test_replay_sleeps_scaled_and_capped(watcher, tmp_path, monkeypatch):
    a = tmp_path / "a.jsonl"
    write_lines(a, [{"type": "user", "timestamp": "2026-10-08T00:00:00.000Z"}, {"type": "user", "timestamp": "2026-10-08T00:00:01.000Z"}, {"type": "user", "timestamp": "2026-10-08T00:00:11.000Z"}])
    sleeps = []
    monkeypatch.setattr(watcher.time, "sleep", sleeps.append)
    args = watcher.build_parser().parse_args(["replay", "--fixture", f"1={a}", "--out-dir", str(tmp_path / "out"), "--speed", "2", "--max-gap", "3"])
    watcher.command_replay(args)
    assert sleeps == [0.5, 3.0]


def test_replay_parser_defaults_and_required_arguments(watcher):
    args = watcher.build_parser().parse_args(["replay", "--fixture", "1=/a", "--out-dir", "/o"])
    assert (args.speed, args.max_gap, args.until) == (1.0, 2.0, None)
    with pytest.raises(SystemExit):
        watcher.build_parser().parse_args(["replay", "--out-dir", "/o"])
    with pytest.raises(SystemExit):
        watcher.build_parser().parse_args(["replay", "--fixture", "1=/a"])
