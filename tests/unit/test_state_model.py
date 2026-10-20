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
    assert len(changes) == 29
    first = changes[0]
    assert (first["event"], first["pid"], first["status"], first["watching"], first["waiting_on"], first["at"]) == ("session", MANAGER, "WORKING", [BUILDER], [BUILDER], "2026-10-08T04:31:10.318Z")
    cleared = [c for c in changes if c["event"] == "session" and c["pid"] == MANAGER and c["at"] == "2026-10-08T04:31:21.055Z"]
    assert cleared and cleared[0]["watching"] == []
    manager_inbox = [c["inbox"] for c in changes if c["event"] == "session" and c["pid"] == MANAGER]
    assert manager_inbox == [0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0]
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


def test_enqueue_stamps_oldest_unenqueued_message_from_sender_and_promotes_it(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock", at="2026-10-08T04:31:10.000Z"))
    model.apply(1, send_entry("t2", "uds:/tmp/cc-socks/2.sock", at="2026-10-08T04:31:12.000Z"))
    changes = model.apply(2, enqueue_entry(1, at="2026-10-08T04:31:10.500Z"))
    assert model.messages["pending:t1"]["enqueued_at"] == "2026-10-08T04:31:10.500Z"
    assert model.messages["pending:t1"]["stage"] == "IN_INBOX"
    assert model.messages["pending:t2"]["stage"] == "PENDING"
    assert model.messages["pending:t2"]["enqueued_at"] is None
    assert [c["stage"] for c in changes if c["event"] == "message"] == ["IN_INBOX"]


def test_enqueue_does_not_demote_a_read_message(watcher):
    model = watcher.StateModel()
    model.apply(2, delivery_entry(1, "m-1"))
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock"))
    model.apply(1, result_entry("t1", msg_id="m-1"))
    model.apply(2, enqueue_entry(1))
    assert model.messages["m-1"]["stage"] == "READ"


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


def test_turn_duration_sets_idle_and_idle_since_only_on_change(watcher):
    model = watcher.StateModel()
    first = model.apply(1, turn_end())
    assert [(c["status"], c["idle_since"], c["activity"]) for c in first] == [("IDLE", "2026-10-08T04:31:13.415Z", None)]
    assert model.apply(1, turn_end()) == []
    model.apply(1, {"type": "assistant", "timestamp": "t", "message": {"content": []}})
    assert model.sessions[1]["status"] == "WORKING"
    changes = model.apply(1, turn_end())
    assert [(c["status"], c["idle_since"]) for c in changes] == [("IDLE", "2026-10-08T04:31:13.415Z")]
    later = model.apply(1, turn_end(at="2026-10-08T04:31:20.055Z"))
    assert [(c["status"], c["idle_since"]) for c in later] == [("IDLE", "2026-10-08T04:31:20.055Z")]


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


def test_receiver_read_adopts_the_senders_pending_row(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock", summary="sum", body="hello"))
    model.apply(2, enqueue_entry(1))
    changes = model.apply(2, delivery_entry(1, "m-1"))
    assert list(model.messages) == ["m-1"]
    message = model.messages["m-1"]
    assert (message["stage"], message["summary"], message["sent_at"], message["pending_key"], message["accepted_at"]) == (
        "READ", "sum", "2026-10-08T04:31:10.318Z", "pending:t1", None)
    assert [(c["key"], c["pending_key"]) for c in changes if c["event"] == "message"] == [("m-1", "pending:t1")]
    model.apply(1, result_entry("t1", msg_id="m-1"))
    assert list(model.messages) == ["m-1"]
    assert (model.messages["m-1"]["accepted_at"], model.messages["m-1"]["stage"]) == ("2026-10-08T04:31:11.281Z", "READ")


def test_adoption_picks_oldest_unmerged_send_to_that_receiver(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t-other", "uds:/tmp/cc-socks/3.sock", summary="to three", at="2026-10-08T04:31:09.000Z"))
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock", summary="first", at="2026-10-08T04:31:10.000Z"))
    model.apply(1, send_entry("t2", "uds:/tmp/cc-socks/2.sock", summary="second", at="2026-10-08T04:31:12.000Z"))
    model.apply(2, delivery_entry(1, "m-1"))
    assert model.messages["m-1"]["summary"] == "first"
    assert model.messages["pending:t2"]["stage"] == "PENDING"
    assert model.messages["pending:t-other"]["stage"] == "PENDING"


def test_adoption_skips_sends_already_merged_or_failed(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock", summary="failed one"))
    model.apply(1, result_entry("t1", success=False, msg_id=None, message="Not sent"))
    model.apply(1, send_entry("t2", "uds:/tmp/cc-socks/2.sock", summary="merged one", at="2026-10-08T04:31:12.000Z"))
    model.apply(1, result_entry("t2", msg_id="m-2"))
    model.apply(2, delivery_entry(1, "m-3", body="fresh"))
    assert model.messages["m-3"]["summary"] is None and model.messages["m-3"]["body"] == "fresh"
    assert model.messages["pending:t1"]["stage"] == "FAILED"
    assert model.messages["m-2"]["stage"] == "IN_INBOX"


def test_fixture_round_trip_has_one_row_per_message_at_every_step(watcher):
    model = registered = watcher.StateModel()
    tailer = watcher.TranscriptTailer(MANAGER_FIXTURE)
    for _timestamp, _index, pid, line in watcher.entries_in_time_order([(MANAGER, MANAGER_FIXTURE), (BUILDER, BUILDER_FIXTURE)]):
        entry = tailer.parse_line(line)
        if entry is None:
            continue
        model.apply(pid, entry)
        keys = [k for k in model.messages if not k.startswith("idle:")]
        assert len(keys) <= 2, keys
        assert not any(k.startswith("pending:") and any(m["pending_key"] == k and m["key"] != k for m in model.messages.values()) for k in keys)
    assert [m["summary"] for m in model.snapshot()["messages"] if m["kind"] == "message"] == ["second hello to fake-session-builder", "Second hi back to fake-session-manager"]


def human_prompt(at="2026-10-08T04:31:09.000Z"):
    return {"type": "user", "turnOrigin": "human", "timestamp": at, "message": {"role": "user", "content": "hi"}}


@pytest.mark.parametrize("entry, label", [
    (send_entry("t1", "uds:/tmp/cc-socks/2.sock"), "assistant → tool_use SendMessage"),
    ({"type": "assistant", "message": {"content": [{"type": "text", "text": "plain"}]}}, "assistant"),
    ({"type": "assistant", "message": {"content": "not a list"}}, "assistant"),
    (delivery_entry(1, "m-1"), "user · origin.kind = peer"),
    (idle_notice_entry("sender"), "user · cross-session idle notice"),
    (result_entry("t1"), "toolUseResult.success"),
    (result_entry("t1", success=False, msg_id=None), "toolUseResult.error"),
    (human_prompt(), "user"),
    (turn_end(), "system · turn_duration"),
    ({"type": "system", "subtype": "informational"}, "system · informational"),
    (enqueue_entry(1), "queue-operation · enqueue"),
    (queue_entry("dequeue"), "queue-operation · dequeue"),
    (queue_entry("remove"), "queue-operation · remove"),
    ({"type": "attachment", "attachment": {"type": "x"}}, "attachment"),
    ({"type": "agent-name", "agentName": "n"}, "agent-name"),
])
def test_entry_source_labels(watcher, entry, label):
    assert watcher.entry_source(entry) == label


def test_changes_carry_source_and_source_pid_and_snapshot_notes_the_source(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    model.register_session({"pid": 2, "name": "two"})
    changes = model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock"))
    assert [(c["event"], c["source"], c["source_pid"]) for c in changes] == [("session", "assistant → tool_use SendMessage", 1), ("message", "assistant → tool_use SendMessage", 1)]
    assert model.snapshot()["sources"] == [{"pid": 1, "at": "2026-10-08T04:31:10.318Z", "source": "assistant → tool_use SendMessage", "seq": 1}]
    assert model.apply(2, enqueue_entry(1, at="2026-10-08T04:31:10.817Z"))[0]["source_pid"] == 2
    assert [(s["pid"], s["source"], s["seq"]) for s in model.snapshot()["sources"]] == [(1, "assistant → tool_use SendMessage", 1), (2, "queue-operation · enqueue", 2)]


def test_entries_without_a_change_do_not_touch_sources(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    assert model.apply(1, {"type": "attachment", "timestamp": "2026-10-08T04:31:10.000Z"}) == []
    assert model.apply(1, {"type": "agent-name", "agentName": "one"}) == []
    assert model.snapshot()["sources"] == [] and model.source_sequence == 0


def test_note_source_keeps_one_row_per_pid_with_a_growing_seq(watcher):
    model = watcher.StateModel()
    model.note_source(1, "2026-10-08T04:31:00.000Z", watcher.REGISTRY_SOURCE)
    model.note_source(2, "2026-10-08T04:31:00.000Z", watcher.REGISTRY_SOURCE)
    model.note_source(1, "2026-10-08T04:31:01.000Z", "assistant")
    assert model.snapshot()["sources"] == [{"pid": 1, "at": "2026-10-08T04:31:01.000Z", "source": "assistant", "seq": 3}, {"pid": 2, "at": "2026-10-08T04:31:00.000Z", "source": "registry", "seq": 2}]


def test_send_claims_a_held_enqueue_and_starts_in_inbox(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    model.register_session({"pid": 2, "name": "two"})
    model.apply(2, enqueue_entry(1, from_name="one", at="2026-10-08T04:31:10.817Z"))
    assert model.unmatched_enqueues == {(1, 2): ["2026-10-08T04:31:10.817Z"]}
    changes = model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock"))
    pending = by_key_prefix(model, "pending:t1")
    assert (pending["stage"], pending["enqueued_at"], pending["to_pid"]) == ("IN_INBOX", "2026-10-08T04:31:10.817Z", 2)
    assert model.unmatched_enqueues == {(1, 2): []}
    assert [c["stage"] for c in changes if c["event"] == "message"] == ["IN_INBOX"]
    model.apply(1, result_entry("t1", msg_id="m-1"))
    assert (model.messages["m-1"]["stage"], model.messages["m-1"]["enqueued_at"]) == ("IN_INBOX", "2026-10-08T04:31:10.817Z")
    model.apply(2, delivery_entry(1, "m-1"))
    assert model.messages["m-1"]["stage"] == "READ" and len(model.messages) == 1


def test_send_without_a_held_enqueue_stays_pending(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    model.register_session({"pid": 2, "name": "two"})
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock"))
    pending = by_key_prefix(model, "pending:t1")
    assert (pending["stage"], pending["enqueued_at"]) == ("PENDING", None)


def test_send_to_an_unresolved_name_does_not_claim_a_held_enqueue(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    model.register_session({"pid": 2, "name": "two"})
    model.apply(2, enqueue_entry(1, from_name="one"))
    model.apply(1, send_entry("t1", "stranger"))
    pending = by_key_prefix(model, "pending:t1")
    assert (pending["stage"], pending["to_pid"], pending["enqueued_at"]) == ("PENDING", None, None)
    assert model.unmatched_enqueues == {(1, 2): ["2026-10-08T04:31:10.817Z"]}


def test_replay_freeze_of_the_reply_is_in_inbox_when_the_receiver_is_fed_first(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": MANAGER, "name": "fake-session-manager"})
    model.register_session({"pid": BUILDER, "name": "fake-session-builder"})
    until = "2026-10-08T04:31:17.600Z"
    for pid, path in [(MANAGER, MANAGER_FIXTURE), (BUILDER, BUILDER_FIXTURE)]:
        for entry in entries_of(path):
            if entry.get("timestamp") and entry["timestamp"] > until:
                break
            model.apply(pid, entry)
    reply = by_key_prefix(model, "pending:")
    assert (reply["from_pid"], reply["to_pid"], reply["stage"], reply["enqueued_at"]) == (BUILDER, MANAGER, "IN_INBOX", "2026-10-08T04:31:17.590Z")
    assert model.sessions[MANAGER]["inbox"] == 1


def tool_entry(name, inputs, at="2026-10-08T04:31:12.000Z", wire=None, text=None, tool_id="tool-1"):
    content = ([{"type": "text", "text": text}] if text else []) + [{"type": "tool_use", "id": tool_id, "name": name, "input": inputs}]
    entry = {"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": content}}
    if wire is not None:
        entry["wireToolInputs"] = {tool_id: wire}
    return entry


def text_entry(text, at="2026-10-08T04:31:12.000Z"):
    return {"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


@pytest.mark.parametrize("name, inputs, wire, expected", [
    ("Bash", {"command": "ls", "description": "List files"}, None, "Bash: List files"),
    ("SendMessage", {"to": "x", "summary": "V8 assigned", "message": "body"}, None, "SendMessage: V8 assigned"),
    ("Agent", {"description": "Review the diff", "prompt": "..."}, None, "Agent: Review the diff"),
    ("Read", {"file_path": "viz/web.html"}, None, "Read viz/web.html"),
    ("Edit", {"file_path": "scores.py", "old_string": "a", "new_string": "b"}, None, "Edit scores.py"),
    ("Grep", {"pattern": "activity", "path": "viz"}, None, "Grep viz"),
    ("Bash", {"command": "python3 -m pytest tests -q"}, None, "Bash python3 -m pytest tests -q"),
    ("WebFetch", {"url": "https://example.com/page"}, None, "WebFetch https://example.com/page"),
    ("Skill", {"skill": "deploy"}, None, "Skill deploy"),
    ("ToolSearch", {"query": "select:SendMessage"}, None, "ToolSearch select:SendMessage"),
    ("Agent", {"prompt": "first line of the prompt\nsecond"}, None, "Agent first line of the prompt"),
    ("SendMessage", {}, {"to": "y", "summary": "from the wire"}, "SendMessage: from the wire"),
    ("Bash", {"description": "Input wins"}, {"description": "Wire loses"}, "Bash: Input wins"),
    ("Bash", {"description": ""}, {"command": "echo"}, "Bash echo"),
    ("Mystery", {"other": 1}, None, "Mystery"),
    (None, {}, None, "tool"),
])
def test_describe_tool_use(watcher, name, inputs, wire, expected):
    block = {"type": "tool_use", "id": "tool-1", "input": inputs}
    if name is not None:
        block["name"] = name
    entry = {"wireToolInputs": {"tool-1": wire}} if wire is not None else {}
    assert watcher.describe_tool_use(block, entry) == expected


def test_first_line_skips_blank_lines_strips_and_truncates(watcher):
    assert watcher.first_line("\n   \n  second line here  \nthird") == "second line here"
    assert watcher.first_line(None) == "" and watcher.first_line("") == ""
    long = "x" * 200
    assert watcher.first_line(long) == "x" * 139 + "…"
    assert watcher.first_line("abc", limit=2) == "a…"


def test_tool_use_sets_activity_and_emits_one_session_change(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    changes = model.apply(1, tool_entry("Read", {"file_path": "viz/web.html"}))
    assert [(c["event"], c["activity"], c["activity_at"], c["status"]) for c in changes] == [("session", "Read viz/web.html", "2026-10-08T04:31:12.000Z", "WORKING")]
    assert model.apply(1, tool_entry("Read", {"file_path": "viz/web.html"}, at="2026-10-08T04:31:13.000Z")) == []
    assert model.sessions[1]["activity_at"] == "2026-10-08T04:31:12.000Z"
    changes = model.apply(1, tool_entry("Edit", {"file_path": "viz/web.html"}, at="2026-10-08T04:31:14.000Z", text="Fixing the label"))
    assert [(c["activity"], c["last_assistant_text"]) for c in changes] == [("Edit viz/web.html", "Fixing the label")]


def test_last_tool_use_in_an_entry_wins_and_send_still_creates_the_message(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    model.register_session({"pid": 2, "name": "two"})
    content = [
        {"type": "tool_use", "id": "s-1", "name": "SendMessage", "input": {"to": "uds:/tmp/cc-socks/2.sock", "summary": "hello", "message": "body"}},
        {"type": "tool_use", "id": "r-1", "name": "Read", "input": {"file_path": "SPEC.md"}},
    ]
    changes = model.apply(1, {"type": "assistant", "timestamp": "2026-10-08T04:31:12.000Z", "message": {"role": "assistant", "content": content}})
    assert model.sessions[1]["activity"] == "Read SPEC.md"
    assert [c["stage"] for c in changes if c["event"] == "message"] == ["PENDING"]


def test_text_only_entry_sets_activity_and_last_assistant_text(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    changes = model.apply(1, text_entry("First line of the answer.\nMore detail."))
    assert [(c["activity"], c["last_assistant_text"]) for c in changes] == [("First line of the answer.", "First line of the answer.")]
    assert model.apply(1, text_entry("   \n\n")) == [] or model.sessions[1]["activity"] == "First line of the answer."
    assert model.apply(1, {"type": "assistant", "timestamp": "t", "message": {"content": "not a list"}}) == []


def test_turn_end_sets_activity_to_the_last_assistant_text(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    model.apply(1, text_entry("Done with the review."))
    model.apply(1, tool_entry("Bash", {"command": "ls", "description": "List files"}, at="2026-10-08T04:31:12.500Z"))
    assert model.sessions[1]["activity"] == "Bash: List files"
    changes = model.apply(1, turn_end(at="2026-10-08T04:31:13.000Z"))
    assert [(c["status"], c["activity"], c["activity_at"], c["idle_since"]) for c in changes] == [("IDLE", "Done with the review.", "2026-10-08T04:31:13.000Z", "2026-10-08T04:31:13.000Z")]
    assert len(changes) == 1


def test_turn_end_without_assistant_text_keeps_the_tool_activity(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    model.apply(1, tool_entry("Bash", {"command": "ls", "description": "List files"}))
    model.apply(1, turn_end(at="2026-10-08T04:31:13.000Z"))
    assert (model.sessions[1]["activity"], model.sessions[1]["last_assistant_text"]) == ("Bash: List files", None)


def test_register_session_defaults_the_activity_fields(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 1, "name": "one"})
    session = model.sessions[1]
    assert (session["activity"], session["activity_at"], session["idle_since"], session["last_assistant_text"]) == (None, None, None, None)
    assert set(("activity", "activity_at", "idle_since", "last_assistant_text")) <= set(model.snapshot()["sessions"][0])


def test_fixture_round_trip_activity_sequence(watcher):
    model, changes = round_trip_model(watcher, True)
    manager = [(c["at"][17:23], c["status"], (c["activity"] or "")[:28]) for c in changes if c["event"] == "session" and c["pid"] == MANAGER and c["source"] in ("assistant", "system · turn_duration", "assistant → tool_use SendMessage")]
    assert manager == [
        ("10.318", "WORKING", "SendMessage: second hello to"),
        ("13.303", "WORKING", "The hello is in `fake-sessio"),
        ("13.415", "IDLE", "The hello is in `fake-sessio"),
        ("19.970", "WORKING", "The reply came back from `fa"),
        ("20.055", "IDLE", "The reply came back from `fa"),
        ("23.149", "WORKING", "The builder is idle again, s"),
        ("23.218", "IDLE", "The builder is idle again, s"),
    ]
    assert model.sessions[MANAGER]["idle_since"] == "2026-10-08T04:31:23.218Z"
    assert model.sessions[BUILDER]["idle_since"] == "2026-10-08T04:31:19.753Z"
    assert model.sessions[BUILDER]["activity"] == "Replied to fake-session-manager's second hello with another hi back. That's another pulse from this session to that one on the dashboard."


def test_waiting_on_holds_a_notify_subscription_until_the_idle_notice(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 2, "name": "builder"})
    model.apply(1, send_entry("t1", "builder", notify=True))
    assert model.sessions[1]["waiting_on"] == [2]
    model.apply(1, result_entry("t1"))
    model.apply(2, delivery_entry(1, "m-1"))
    assert model.messages["m-1"]["stage"] == "READ" and model.sessions[1]["waiting_on"] == [2]
    model.apply(1, idle_notice_entry("builder"))
    assert model.sessions[1]["waiting_on"] == [] and model.sessions[1]["watching"] == []


def test_waiting_on_holds_a_plain_send_until_it_is_read(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 2, "name": "builder"})
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock"))
    assert model.sessions[1]["waiting_on"] == [2]
    model.apply(1, result_entry("t1"))
    model.apply(2, enqueue_entry(1))
    assert model.messages["m-1"]["stage"] == "IN_INBOX" and model.sessions[1]["waiting_on"] == [2]
    changes = model.apply(2, delivery_entry(1, "m-1"))
    assert model.messages["m-1"]["stage"] == "READ" and model.sessions[1]["waiting_on"] == []
    assert sorted((c["pid"], tuple(c["waiting_on"])) for c in changes if c["event"] == "session") == [(1, ()), (2, ())]


def test_waiting_on_clears_when_the_send_fails(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock"))
    assert model.sessions[1]["waiting_on"] == [2]
    model.apply(1, result_entry("t1", success=False, msg_id=None, message="Not sent"))
    assert model.messages["pending:t1"]["stage"] == "FAILED" and model.sessions[1]["waiting_on"] == []


def test_waiting_on_skips_an_unresolved_name_until_it_is_learned(watcher):
    model = watcher.StateModel()
    model.apply(1, send_entry("t1", "later-named", notify=True))
    assert model.sessions[1]["watching"] == ["later-named"] and model.sessions[1]["waiting_on"] == []
    model.register_session({"pid": 2, "name": "later-named"})
    changes = model.apply(2, turn_end())
    assert model.sessions[1]["waiting_on"] == [2]
    assert [(c["pid"], c["waiting_on"]) for c in changes if c["event"] == "session"] == [(1, [2]), (2, [])]


def test_waiting_on_lists_each_target_once_watched_first_then_sends_by_time(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 2, "name": "b"})
    model.register_session({"pid": 3, "name": "c"})
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/3.sock", at="2026-10-08T04:31:10.318Z"))
    model.apply(1, send_entry("t2", "b", notify=True, at="2026-10-08T04:31:10.400Z"))
    model.apply(1, send_entry("t3", "uds:/tmp/cc-socks/3.sock", at="2026-10-08T04:31:10.500Z"))
    assert model.sessions[1]["waiting_on"] == [2, 3]
    assert model.sessions[2]["waiting_on"] == [] and model.sessions[3]["waiting_on"] == []


def test_waiting_on_is_not_re_emitted_when_unchanged(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 2, "name": "builder"})
    model.apply(1, send_entry("t1", "uds:/tmp/cc-socks/2.sock"))
    changes = model.apply(2, turn_end())
    assert [(c["pid"], c["waiting_on"]) for c in changes if c["event"] == "session"] == [(2, [])]
    assert model.snapshot()["sessions"][0]["waiting_on"] == [2]


def test_round_trip_waiting_on_in_time_order(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": MANAGER, "name": "fake-session-manager"})
    model.register_session({"pid": BUILDER, "name": "fake-session-builder"})
    tailer = watcher.TranscriptTailer(MANAGER_FIXTURE)
    waiting = []
    for timestamp, _index, pid, line in watcher.entries_in_time_order([(MANAGER, str(MANAGER_FIXTURE)), (BUILDER, str(BUILDER_FIXTURE))]):
        entry = tailer.parse_line(line)
        if entry is None:
            continue
        for change in model.apply(pid, entry):
            if change["event"] == "session":
                waiting.append((change["at"], change["pid"], change["waiting_on"]))
    manager = [(at, w) for at, pid, w in waiting if pid == MANAGER]
    builder = [(at, w) for at, pid, w in waiting if pid == BUILDER]
    assert manager[0] == ("2026-10-08T04:31:10.318Z", [BUILDER])
    assert all(w == [BUILDER] for at, w in manager if at < "2026-10-08T04:31:21.055Z")
    assert all(w == [] for at, w in manager if at >= "2026-10-08T04:31:21.055Z")
    assert [(at, w) for at, w in builder if w] == [("2026-10-08T04:31:16.750Z", [MANAGER])]
    assert ("2026-10-08T04:31:17.638Z", []) in builder
