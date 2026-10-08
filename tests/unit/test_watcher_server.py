import json
import queue
import re

import pytest

from conftest import FIXTURES_DIR

MANAGER_FIXTURE = FIXTURES_DIR / "viz" / "round_trip_manager_32813_33993.jsonl"
BUILDER_FIXTURE = FIXTURES_DIR / "viz" / "round_trip_builder_32813_33993.jsonl"


def test_now_iso_is_utc_with_milliseconds(watcher):
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", watcher.now_iso())


def test_broadcaster_delivers_to_every_subscriber_until_unsubscribed(watcher):
    broadcaster = watcher.EventBroadcaster()
    first, second = broadcaster.subscribe(), broadcaster.subscribe()
    broadcaster.publish({"event": "x"})
    assert first.get_nowait() == {"event": "x"}
    assert second.get_nowait() == {"event": "x"}
    broadcaster.unsubscribe(first)
    broadcaster.publish({"event": "y"})
    assert second.get_nowait() == {"event": "y"}
    with pytest.raises(queue.Empty):
        first.get_nowait()
    broadcaster.unsubscribe(first)


def test_broadcaster_publish_without_subscribers_is_a_noop(watcher):
    watcher.EventBroadcaster().publish({"event": "x"})


def drain(subscriber):
    items = []
    while True:
        try:
            items.append(subscriber.get_nowait())
        except queue.Empty:
            return items


def copy_fixtures(tmp_path):
    manager = tmp_path / "m.jsonl"
    builder = tmp_path / "b.jsonl"
    manager.write_text(MANAGER_FIXTURE.read_text())
    builder.write_text(BUILDER_FIXTURE.read_text())
    return manager, builder


def test_fixture_watcher_first_poll_registers_sessions_and_replays_history(watcher, tmp_path):
    manager, builder = copy_fixtures(tmp_path)
    w = watcher.Watcher(fixtures=[(32813, str(manager)), (33993, str(builder))])
    subscriber = w.broadcaster.subscribe()
    w.poll_once()
    events = drain(subscriber)
    assert [e["event"] for e in events[:2]] == ["session", "session"]
    assert {e["pid"] for e in events[:2]} == {32813, 33993}
    assert events[0]["transcript"] == str(manager)
    assert len(events) == 2 + 24
    snapshot = w.snapshot()
    assert set(snapshot) == {"generated_at", "sessions", "messages"}
    assert [(m["kind"], m["stage"]) for m in snapshot["messages"]] == [("message", "READ"), ("message", "READ"), ("idle_notice", "READ")]
    assert w.poll_once() is None
    assert drain(subscriber) == []


def test_fixture_watcher_streams_appended_line_as_one_change(watcher, tmp_path):
    manager, builder = copy_fixtures(tmp_path)
    w = watcher.Watcher(fixtures=[(32813, str(manager)), (33993, str(builder))])
    w.poll_once()
    subscriber = w.broadcaster.subscribe()
    with open(builder, "a") as handle:
        handle.write(json.dumps({"type": "assistant", "timestamp": "2026-10-08T05:00:01.000Z", "message": {"content": [{"type": "text", "text": "hi"}]}}) + "\n")
    w.poll_once()
    events = drain(subscriber)
    assert [(e["event"], e["pid"], e["status"], e["at"]) for e in events] == [("session", 33993, "WORKING", "2026-10-08T05:00:01.000Z")]
    with open(builder, "a") as handle:
        handle.write(json.dumps({"type": "system", "subtype": "turn_duration", "timestamp": "2026-10-08T05:00:02.000Z"}) + "\n")
    w.poll_once()
    assert [e["status"] for e in drain(subscriber)] == ["IDLE"]


def test_fixture_watcher_takes_name_and_label_from_live_registry(watcher, tmp_path, monkeypatch):
    manager, builder = copy_fixtures(tmp_path)
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: pid == 32813)
    (watcher.SESSIONS_DIR / "32813.json").write_text(json.dumps({"pid": 32813, "name": "mgr-from-registry", "cwd": "/x", "sessionId": "sid"}))
    (watcher.IDENTITY_DIR / "32813.json").write_text(json.dumps({"role": "manager", "label": "the manager"}))
    w = watcher.Watcher(fixtures=[(32813, str(manager)), (33993, str(builder))])
    w.poll_once()
    sessions = {s["pid"]: s for s in w.snapshot()["sessions"]}
    assert (sessions[32813]["label"], sessions[32813]["role"], sessions[32813]["session_id"]) == ("the manager", "manager", "sid")
    assert sessions[33993]["label"] is None


def test_registry_watcher_adds_session_with_resolved_transcript(watcher, monkeypatch):
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: pid == 100)
    cwd = "/home/user/path_finder/fake_session"
    (watcher.SESSIONS_DIR / "100.json").write_text(json.dumps({"pid": 100, "name": "one", "cwd": cwd, "sessionId": "sid-100"}))
    folder = watcher.PROJECTS_DIR / watcher.encoded_cwd(cwd)
    folder.mkdir()
    (folder / "sid-100.jsonl").write_text(json.dumps({"type": "agent-name", "agentName": "one"}) + "\n")
    w = watcher.Watcher(root="/home/user/path_finder")
    subscriber = w.broadcaster.subscribe()
    w.poll_once()
    first = drain(subscriber)
    assert [e["event"] for e in first] == ["session"]
    assert (first[0]["pid"], first[0]["name"], first[0]["transcript"]) == (100, "one", str(folder / "sid-100.jsonl"))
    w.poll_once()
    assert drain(subscriber) == []


def test_registry_watcher_publishes_session_removed(watcher, monkeypatch):
    alive = {100}
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: pid in alive)
    cwd = "/home/user/path_finder"
    (watcher.SESSIONS_DIR / "100.json").write_text(json.dumps({"pid": 100, "name": "one", "cwd": cwd, "sessionId": "sid-100"}))
    folder = watcher.PROJECTS_DIR / watcher.encoded_cwd(cwd)
    folder.mkdir()
    (folder / "sid-100.jsonl").write_text("")
    w = watcher.Watcher(root=cwd)
    w.poll_once()
    subscriber = w.broadcaster.subscribe()
    alive.clear()
    w.poll_once()
    events = drain(subscriber)
    assert [(e["event"], e["pid"]) for e in events] == [("session_removed", 100)]
    assert re.fullmatch(r".*Z", events[0]["at"])


def test_registry_watcher_skips_session_without_transcript_and_outside_root(watcher, monkeypatch):
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: True)
    (watcher.SESSIONS_DIR / "1.json").write_text(json.dumps({"pid": 1, "name": "no-transcript", "cwd": "/home/user/path_finder", "sessionId": "missing"}))
    (watcher.SESSIONS_DIR / "2.json").write_text(json.dumps({"pid": 2, "name": "outside", "cwd": "/elsewhere", "sessionId": "sid-2"}))
    w = watcher.Watcher(root="/home/user/path_finder")
    w.poll_once()
    assert w.snapshot()["sessions"] == []


def test_registry_watcher_republishes_when_identity_changes(watcher, monkeypatch):
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: True)
    cwd = "/home/user/path_finder"
    (watcher.SESSIONS_DIR / "1.json").write_text(json.dumps({"pid": 1, "name": "one", "cwd": cwd, "sessionId": "sid-1"}))
    folder = watcher.PROJECTS_DIR / watcher.encoded_cwd(cwd)
    folder.mkdir()
    (folder / "sid-1.jsonl").write_text("")
    w = watcher.Watcher(root=cwd)
    w.poll_once()
    subscriber = w.broadcaster.subscribe()
    (watcher.IDENTITY_DIR / "1.json").write_text(json.dumps({"role": "validator", "label": "validator"}))
    w.poll_once()
    events = drain(subscriber)
    assert [(e["event"], e["label"]) for e in events] == [("session", "validator")]


def test_snapshot_is_a_copy(watcher, tmp_path):
    manager, builder = copy_fixtures(tmp_path)
    w = watcher.Watcher(fixtures=[(32813, str(manager)), (33993, str(builder))])
    w.poll_once()
    snapshot = w.snapshot()
    snapshot["sessions"][0]["status"] = "MUTATED"
    assert w.model.sessions[32813]["status"] == "IDLE"


def test_serve_parser_defaults(watcher):
    args = watcher.build_parser().parse_args(["serve"])
    assert (args.port, args.root, args.fixture, args.verbose) == (4780, None, None, False)
    args = watcher.build_parser().parse_args(["serve", "--port", "4799", "--fixture", "1=/a.jsonl", "--fixture", "2=/b.jsonl"])
    assert args.fixture == [(1, "/a.jsonl"), (2, "/b.jsonl")]
    assert watcher.SSE_KEEPALIVE_S == 15
    assert watcher.STATIC_DIRS == (watcher.VIZ_DIR, watcher.DISCOVERY_DIR)
