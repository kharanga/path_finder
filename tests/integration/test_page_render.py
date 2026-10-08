import json
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import FIXTURES_DIR, REPO_ROOT

PAGE = REPO_ROOT / "viz" / "index.html"
HARNESS = Path(__file__).resolve().parent.parent / "page" / "render_page.mjs"
FIXTURES = [(32813, str(FIXTURES_DIR / "viz" / "round_trip_manager_32813_33993.jsonl")), (33993, str(FIXTURES_DIR / "viz" / "round_trip_builder_32813_33993.jsonl"))]
CWD = "/home/user/path_finder/fake_session"
REGISTERED_AT = "2026-10-08T04:31:00.000Z"
FIRST_SUMMARY = "second hello to fake-session-builder"
REPLY_SUMMARY = "Second hi back to fake-session-manager"
FIRST_BODY_START = "Hi again from fake-session-manager"
REPLY_BODY_START = "Hi again from fake-session-builder"
FRAME_TIMES = {1: "10.300", 2: "10.500", 3: "11.000", 4: "13.500", 5: "17.000", 6: "17.600", 7: "19.800", 8: "20.100", 9: "30.000"}
SEND_SOURCE = "assistant → tool_use SendMessage"
ENQUEUE_SOURCE = "queue-operation · enqueue"
TURN_END_SOURCE = "system · turn_duration"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is needed to run the page script")


def frame_time(frame):
    return f"2026-10-08T04:31:{FRAME_TIMES[frame]}Z"


def registered_model(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 32813, "name": "fake-session-manager", "role": "fake session manager", "label": "fake manager", "cwd": CWD})
    model.register_session({"pid": 33993, "name": "fake-session-builder", "role": "fake-session-builder", "label": "fake builder", "cwd": CWD})
    for pid in (32813, 33993):
        model.note_source(pid, REGISTERED_AT, watcher.REGISTRY_SOURCE)
    return model


def replay_until(watcher, model, until, after=None):
    tailer = watcher.TranscriptTailer(FIXTURES[0][1])
    changes = []
    for timestamp, _index, pid, line in watcher.entries_in_time_order(FIXTURES):
        if until and timestamp and timestamp > until:
            break
        entry = tailer.parse_line(line)
        if entry is None:
            continue
        produced = model.apply(pid, entry)
        if after is None or (timestamp and timestamp > after):
            changes += produced
    return changes


def snapshot_at(watcher, until):
    model = registered_model(watcher)
    replay_until(watcher, model, until)
    return {"generated_at": until or "2026-10-08T04:32:00.000Z", **model.snapshot()}


def render(tmp_path, snapshot, frames=(), open_stream=True, error=False, advance_ms=0, click_pair=None, click_arc=None, close_panel=False):
    input_path = tmp_path / "input.json"
    payload = {"snapshot": snapshot, "frames": list(frames), "open": open_stream, "error": error, "advanceMs": advance_ms, "closePanel": close_panel}
    if click_pair is not None:
        payload["clickPair"] = click_pair
    if click_arc is not None:
        payload["clickArc"] = click_arc
    input_path.write_text(json.dumps(payload))
    result = subprocess.run(["node", str(HARNESS), str(PAGE), str(input_path)], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def cards_of(rendered):
    return {card["label"]: card for row in rendered["rows"] for card in row["cards"]}


def pill_texts(card):
    return [text for _class, text in card["pills"]]


def only_link(rendered):
    links = [link for row in rendered["rows"] for link in row["links"]]
    assert len(links) == 1
    return links[0]


def link_lines(link):
    return [tuple(line) for line in link["lines"]]


def caption_of(rendered):
    return rendered["rows"][0]["caption"]


def assert_quiet_card(card, status="Idle"):
    assert card["status"] == status
    assert pill_texts(card) == [status]
    assert card["watching"] == "" and card["last"] == "" and card["lastTitle"] == ""


def test_frame_1_both_idle_no_traffic(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, frame_time(1)))
    assert rendered["count"] == "2 sessions, 2 identified, 0 working"
    assert rendered["link"] == "live · 0 events" and rendered["eventsUrl"] == "./events"
    assert [row["folder"] for row in rendered["rows"]] == ["fake_session"]
    assert rendered["rows"][0]["folderHidden"] is True
    manager, builder = cards_of(rendered)["fake manager"], cards_of(rendered)["fake builder"]
    assert_quiet_card(manager)
    assert_quiet_card(builder)
    assert (manager["id"], manager["pid"], manager["title"]) == ("session-32813", 32813, "fake-session-manager · pid 32813")
    assert (manager["dot"], builder["dot"]) == ("var(--dot-manager)", "var(--dot-builder)")
    assert [card["className"] for card in (manager, builder)] == ["card", "card"]
    link = only_link(rendered)
    assert link_lines(link) == [("none", "No traffic")]
    assert link["stage"] is None and link["clickable"] is False
    assert rendered["rows"][0]["arcs"] == []
    assert caption_of(rendered) == "registry"


def test_frame_2_manager_sending_pending_connector(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, frame_time(2)))
    manager, builder = cards_of(rendered)["fake manager"], cards_of(rendered)["fake builder"]
    assert rendered["count"] == "2 sessions, 2 identified, 1 working"
    assert manager["status"] == "Sending" and manager["pills"] == [["pill status busy", "Sending"]]
    assert manager["watching"] == "Watching fake builder"
    assert manager["watchingTitle"] == "asked to be told when fake builder goes idle"
    assert (manager["last"], manager["lastTitle"]) == (f"“{FIRST_SUMMARY}”", FIRST_SUMMARY)
    assert_quiet_card(builder)
    link = only_link(rendered)
    assert link_lines(link) == [("summary", FIRST_SUMMARY), ("arrow", "→"), ("stage PENDING", "Pending")]
    assert (link["pair"], link["stage"], link["clickable"]) == ("32813:33993", "PENDING", True)
    assert caption_of(rendered) == SEND_SOURCE


def test_frame_3_in_inbox_with_builder_badge(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, frame_time(3)))
    manager, builder = cards_of(rendered)["fake manager"], cards_of(rendered)["fake builder"]
    assert manager["status"] == "Working" and manager["pills"] == [["pill status busy", "Working"]]
    assert manager["watching"] == "Watching fake builder" and manager["last"] == ""
    assert builder["status"] == "Idle" and builder["pills"] == [["pill status", "Idle"], ["pill inbox", "Inbox 1"]]
    assert builder["last"] == "" and builder["watching"] == ""
    link = only_link(rendered)
    assert link_lines(link) == [("summary", FIRST_SUMMARY), ("arrow", "→"), ("stage IN_INBOX", "✓ In inbox")]
    assert link["stageTitle"].startswith(f"IN_INBOX\n{FIRST_BODY_START}")
    assert caption_of(rendered) == ENQUEUE_SOURCE


def test_frame_4_read_with_builder_working_on_the_body(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, frame_time(4)))
    manager, builder = cards_of(rendered)["fake manager"], cards_of(rendered)["fake builder"]
    assert manager["status"] == "Idle" and pill_texts(manager) == ["Idle"]
    assert manager["watching"] == "Watching fake builder" and manager["last"] == ""
    assert builder["status"] == "Working" and pill_texts(builder) == ["Working"]
    assert builder["last"].startswith(f"“{FIRST_BODY_START}") and builder["last"].endswith("”")
    assert builder["last"] == f"“{builder['lastTitle']}”" and builder["lastTitle"].startswith(FIRST_BODY_START)
    link = only_link(rendered)
    assert link_lines(link) == [("summary", FIRST_SUMMARY), ("arrow", "→"), ("stage READ", "✓✓ Read")]
    assert caption_of(rendered) == TURN_END_SOURCE


def test_frame_5_builder_sending_the_reply(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, frame_time(5)))
    manager, builder = cards_of(rendered)["fake manager"], cards_of(rendered)["fake builder"]
    assert manager["status"] == "Idle" and pill_texts(manager) == ["Idle"]
    assert manager["watching"] == "Watching fake builder" and manager["last"] == ""
    assert builder["status"] == "Sending" and builder["pills"] == [["pill status busy", "Sending"]]
    assert (builder["last"], builder["lastTitle"]) == (f"“{REPLY_SUMMARY}”", REPLY_SUMMARY)
    link = only_link(rendered)
    assert link_lines(link) == [("summary", REPLY_SUMMARY), ("arrow", "←"), ("stage PENDING", "Pending")]
    assert caption_of(rendered) == SEND_SOURCE


def test_frame_6_reply_in_manager_inbox(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, frame_time(6)))
    manager, builder = cards_of(rendered)["fake manager"], cards_of(rendered)["fake builder"]
    assert manager["status"] == "Idle" and manager["pills"] == [["pill status", "Idle"], ["pill inbox", "Inbox 1"]]
    assert manager["watching"] == "Watching fake builder" and manager["last"] == ""
    assert builder["status"] == "Working" and pill_texts(builder) == ["Working"] and builder["last"] == ""
    link = only_link(rendered)
    assert link_lines(link) == [("summary", REPLY_SUMMARY), ("arrow", "←"), ("stage IN_INBOX", "✓ In inbox")]
    assert caption_of(rendered) == ENQUEUE_SOURCE


def test_frame_7_manager_reads_the_reply(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, frame_time(7)))
    manager, builder = cards_of(rendered)["fake manager"], cards_of(rendered)["fake builder"]
    assert manager["status"] == "Working" and pill_texts(manager) == ["Working"]
    assert manager["watching"] == "Watching fake builder"
    assert manager["last"].startswith(f"“{REPLY_BODY_START}") and manager["lastTitle"].startswith(REPLY_BODY_START)
    assert_quiet_card(builder)
    link = only_link(rendered)
    assert link_lines(link) == [("summary", REPLY_SUMMARY), ("arrow", "←"), ("stage READ", "✓✓ Read")]
    assert caption_of(rendered) == TURN_END_SOURCE


def test_frame_9_both_idle_watching_cleared_notice_gone(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, frame_time(9)))
    manager, builder = cards_of(rendered)["fake manager"], cards_of(rendered)["fake builder"]
    assert rendered["count"] == "2 sessions, 2 identified, 0 working"
    assert manager["status"] == "Idle" and pill_texts(manager) == ["Idle"] and manager["watching"] == ""
    assert manager["last"].startswith(f"“{REPLY_BODY_START}")
    assert builder["status"] == "Idle" and pill_texts(builder) == ["Idle"] and builder["watching"] == ""
    assert builder["last"] == ""
    link = only_link(rendered)
    assert link_lines(link) == [("summary", REPLY_SUMMARY), ("arrow", "←"), ("stage READ", "✓✓ Read")]
    assert caption_of(rendered) == TURN_END_SOURCE


@pytest.mark.parametrize("frame", [2, 3, 4, 5, 6, 7, 9])
def test_change_stream_renders_each_frame_like_its_frozen_snapshot(watcher, tmp_path, frame):
    base = snapshot_at(watcher, frame_time(1))
    model = registered_model(watcher)
    frames = replay_until(watcher, model, frame_time(frame), after=frame_time(1))
    assert frames
    streamed = render(tmp_path, base, frames=frames, advance_ms=4000 if frame == 9 else 0)
    frozen = render(tmp_path, snapshot_at(watcher, frame_time(frame)))
    assert streamed["rows"] == frozen["rows"]
    assert streamed["count"] == frozen["count"]
    assert streamed["link"] == f"live · {len(frames)} events"


def test_frame_8_idle_notice_line_appears_on_the_stream_and_expires(watcher, tmp_path):
    frozen = snapshot_at(watcher, frame_time(8))
    before = render(tmp_path, frozen)
    assert link_lines(only_link(before))[-1] == ("stage READ", "✓✓ Read")
    assert cards_of(before)["fake manager"]["watching"] == "Watching fake builder"
    model = registered_model(watcher)
    rest = replay_until(watcher, model, None, after=frame_time(8))
    assert any(change["event"] == "message" and change["kind"] == "idle_notice" for change in rest)
    shown = render(tmp_path, frozen, frames=rest)
    link = only_link(shown)
    assert link["stage"] == "READ"
    assert link_lines(link) == [("summary", REPLY_SUMMARY), ("arrow", "←"), ("stage READ", "✓✓ Read"), ("notice", "fake-session-builder is idle")]
    assert cards_of(shown)["fake manager"]["watching"] == ""
    assert caption_of(shown) == TURN_END_SOURCE
    expired = render(tmp_path, frozen, frames=rest, advance_ms=4000)
    assert link_lines(only_link(expired)) == [("summary", REPLY_SUMMARY), ("arrow", "←"), ("stage READ", "✓✓ Read")]


def test_snapshot_loaded_within_notice_lifetime_shows_the_notice_once(watcher, tmp_path):
    recent = snapshot_at(watcher, None)
    recent["generated_at"] = "2026-10-08T04:31:22.000Z"
    assert ("notice", "fake-session-builder is idle") in link_lines(only_link(render(tmp_path, recent)))
    later = dict(recent, generated_at="2026-10-08T04:32:00.000Z")
    assert all(line[0] != "notice" for line in link_lines(only_link(render(tmp_path, later))))


def test_clicking_the_connector_opens_the_pair_panel_newest_first(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, None), click_pair="32813:33993")
    assert rendered["panel"]["open"] is True
    assert rendered["panel"]["title"] == "fake manager ↔ fake builder (2)"
    reply, first = rendered["panel"]["entries"]
    assert reply[0] == "fake builder → fake manager · ✓✓ Read" and reply[1] == REPLY_SUMMARY and reply[2].startswith(REPLY_BODY_START)
    assert reply[3] == "sent 04:31:16.750 · accepted 04:31:17.811 · enqueued 04:31:17.590 · read 04:31:17.638"
    assert first[0] == "fake manager → fake builder · ✓✓ Read" and first[1] == FIRST_SUMMARY and first[2].startswith(FIRST_BODY_START)
    assert first[3] == "sent 04:31:10.318 · accepted 04:31:11.281 · enqueued 04:31:10.817 · read 04:31:11.097"
    closed = render(tmp_path, snapshot_at(watcher, None), click_pair="32813:33993", close_panel=True)
    assert closed["panel"]["open"] is False


def session(pid, name, cwd="/x", role="r", label=None, status="IDLE", inbox=0, watching=()):
    return {"pid": pid, "name": name, "role": role, "label": label or name, "cwd": cwd, "status": status, "inbox": inbox, "last_text": None, "watching": list(watching), "socket": f"uds:/tmp/cc-socks/{pid}.sock"}


def message(key, from_pid, to_pid, stage, summary, sent_at, body="body", to=None, reason=None, accepted_at=None, enqueued_at=None, read_at=None):
    return {"key": key, "pending_key": key if key.startswith("pending:") else None, "msg_id": None if key.startswith("pending:") else key, "kind": "message", "from_pid": from_pid, "to_pid": to_pid,
        "to": to or (f"uds:/tmp/cc-socks/{to_pid}.sock" if to_pid else None), "summary": summary, "body": body, "stage": stage, "reason": reason, "sent_at": sent_at,
        "accepted_at": accepted_at, "enqueued_at": enqueued_at, "read_at": read_at, "notify_when_idle": False, "tool_use_id": key}


def source(pid, label, seq, at="2026-10-08T04:31:10.000Z"):
    return {"pid": pid, "at": at, "source": label, "seq": seq}


def synthetic(sessions, messages=(), sources=(), generated_at="2026-10-08T04:31:12.000Z"):
    return {"generated_at": generated_at, "sessions": list(sessions), "messages": list(messages), "sources": list(sources)}


def test_non_neighbour_pairs_get_tiered_clickable_arcs(tmp_path):
    sessions = [session(1, "a"), session(2, "b"), session(3, "c"), session(4, "d")]
    messages = [
        message("m13", 1, 3, "READ", "one to three", "2026-10-08T04:31:10.000Z", read_at="2026-10-08T04:31:11.000Z"),
        message("m14", 1, 4, "IN_INBOX", "one to four", "2026-10-08T04:31:10.500Z", enqueued_at="2026-10-08T04:31:11.000Z"),
        message("pending:t24", 4, 2, "PENDING", "four to two", "2026-10-08T04:31:12.000Z"),
        message("pending:t12", 1, 2, "PENDING", "one to two", "2026-10-08T04:31:12.000Z"),
    ]
    rendered = render(tmp_path, synthetic(sessions, messages), click_arc=0)
    row = rendered["rows"][0]
    assert [(link["pair"], link["stage"]) for link in row["links"]] == [("1:2", "PENDING"), ("2:3", None), ("3:4", None)]
    assert [arc["class"] for arc in row["arcs"]] == ["arc READ", "arc PENDING", "arc IN_INBOX"]
    assert [arc["text"] for arc in row["arcs"]] == ["one to three → ✓✓ Read", "four to two ← Pending", "one to four → ✓ In inbox"]
    assert [arc["y"] for arc in row["arcs"]] == [52, 22, -8]
    assert [arc["x"] for arc in row["arcs"]] == [596, 1016, 806]
    assert all(arc["clickable"] for arc in row["arcs"])
    assert row["paddingTop"] == "120px"
    assert rendered["panel"]["title"] == "a ↔ c (1)"


def test_failed_message_and_target_resolved_by_name(tmp_path):
    sessions = [session(1, "alpha"), session(2, "beta")]
    messages = [
        message("pending:t1", 1, None, "FAILED", "will fail", "2026-10-08T04:31:10.000Z", to="beta [ab12]", reason="Not sent: refused", accepted_at="2026-10-08T04:31:10.500Z"),
        message("pending:t2", 1, None, "PENDING", "lost", "2026-10-08T04:31:11.000Z", to="nobody"),
    ]
    rendered = render(tmp_path, synthetic(sessions, messages))
    link = only_link(rendered)
    assert link["stage"] == "FAILED"
    assert link_lines(link) == [("summary", "will fail"), ("arrow", "→"), ("stage FAILED", "✗ Failed")]
    assert link["stageTitle"].startswith("FAILED: Not sent: refused")
    alpha = cards_of(rendered)["alpha"]
    assert alpha["status"] == "Idle" and alpha["last"] == "“lost”"


def test_status_pill_derivation(tmp_path):
    sessions = [session(1, "a", status="WORKING"), session(2, "b", status="WORKING"), session(3, "c", status="IDLE"), session(4, "d", status="WORKING")]
    messages = [
        message("pending:t1", 1, 2, "PENDING", "pending send", "2026-10-08T04:31:10.000Z"),
        message("m2", 2, 1, "IN_INBOX", "accepted send", "2026-10-08T04:31:10.000Z", accepted_at="2026-10-08T04:31:10.500Z"),
        message("pending:t3", 3, 1, "PENDING", "idle pending", "2026-10-08T04:31:10.000Z"),
    ]
    cards = cards_of(render(tmp_path, synthetic(sessions, messages)))
    assert [cards[name]["status"] for name in "abcd"] == ["Sending", "Working", "Idle", "Working"]
    assert [cards[name]["pills"][0][0] for name in "abcd"] == ["pill status busy", "pill status busy", "pill status", "pill status busy"]


def test_last_line_follows_the_latest_send_or_read(tmp_path):
    sessions = [session(1, "a"), session(2, "b")]
    read_then_send = [
        message("m1", 2, 1, "READ", "from b", "2026-10-08T04:31:10.000Z", body="b wrote this", read_at="2026-10-08T04:31:11.000Z"),
        message("pending:t2", 1, 2, "PENDING", None, "2026-10-08T04:31:12.000Z", body="a body only"),
    ]
    cards = cards_of(render(tmp_path, synthetic(sessions, read_then_send)))
    assert cards["a"]["last"] == "“a body only”"
    assert cards["b"]["last"] == ""
    send_then_read = [
        message("m1", 1, 2, "IN_INBOX", "from a", "2026-10-08T04:31:10.000Z", accepted_at="2026-10-08T04:31:10.500Z"),
        message("m2", 2, 1, "READ", "from b", "2026-10-08T04:31:12.000Z", body="b wrote this", read_at="2026-10-08T04:31:13.000Z"),
    ]
    cards = cards_of(render(tmp_path, synthetic(sessions, send_then_read)))
    assert cards["a"]["last"] == "“b wrote this”"
    assert cards["b"]["last"] == ""


def test_unidentified_session_and_long_last_line(tmp_path):
    long_summary = "x" * 200
    sessions = [session(1, "nameless", role=None, label=None), session(2, "talker")]
    messages = [message("pending:t1", 2, 1, "PENDING", long_summary, "2026-10-08T04:31:10.000Z")]
    rendered = render(tmp_path, synthetic(sessions, messages))
    assert rendered["count"] == "2 sessions, 1 identified, 0 working"
    nameless = cards_of(rendered)["nameless"]
    assert nameless["className"] == "card incomplete"
    assert nameless["title"] == "unidentified: this session has not run identify"
    assert nameless["dot"] == "#f472b6"
    talker = cards_of(rendered)["talker"]
    assert talker["last"] == "“" + "x" * 89 + "…”"
    assert talker["lastTitle"] == long_summary
    assert only_link(rendered)["lines"][0][1] == "x" * 59 + "…"


def test_two_folders_show_titles_sorted(tmp_path):
    rendered = render(tmp_path, synthetic([session(1, "a", cwd="/home/user/zeta"), session(2, "b", cwd="/home/user/alpha")]))
    assert [(row["folder"], row["folderHidden"]) for row in rendered["rows"]] == [("alpha", False), ("zeta", False)]
    assert all(link_lines(row["links"][0]) == [("none", "No traffic")] for row in rendered["rows"] if row["links"])


def test_caption_takes_the_highest_seq_in_the_row_and_follows_changes(tmp_path):
    sources = [source(1, "registry", 5), source(2, "assistant", 3)]
    rendered = render(tmp_path, synthetic([session(1, "a"), session(2, "b")], sources=sources))
    assert caption_of(rendered) == "registry"
    change = {"event": "session", "at": "2026-10-08T04:31:13.000Z", "source": "system · turn_duration", "source_pid": 2, **session(2, "b", status="IDLE")}
    rendered = render(tmp_path, synthetic([session(1, "a"), session(2, "b")], sources=sources), frames=[change])
    assert caption_of(rendered) == "system · turn_duration"
    assert rendered["updated"] == "updated 2026-10-08T04:31:13.000Z"


def test_session_removed_drops_the_card_and_its_source(tmp_path):
    sources = [source(1, "registry", 1), source(2, "assistant", 2)]
    removal = {"event": "session_removed", "at": "2026-10-08T04:31:13.000Z", "source": "registry", "source_pid": 2, "pid": 2}
    rendered = render(tmp_path, synthetic([session(1, "a"), session(2, "b")], sources=sources), frames=[removal])
    assert rendered["count"] == "1 sessions, 1 identified, 0 working"
    assert list(cards_of(rendered)) == ["a"]
    assert rendered["rows"][0]["links"] == []
    assert caption_of(rendered) == "registry"


def test_snapshot_event_on_the_stream_replaces_state(tmp_path):
    replacement = {"event": "snapshot", **synthetic([session(9, "only")], sources=[source(9, "registry", 1)], generated_at="2026-10-08T04:31:20.000Z")}
    rendered = render(tmp_path, synthetic([session(1, "a"), session(2, "b")]), frames=[replacement])
    assert list(cards_of(rendered)) == ["only"]
    assert caption_of(rendered) == "registry"
    assert rendered["updated"] == "updated 2026-10-08T04:31:20.000Z"


def test_stream_error_switches_to_state_polling(tmp_path):
    rendered = render(tmp_path, synthetic([session(1, "a")]), error=True)
    assert (rendered["link"], rendered["linkClass"], rendered["fallbackPolls"]) == ("reconnecting", "off", 1)


def test_empty_snapshot_shows_placeholder(tmp_path):
    rendered = render(tmp_path, synthetic([]))
    assert rendered["rows"] == [{"empty": "No sessions discovered yet"}]
    assert rendered["count"] == ""
