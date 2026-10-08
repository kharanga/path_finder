import json

import pytest

from conftest import FIXTURES_DIR

MANAGER = 32813
BUILDER = 33993
MANAGER_FIXTURE = FIXTURES_DIR / "viz" / "round_trip_manager_32813_33993.jsonl"
BUILDER_FIXTURE = FIXTURES_DIR / "viz" / "round_trip_builder_32813_33993.jsonl"
FIRST_MSG = "693b9bd4-a916-40de-9ff1-aee2ee5dd741"
REPLY_MSG_PREFIX = "f5ac2c3a-"


def entries_of(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def feed(watcher, model, order):
    changes = []
    for pid, path in order:
        tailer = watcher.TranscriptTailer(path)
        for entry in tailer.poll():
            changes += model.apply(pid, entry)
    return changes


def round_trip_model(watcher, manager_first=True):
    model = watcher.StateModel()
    model.register_session({"pid": MANAGER, "name": "fake-session-manager"})
    model.register_session({"pid": BUILDER, "name": "fake-session-builder"})
    order = [(MANAGER, MANAGER_FIXTURE), (BUILDER, BUILDER_FIXTURE)]
    if not manager_first:
        order.reverse()
    changes = feed(watcher, model, order)
    return model, changes


def send_entry(tool_use_id, to, summary="s", body="b", notify=False, at="2026-10-08T04:31:10.318Z"):
    block = {"type": "tool_use", "id": tool_use_id, "name": "SendMessage", "input": {"to": to, "summary": summary, "message": body, "notify_when_idle": notify}}
    return {"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [block]}}


def result_entry(tool_use_id, success=True, msg_id="m-1", message="ok", at="2026-10-08T04:31:11.281Z"):
    result = {"success": success, "message": message}
    if msg_id is not None:
        result["msg_id"] = msg_id
    return {"type": "user", "timestamp": at, "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": [{"type": "text", "text": json.dumps(result)}]}]}, "toolUseResult": result}


def enqueue_entry(from_pid, from_name="sender", at="2026-10-08T04:31:10.817Z"):
    content = f'<cross-session-message from="uds:/tmp/cc-socks/{from_pid}.sock" from-name="{from_name}" from-mode="prompting">\nhello\n</cross-session-message>'
    return {"type": "queue-operation", "operation": "enqueue", "timestamp": at, "content": content}


def queue_entry(operation, at="2026-10-08T04:31:11.028Z"):
    return {"type": "queue-operation", "operation": operation, "timestamp": at}


def delivery_entry(from_pid, msg_id, body="hello", name="sender", at="2026-10-08T04:31:11.097Z", uuid="u-1"):
    return {"type": "user", "isMeta": True, "turnOrigin": "peer", "uuid": uuid, "timestamp": at, "origin": {"kind": "peer", "from": f"uds:/tmp/cc-socks/{from_pid}.sock", "verifiedPeerPid": from_pid, "msg_id": msg_id, "name": name, "body": body}, "message": {"role": "user", "content": "wrapped"}}


def idle_notice_entry(watched_name, at="2026-10-08T04:31:21.055Z", uuid="idle-1"):
    text = f'[Cross-session idle notice] "{watched_name}", which you asked to be notified about, is idle now'
    return {"type": "user", "isMeta": True, "turnOrigin": "system", "uuid": uuid, "timestamp": at, "message": {"role": "user", "content": text}}


def turn_end(at="2026-10-08T04:31:13.415Z"):
    return {"type": "system", "subtype": "turn_duration", "timestamp": at}


def by_key_prefix(model, prefix):
    matches = [m for k, m in model.messages.items() if k.startswith(prefix)]
    assert len(matches) == 1, [m["key"] for m in matches]
    return matches[0]


def test_fixture_line_counts(watcher):
    assert len(entries_of(MANAGER_FIXTURE)) == 29
    assert len(entries_of(BUILDER_FIXTURE)) == 16


def test_fixtures_are_sanitized():
    for path in (MANAGER_FIXTURE, BUILDER_FIXTURE):
        text = path.read_text()
        assert "/Users/" not in text
        assert "@sjsu" not in text


@pytest.mark.parametrize("manager_first", [True, False])
def test_round_trip_yields_two_read_messages_and_one_idle_notice(watcher, manager_first):
    model, _ = round_trip_model(watcher, manager_first)
    messages = model.snapshot()["messages"]
    assert [(m["kind"], m["stage"]) for m in messages] == [("message", "READ"), ("message", "READ"), ("idle_notice", "READ")]
    first, reply, notice = messages
    assert (first["from_pid"], first["to_pid"], first["msg_id"]) == (MANAGER, BUILDER, FIRST_MSG)
    assert (first["sent_at"], first["enqueued_at"], first["read_at"], first["accepted_at"]) == (
        "2026-10-08T04:31:10.318Z", "2026-10-08T04:31:10.817Z", "2026-10-08T04:31:11.097Z", "2026-10-08T04:31:11.281Z")
    assert (reply["from_pid"], reply["to_pid"]) == (BUILDER, MANAGER)
    assert reply["msg_id"].startswith(REPLY_MSG_PREFIX)
    assert (reply["sent_at"], reply["enqueued_at"], reply["read_at"], reply["accepted_at"]) == (
        "2026-10-08T04:31:16.750Z", "2026-10-08T04:31:17.590Z", "2026-10-08T04:31:17.638Z", "2026-10-08T04:31:17.811Z")
    assert (notice["from_pid"], notice["to_pid"]) == (BUILDER, MANAGER)
    assert notice["key"].startswith("idle:")
    assert notice["sent_at"] == notice["read_at"] == "2026-10-08T04:31:21.055Z"
    assert notice["accepted_at"] is None and notice["enqueued_at"] is None
    assert first["summary"] == "second hello to fake-session-builder"
    assert first["notify_when_idle"] is True
    assert reply["summary"] == "Second hi back to fake-session-manager"


@pytest.mark.parametrize("manager_first", [True, False])
def test_round_trip_session_state(watcher, manager_first):
    model, _ = round_trip_model(watcher, manager_first)
    manager, builder = model.snapshot()["sessions"]
    assert (manager["pid"], manager["status"], manager["inbox"], manager["watching"]) == (MANAGER, "IDLE", 0, [])
    assert (builder["pid"], builder["status"], builder["inbox"], builder["watching"]) == (BUILDER, "IDLE", 0, [])
    assert manager["last_text"].startswith("Hi again from fake-session-builder")
    assert builder["last_text"] == "Second hi back to fake-session-manager"
    assert manager["socket"] == "uds:/tmp/cc-socks/32813.sock"


def test_round_trip_snapshot_is_order_independent(watcher):
    first, _ = round_trip_model(watcher, True)
    second, _ = round_trip_model(watcher, False)
    strip = lambda snap: {
        "sessions": [{k: v for k, v in s.items() if k != "last_seen_at"} for s in snap["sessions"]],
        "messages": sorted(snap["messages"], key=lambda m: m["key"]),
    }
    assert strip(first.snapshot()) == strip(second.snapshot())


def test_round_trip_change_stream(watcher):
    _, changes = round_trip_model(watcher, True)
    assert len(changes) == 23
    first = changes[0]
    assert (first["event"], first["pid"], first["status"], first["watching"], first["at"]) == ("session", MANAGER, "WORKING", [BUILDER], "2026-10-08T04:31:10.318Z")
    cleared = [c for c in changes if c["event"] == "session" and c["pid"] == MANAGER and c["at"] == "2026-10-08T04:31:21.055Z"]
    assert cleared and cleared[0]["watching"] == []
    manager_inbox = [c["inbox"] for c in changes if c["event"] == "session" and c["pid"] == MANAGER]
    assert manager_inbox == [0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    pending = [c for c in changes if c["event"] == "message" and c["stage"] == "PENDING"]
    assert len(pending) == 2
    assert all(c["key"] == c["pending_key"] for c in pending)
    superseded = [c for c in changes if c["event"] == "message" and c["key"] != c["pending_key"]]
    assert all(c["pending_key"].startswith("pending:toolu_") for c in superseded)


def test_changes_are_deep_copies(watcher):
    model = watcher.StateModel()
    changes = model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock", notify=True))
    watching_before = list(changes[0]["watching"])
    model.sessions[1]["watching"].append(99)
    assert changes[0]["watching"] == watching_before


def test_pid_from_socket(watcher):
    assert watcher.pid_from_socket("uds:/tmp/cc-socks/32813.sock") == 32813
    assert watcher.pid_from_socket("uds:/tmp/cc-socks/abc.sock") is None
    assert watcher.pid_from_socket("fake-session-builder") is None
    assert watcher.pid_from_socket(None) is None
    assert watcher.pid_from_socket("uds:/tmp/cc-socks/1.sock.bak") is None


def test_bare_name_strips_ref_suffix(watcher):
    assert watcher.bare_name("worker [3fa9c1]") == "worker"
    assert watcher.bare_name("  worker  ") == "worker"
    assert watcher.bare_name("worker") == "worker"
    assert watcher.bare_name(None) is None


def test_resolve_target_by_socket_name_and_ref(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 7, "name": "builder"})
    assert model.resolve_target("uds:/tmp/cc-socks/7.sock") == 7
    assert model.resolve_target("builder") == 7
    assert model.resolve_target("builder [ab12]") == 7
    assert model.resolve_target("stranger") is None


def test_send_creates_pending_and_sets_last_text_and_watching(watcher):
    model = watcher.StateModel()
    changes = model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock", summary="sum", notify=True))
    message = model.messages["pending:t1"]
    assert (message["stage"], message["from_pid"], message["to_pid"], message["summary"], message["sent_at"]) == ("PENDING", 1, 2, "sum", "2026-10-08T04:31:10.318Z")
    session = model.sessions[1]
    assert (session["status"], session["last_text"], session["watching"]) == ("WORKING", "sum", [2])
    assert {c["event"] for c in changes} == {"session", "message"}


def test_send_to_unknown_name_watches_by_name_until_resolved(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "later-named", notify=True))
    assert model.sessions[1]["watching"] == ["later-named"]
    assert model.messages["pending:t1"]["to_pid"] is None
    model.apply(1, idle_notice_entry("later-named"))
    assert model.sessions[1]["watching"] == []


def test_successful_result_rekeys_to_msg_id_and_in_inbox(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock"))
    changes = model.apply(1, result_entry("t1", msg_id="m-1"))
    assert "pending:t1" not in model.messages
    message = model.messages["m-1"]
    assert (message["stage"], message["msg_id"], message["accepted_at"], message["pending_key"]) == ("IN_INBOX", "m-1", "2026-10-08T04:31:11.281Z", "pending:t1")
    assert changes[0]["key"] == "m-1" and changes[0]["pending_key"] == "pending:t1"


def test_failed_result_marks_failed_with_reason(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "nobody"))
    model.apply(1, result_entry("t1", success=False, msg_id=None, message="Not sent: no such session"))
    message = model.messages["pending:t1"]
    assert (message["stage"], message["reason"]) == ("FAILED", "Not sent: no such session")


def test_is_error_block_without_tool_use_result_marks_failed(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "nobody"))
    entry = {"type": "user", "timestamp": "2026-10-08T04:31:11.281Z", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "Not sent"}]}}
    model.apply(1, entry)
    assert model.messages["pending:t1"]["stage"] == "FAILED"


def test_success_without_msg_id_is_marked_failed(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "subagent"))
    model.apply(1, result_entry("t1", success=True, msg_id=None, message="delivered to in-process agent"))
    assert model.messages["pending:t1"]["stage"] == "FAILED"


def test_result_for_unknown_tool_use_is_ignored(watcher):
    model = watcher.StateModel()
    assert model.apply(1, result_entry("never-sent")) == []
    assert model.messages == {}


def test_enqueue_dequeue_and_remove_adjust_inbox_floored_at_zero(watcher):
    model = watcher.StateModel()
    model.apply(2, queue_entry("dequeue"))
    assert model.sessions[2]["inbox"] == 0
    model.apply(2, enqueue_entry(1))
    model.apply(2, enqueue_entry(1))
    assert model.sessions[2]["inbox"] == 2
    model.apply(2, queue_entry("dequeue"))
    assert model.sessions[2]["inbox"] == 1
    model.apply(2, queue_entry("remove"))
    assert model.sessions[2]["inbox"] == 0
    model.apply(2, queue_entry("remove"))
    assert model.sessions[2]["inbox"] == 0


def test_enqueue_stamps_oldest_unenqueued_message_from_sender(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock", at="2026-10-08T04:31:10.000Z"))
    model.apply(1, send_entry("t2", "uds:/tmp/cc-socks/2.sock", at="2026-10-08T04:31:12.000Z"))
    model.apply(2, enqueue_entry(1, at="2026-10-08T04:31:10.500Z"))
    assert model.messages["pending:t1"]["enqueued_at"] == "2026-10-08T04:31:10.500Z"
    assert model.messages["pending:t2"]["enqueued_at"] is None


def test_enqueue_before_sender_is_held_and_claimed_on_delivery(watcher):
    model = watcher.StateModel()
    model.apply(2, enqueue_entry(1, from_name="sender-name"))
    assert model.unmatched_enqueues == {(1, 2): ["2026-10-08T04:31:10.817Z"]}
    assert model.pid_by_name["sender-name"] == 1
    model.apply(2, delivery_entry(1, "m-1"))
    message = model.messages["m-1"]
    assert (message["stage"], message["from_pid"], message["to_pid"], message["enqueued_at"], message["read_at"], message["body"]) == (
        "READ", 1, 2, "2026-10-08T04:31:10.817Z", "2026-10-08T04:31:11.097Z", "hello")
    assert model.unmatched_enqueues[(1, 2)] == []


def test_receiver_first_then_sender_merges_on_msg_id(watcher):
    model = watcher.StateModel()
    model.apply(2, enqueue_entry(1))
    model.apply(2, delivery_entry(1, "m-1"))
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock", summary="sum", body="hello"))
    model.apply(1, result_entry("t1", msg_id="m-1"))
    assert "pending:t1" not in model.messages
    message = model.messages["m-1"]
    assert message["stage"] == "READ"
    assert (message["summary"], message["sent_at"], message["accepted_at"], message["pending_key"], message["tool_use_id"]) == (
        "sum", "2026-10-08T04:31:10.318Z", "2026-10-08T04:31:11.281Z", "pending:t1", "t1")
    assert len(model.messages) == 1


def test_delivery_without_msg_id_gets_peer_key(watcher):
    model = watcher.StateModel()
    entry = delivery_entry(1, None, uuid="u-9")
    del entry["origin"]["msg_id"]
    model.apply(2, entry)
    assert "peer:u-9" in model.messages


def test_delivery_sets_receiver_working_and_last_text(watcher):
    model = watcher.StateModel()
    model.apply(2, delivery_entry(1, "m-1", body="the body"))
    assert (model.sessions[2]["status"], model.sessions[2]["last_text"]) == ("WORKING", "the body")


def test_idle_notice_creates_one_shot_connector_and_clears_watching(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 2, "name": "builder"})
    model.apply(1, send_entry("t1", "builder", notify=True))
    assert model.sessions[1]["watching"] == [2]
    changes = model.apply(1, idle_notice_entry("builder", uuid="n-1"))
    notice = model.messages["idle:n-1"]
    assert (notice["kind"], notice["stage"], notice["from_pid"], notice["to_pid"], notice["summary"]) == ("idle_notice", "READ", 2, 1, "builder is idle")
    assert model.sessions[1]["watching"] == []
    assert model.sessions[1]["status"] == "WORKING"
    assert {c["event"] for c in changes} == {"session", "message"}


def test_system_prompt_without_idle_prefix_is_not_a_notice(watcher):
    model = watcher.StateModel()
    entry = {"type": "user", "turnOrigin": "system", "timestamp": "2026-10-08T04:31:21.055Z", "message": {"role": "user", "content": "[Cross-session delivery notice] held"}}
    assert model.apply(1, entry) == []
    assert model.messages == {}


def test_turn_duration_sets_idle_only_on_change(watcher):
    model = watcher.StateModel()
    assert model.apply(1, turn_end()) == []
    model.apply(1, {"type": "assistant", "timestamp": "t", "message": {"content": []}})
    assert model.sessions[1]["status"] == "WORKING"
    changes = model.apply(1, turn_end())
    assert changes[0]["status"] == "IDLE"


def test_human_prompt_sets_working(watcher):
    model = watcher.StateModel()
    model.apply(1, {"type": "user", "turnOrigin": "human", "timestamp": "t", "message": {"role": "user", "content": "go"}})
    assert model.sessions[1]["status"] == "WORKING"


def test_agent_name_rename_emits_once_and_updates_name_map(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "old"})
    assert len(model.apply(1, {"type": "agent-name", "agentName": "new"})) == 1
    assert model.sessions[1]["name"] == "new"
    assert model.apply(1, {"type": "agent-name", "agentName": "new"}) == []
    assert model.apply(1, {"type": "agent-name"}) == []
    assert model.pid_by_name["new"] == 1


def test_first_agent_name_on_bare_session_emits_a_change(watcher):
    model = watcher.StateModel()
    changes = model.apply(1, {"type": "agent-name", "agentName": "a"})
    assert model.sessions[1]["name"] == "a"
    assert [c["name"] for c in changes] == ["a"]


@pytest.mark.parametrize("entry", [{"type": "summary"}, {"type": "attachment", "attachment": {"type": "queued_command"}}, {"type": "unknown"}, {}])
def test_unhandled_entry_types_produce_no_change(watcher, entry):
    assert watcher.StateModel().apply(1, entry) == []


def test_register_session_keeps_registry_fields_and_defaults(watcher):
    model = watcher.StateModel()
    session = model.register_session({"pid": 5, "name": "n", "role": "manager", "label": "mgr", "session_id": "sid", "cwd": "/x"})
    assert session["socket"] == "uds:/tmp/cc-socks/5.sock"
    assert (session["status"], session["inbox"], session["watching"], session["last_text"]) == ("IDLE", 0, [], None)
    model.register_session({"pid": 5, "role": None})
    assert model.sessions[5]["role"] == "manager"
    bare = model.session(6)
    assert (bare["name"], bare["role"], bare["label"], bare["session_id"], bare["cwd"]) == (None, None, None, None, None)


def test_parse_fixture_argument(watcher):
    assert watcher.parse_fixture_argument("12=/a/b.jsonl") == (12, "/a/b.jsonl")
    for bad in ("x=/a", "12", "12=", "=/a"):
        with pytest.raises(Exception):
            watcher.parse_fixture_argument(bad)
