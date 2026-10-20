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
    w = watcher.Watcher(spec_path=None, fixtures=[(32813, str(manager)), (33993, str(builder))])
    subscriber = w.broadcaster.subscribe()
    w.poll_once()
    events = drain(subscriber)
    assert [e["event"] for e in events[:2]] == ["session", "session"]
    assert {e["pid"] for e in events[:2]} == {32813, 33993}
    assert events[0]["transcript"] == str(manager)
    assert len(events) == 2 + 31
    snapshot = w.snapshot()
    assert set(snapshot) == {"generated_at", "sessions", "messages", "sources", "tasks", "task_counts", "spec_path"}
    assert [(e["source"], e["source_pid"]) for e in events[:2]] == [("registry", 32813), ("registry", 33993)]
    assert all(e["source"] and e["source_pid"] in (32813, 33993) for e in events[2:])
    assert [s["pid"] for s in snapshot["sources"]] == [32813, 33993]
    assert [(m["kind"], m["stage"]) for m in snapshot["messages"]] == [("message", "READ"), ("message", "READ"), ("idle_notice", "READ")]
    assert w.poll_once() is None
    assert drain(subscriber) == []


def test_fixture_watcher_streams_appended_line_as_one_change(watcher, tmp_path):
    manager, builder = copy_fixtures(tmp_path)
    w = watcher.Watcher(spec_path=None, fixtures=[(32813, str(manager)), (33993, str(builder))])
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
    w = watcher.Watcher(spec_path=None, fixtures=[(32813, str(manager)), (33993, str(builder))])
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
    w = watcher.Watcher(spec_path=None, root="/home/user/path_finder")
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
    w = watcher.Watcher(spec_path=None, root=cwd)
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
    w = watcher.Watcher(spec_path=None, root="/home/user/path_finder")
    w.poll_once()
    assert w.snapshot()["sessions"] == []


def test_registry_watcher_republishes_when_identity_changes(watcher, monkeypatch):
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: True)
    cwd = "/home/user/path_finder"
    (watcher.SESSIONS_DIR / "1.json").write_text(json.dumps({"pid": 1, "name": "one", "cwd": cwd, "sessionId": "sid-1"}))
    folder = watcher.PROJECTS_DIR / watcher.encoded_cwd(cwd)
    folder.mkdir()
    (folder / "sid-1.jsonl").write_text("")
    w = watcher.Watcher(spec_path=None, root=cwd)
    w.poll_once()
    subscriber = w.broadcaster.subscribe()
    (watcher.IDENTITY_DIR / "1.json").write_text(json.dumps({"role": "validator", "label": "validator"}))
    w.poll_once()
    events = drain(subscriber)
    assert [(e["event"], e["label"]) for e in events] == [("session", "validator")]


def test_snapshot_is_a_copy(watcher, tmp_path):
    manager, builder = copy_fixtures(tmp_path)
    w = watcher.Watcher(spec_path=None, fixtures=[(32813, str(manager)), (33993, str(builder))])
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
    assert watcher.STATIC_DIRS == (watcher.VIZ_DIR,)
    assert watcher.PAGE_ROUTES == {"/web": "/web.html"}


def test_emit_writes_one_json_line_per_change_and_publishes(watcher, tmp_path):
    log_path = tmp_path / "logs" / "events.jsonl"
    w = watcher.Watcher(spec_path=None, fixtures=[], log_path=str(log_path))
    subscriber = w.broadcaster.subscribe()
    assert not log_path.exists()
    w.emit({"event": "session", "at": "t1", "pid": 1})
    w.emit({"event": "session_removed", "at": "t2", "pid": 1})
    assert [json.loads(l) for l in log_path.read_text().splitlines()] == [{"event": "session", "at": "t1", "pid": 1}, {"event": "session_removed", "at": "t2", "pid": 1}]
    assert [e["event"] for e in drain(subscriber)] == ["session", "session_removed"]
    w.close()
    assert w.log_handle is None and w.stop_event.is_set()


def test_emit_without_log_path_only_publishes(watcher, tmp_path):
    w = watcher.Watcher(spec_path=None, fixtures=[])
    subscriber = w.broadcaster.subscribe()
    w.emit({"event": "session", "at": "t", "pid": 1})
    assert len(drain(subscriber)) == 1
    assert list(tmp_path.rglob("*.jsonl")) == []
    assert w.log_path is None and w.log_handle is None


def test_log_matches_the_stream_for_the_fixture_round_trip(watcher, tmp_path):
    manager, builder = copy_fixtures(tmp_path)
    log_path = tmp_path / "events.jsonl"
    w = watcher.Watcher(spec_path=None, fixtures=[(32813, str(manager)), (33993, str(builder))], log_path=str(log_path))
    subscriber = w.broadcaster.subscribe()
    w.poll_once()
    streamed = drain(subscriber)
    logged = [json.loads(l) for l in log_path.read_text().splitlines()]
    assert logged == streamed
    assert len(logged) == 2 + 31
    w.poll_once()
    assert len(log_path.read_text().splitlines()) == 33
    w.close()
    w2 = watcher.Watcher(spec_path=None, fixtures=[(32813, str(manager)), (33993, str(builder))], log_path=str(log_path))
    w2.poll_once()
    w2.close()
    assert len(log_path.read_text().splitlines()) == 66


def test_serve_parser_log_defaults(watcher):
    args = watcher.build_parser().parse_args(["serve"])
    assert (args.log, args.no_log) == (str(watcher.EVENT_LOG_PATH), False)
    assert watcher.EVENT_LOG_PATH == watcher.VIZ_DIR / "events.jsonl"
    args = watcher.build_parser().parse_args(["serve", "--no-log", "--log", "/x.jsonl"])
    assert (args.log, args.no_log) == ("/x.jsonl", True)


def truncate_fixture(source, target, until):
    kept = []
    for line in source.read_text().splitlines():
        timestamp = json.loads(line).get("timestamp")
        if timestamp and timestamp > until:
            break
        kept.append(line)
    target.write_text("\n".join(kept) + "\n")


def test_first_poll_newest_source_is_the_newest_transcript_entry_across_files(watcher, tmp_path):
    manager, builder = tmp_path / "m.jsonl", tmp_path / "b.jsonl"
    truncate_fixture(MANAGER_FIXTURE, manager, "2026-10-08T04:31:17.600Z")
    truncate_fixture(BUILDER_FIXTURE, builder, "2026-10-08T04:31:17.600Z")
    w = watcher.Watcher(spec_path=None, fixtures=[(32813, str(manager)), (33993, str(builder))])
    w.poll_once()
    sources = {s["pid"]: s for s in w.snapshot()["sources"]}
    assert (sources[32813]["source"], sources[32813]["at"]) == ("queue-operation · enqueue", "2026-10-08T04:31:17.590Z")
    assert (sources[33993]["source"], sources[33993]["at"]) == ("assistant → tool_use SendMessage", "2026-10-08T04:31:16.750Z")
    assert sources[32813]["seq"] > sources[33993]["seq"]


def test_registry_watcher_session_removed_carries_source_and_drops_its_source_row(watcher, monkeypatch):
    alive = {100, 101}
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: pid in alive)
    cwd = "/home/user/path_finder"
    folder = watcher.PROJECTS_DIR / watcher.encoded_cwd(cwd)
    folder.mkdir()
    for pid in (100, 101):
        (watcher.SESSIONS_DIR / f"{pid}.json").write_text(json.dumps({"pid": pid, "name": f"s{pid}", "cwd": cwd, "sessionId": f"sid-{pid}"}))
        (folder / f"sid-{pid}.jsonl").write_text("")
    w = watcher.Watcher(spec_path=None, root=cwd)
    subscriber = w.broadcaster.subscribe()
    w.poll_once()
    first = drain(subscriber)
    assert [(e["event"], e["source"], e["source_pid"]) for e in first] == [("session", "registry", 100), ("session", "registry", 101)]
    assert [(s["pid"], s["source"], s["seq"]) for s in w.snapshot()["sources"]] == [(100, "registry", 1), (101, "registry", 2)]
    alive.discard(101)
    w.poll_once()
    removed = drain(subscriber)
    assert [(e["event"], e["pid"], e["source"], e["source_pid"]) for e in removed] == [("session_removed", 101, "registry", 101)]
    assert [s["pid"] for s in w.snapshot()["sources"]] == [100]


def test_first_poll_applies_both_files_in_timestamp_order(watcher, tmp_path):
    manager, builder = copy_fixtures(tmp_path)
    w = watcher.Watcher(spec_path=None, fixtures=[(32813, str(manager)), (33993, str(builder))])
    subscriber = w.broadcaster.subscribe()
    w.poll_once()
    streamed = [(e["event"], e["source_pid"], e["source"], e["at"]) for e in drain(subscriber)[2:] if e["source"] != "agent-name"]
    model = watcher.StateModel()
    model.register_session({"pid": 32813, "name": "fake-session-manager"})
    model.register_session({"pid": 33993, "name": "fake-session-builder"})
    tailer = watcher.TranscriptTailer(str(manager))
    expected = []
    for _timestamp, _index, pid, line in watcher.entries_in_time_order([(32813, str(manager)), (33993, str(builder))]):
        entry = tailer.parse_line(line)
        if entry is not None:
            expected += [(c["event"], c["source_pid"], c["source"], c["at"]) for c in model.apply(pid, entry) if c["source"] != "agent-name"]
    assert streamed == expected
    assert [at for _e, _p, _s, at in streamed] == sorted(at for _e, _p, _s, at in streamed)
    assert [s["source"] for s in w.snapshot()["sources"]] == ["system · turn_duration", "system · turn_duration"]


def write_lines(path, entries):
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))


def test_timestamp_less_lines_inherit_the_previous_timestamp_in_their_file_across_polls(watcher, tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    write_lines(a, [{"type": "user", "turnOrigin": "human", "timestamp": "2026-10-08T04:31:12.000Z", "message": {"content": "go"}}, {"type": "agent-name", "agentName": "a-renamed"}])
    write_lines(b, [{"type": "user", "turnOrigin": "human", "timestamp": "2026-10-08T04:31:11.000Z", "message": {"content": "go"}}])
    w = watcher.Watcher(spec_path=None, fixtures=[(1, str(a)), (2, str(b))])
    subscriber = w.broadcaster.subscribe()
    w.poll_once()
    first = [(e["source_pid"], e["source"]) for e in drain(subscriber)[2:]]
    assert first == [(2, "user"), (1, "user"), (1, "agent-name")]
    with open(a, "a") as handle:
        handle.write(json.dumps({"type": "agent-name", "agentName": "a-again"}) + "\n")
    with open(b, "a") as handle:
        handle.write(json.dumps({"type": "system", "subtype": "turn_duration", "timestamp": "2026-10-08T04:31:13.000Z"}) + "\n")
    w.poll_once()
    assert [(e["source_pid"], e["source"]) for e in drain(subscriber)] == [(1, "agent-name"), (2, "system · turn_duration")]


SPEC_TEXT = """# SPEC

## Decisions so far

- [ ] not a task, wrong section

## Tasks

The manager assigns every task by ID.

- [x] D1: role prompt in discovery (label equals role). When a round starts, each session asks.
- [x] V3: `GET /state` (full snapshot) and `GET /events` (SSE) on the port 4780 server. Done when `curl /state` returns.
- [~] V9: task panel. A side panel on `viz/web.html`.
- [ ] D4: retire `ui`. Remove `discover.py ui`. Done when it fails.
- [ ] X7: something else entirely
- [ ] V10: no period at all
- [?] V11: unknown mark is skipped
- [ ] bad line without an id
  - [ ] indented is skipped

## Open questions

- [ ] Z1: after the section
"""


def test_parse_spec_tasks_reads_only_the_tasks_section(watcher):
    tasks = watcher.parse_spec_tasks(SPEC_TEXT)
    assert [(t["id"], t["state"], t["owner"]) for t in tasks] == [("D1", "done", "discovery-builder"), ("V3", "done", "viz-builder"), ("V9", "in_progress", "viz-builder"), ("D4", "todo", "discovery-builder"), ("X7", "todo", None), ("V10", "todo", "viz-builder")]
    assert [t["title"] for t in tasks] == ["role prompt in discovery (label equals role)", "`GET /state` (full snapshot) and `GET /events` (SSE) on the port 4780 server", "task panel", "retire `ui`", "something else entirely", "no period at all"]
    assert tasks[2]["text"] == "task panel. A side panel on `viz/web.html`."
    assert tasks[3]["text"] == "retire `ui`. Remove `discover.py ui`. Done when it fails."


def test_parse_spec_tasks_without_a_section_or_text(watcher):
    assert watcher.parse_spec_tasks("") == []
    assert watcher.parse_spec_tasks("## Tasks\n") == []
    assert watcher.parse_spec_tasks("## Tasks\n- [x] V1: done.\n## Tasks\n- [ ] V2: again.\n") == [
        {"id": "V1", "state": "done", "title": "done", "text": "done.", "owner": "viz-builder", "area": "Visualization"}, {"id": "V2", "state": "todo", "title": "again", "text": "again.", "owner": "viz-builder", "area": "Visualization"}]


@pytest.mark.parametrize("task_id, area", [("D1", "Discovery"), ("d4", "Discovery"), ("V10", "Visualization"), ("X7", "X"), ("q2", "Q")])
def test_task_area_maps_the_series_letter(watcher, task_id, area):
    assert watcher.task_area(task_id) == area


def test_parse_spec_tasks_carries_the_area(watcher):
    assert [(t["id"], t["area"]) for t in watcher.parse_spec_tasks(SPEC_TEXT)] == [("D1", "Discovery"), ("V3", "Visualization"), ("V9", "Visualization"), ("D4", "Discovery"), ("X7", "X"), ("V10", "Visualization")]


@pytest.mark.parametrize("text, title", [
    ("retire `ui`. Remove things.", "retire `ui`"),
    ("uses discover.py ui then stops. Next", "uses discover.py ui then stops"),
    ("ends with a period.", "ends with a period"),
    ("no period", "no period"),
    ("  padded.   ", "padded"),
    ("v1.2 release. Then", "v1.2 release"),
])
def test_task_title_cuts_at_the_first_sentence_end(watcher, text, title):
    assert watcher.task_title(text) == title


def test_task_counts(watcher):
    tasks = watcher.parse_spec_tasks(SPEC_TEXT)
    assert watcher.task_counts(tasks) == {"done": 2, "in_progress": 1, "todo": 3}
    assert watcher.task_counts([]) == {"done": 0, "in_progress": 0, "todo": 0}


def test_parse_repo_spec_has_every_task_with_a_known_state(watcher):
    tasks = watcher.parse_spec_tasks(watcher.SPEC_PATH.read_text(encoding="utf-8"))
    ids = [t["id"] for t in tasks]
    assert len(ids) == len(set(ids)) and {"D1", "D3", "V0", "V9"} <= set(ids)
    assert all(t["state"] in ("done", "in_progress", "todo") and t["title"] and t["owner"] in ("viz-builder", "discovery-builder") for t in tasks)
    assert {t["area"] for t in tasks} == {"Discovery", "Visualization"}
    assert all(t["area"] == ("Discovery" if t["id"].startswith("D") else "Visualization") for t in tasks)


def test_spec_tasks_refresh_follows_the_file(watcher, tmp_path):
    path = tmp_path / "SPEC.md"
    spec = watcher.SpecTasks(path)
    assert spec.refresh() is False and spec.payload() == {"tasks": [], "task_counts": {"done": 0, "in_progress": 0, "todo": 0}, "spec_path": str(path)}
    path.write_text("## Tasks\n- [ ] V1: first.\n")
    assert spec.refresh() is True and [t["state"] for t in spec.tasks] == ["todo"]
    assert spec.refresh() is False
    path.write_text("## Tasks\n- [ ] V1: first.\n")
    assert spec.refresh() is False
    path.write_text("## Tasks\n- [~] V1: first.\n")
    assert spec.refresh() is True and spec.payload()["task_counts"] == {"done": 0, "in_progress": 1, "todo": 0}
    path.unlink()
    assert spec.refresh() is True and spec.tasks == []
    assert watcher.SpecTasks(None).refresh() is False and watcher.SpecTasks(None).payload()["spec_path"] is None


def test_spec_tasks_payload_is_a_copy(watcher, tmp_path):
    path = tmp_path / "SPEC.md"
    path.write_text("## Tasks\n- [x] V1: first.\n")
    spec = watcher.SpecTasks(path)
    spec.refresh()
    payload = spec.payload()
    payload["tasks"][0]["state"] = "todo"
    assert spec.tasks[0]["state"] == "done"


def test_watcher_emits_the_tasks_change_on_the_first_poll_and_on_edits(watcher, tmp_path):
    path = tmp_path / "SPEC.md"
    path.write_text("## Tasks\n- [~] V9: task panel. Full.\n- [ ] V10: next.\n")
    manager, builder = copy_fixtures(tmp_path)
    w = watcher.Watcher(fixtures=[(32813, str(manager)), (33993, str(builder))], spec_path=path)
    subscriber = w.broadcaster.subscribe()
    w.poll_once()
    events = drain(subscriber)
    assert [e["event"] for e in events[:3]] == ["session", "session", "tasks"]
    tasks_change = events[2]
    assert (tasks_change["source"], tasks_change["source_pid"], tasks_change["spec_path"]) == ("spec", None, str(path))
    assert tasks_change["task_counts"] == {"done": 0, "in_progress": 1, "todo": 1}
    assert [(t["id"], t["state"]) for t in tasks_change["tasks"]] == [("V9", "in_progress"), ("V10", "todo")]
    assert re.fullmatch(r".*Z", tasks_change["at"])
    assert len(events) == 3 + 31
    snapshot = w.snapshot()
    assert set(snapshot) == {"generated_at", "sessions", "messages", "sources", "tasks", "task_counts", "spec_path"}
    assert snapshot["task_counts"] == {"done": 0, "in_progress": 1, "todo": 1}
    w.poll_once()
    assert drain(subscriber) == []
    path.write_text("## Tasks\n- [x] V9: task panel. Full.\n- [~] V10: next.\n")
    w.poll_once()
    edited = drain(subscriber)
    assert [e["event"] for e in edited] == ["tasks"]
    assert [(t["id"], t["state"]) for t in edited[0]["tasks"]] == [("V9", "done"), ("V10", "in_progress")]
    assert w.snapshot()["task_counts"] == {"done": 1, "in_progress": 1, "todo": 0}


def test_watcher_without_a_spec_emits_no_tasks_change_and_empty_tasks(watcher, tmp_path):
    manager, builder = copy_fixtures(tmp_path)
    w = watcher.Watcher(fixtures=[(32813, str(manager)), (33993, str(builder))], spec_path=None)
    subscriber = w.broadcaster.subscribe()
    w.poll_once()
    assert all(e["event"] != "tasks" for e in drain(subscriber))
    snapshot = w.snapshot()
    assert (snapshot["tasks"], snapshot["task_counts"], snapshot["spec_path"]) == ([], {"done": 0, "in_progress": 0, "todo": 0}, None)


def test_watcher_default_spec_path_is_the_repo_spec(watcher):
    assert watcher.Watcher.__init__.__defaults__[-1] == watcher.SPEC_PATH
    assert watcher.SPEC_PATH.name == "SPEC.md" and watcher.SPEC_PATH.parent == watcher.VIZ_DIR.parent
    args = watcher.build_parser().parse_args(["serve"])
    assert args.spec == str(watcher.SPEC_PATH)
    assert watcher.build_parser().parse_args(["serve", "--spec", "/tmp/x.md"]).spec == "/tmp/x.md"
