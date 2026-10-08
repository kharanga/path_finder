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

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is needed to run the page script")


def registered_model(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 32813, "name": "fake-session-manager", "role": "fake session manager", "label": "fake manager", "cwd": CWD})
    model.register_session({"pid": 33993, "name": "fake-session-builder", "role": "fake-session-builder", "label": "fake builder", "cwd": CWD})
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


def lines_by_class(rendered):
    return sorted(line["class"] for line in rendered["lines"])


def tag_texts(rendered):
    return [(tag["class"], tag["text"]) for tag in rendered["tags"]]


def render(tmp_path, snapshot, frames=(), open_stream=True, error=False, advance_ms=0, click_tag=None):
    input_path = tmp_path / "input.json"
    payload = {"snapshot": snapshot, "frames": list(frames), "open": open_stream, "error": error, "advanceMs": advance_ms}
    if click_tag is not None:
        payload["clickTag"] = click_tag
    input_path.write_text(json.dumps(payload))
    result = subprocess.run(["node", str(HARNESS), str(PAGE), str(input_path)], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def capsules_of(rendered):
    return {c["label"]: c for row in rendered["rows"] for c in row["capsules"]}


def snapshot_at(watcher, until):
    model = registered_model(watcher)
    replay_until(watcher, model, until)
    return {"generated_at": until or "2026-10-08T04:32:00.000Z", **model.snapshot()}


def test_frame_1_both_idle_and_empty(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:00.000Z"))
    assert rendered["count"] == "2 sessions, 2 identified, 0 working"
    assert rendered["link"] == "live · 0 events"
    assert rendered["eventsUrl"] == "./events"
    assert rendered["lines"] == [] and rendered["tags"] == []
    assert [row["folder"] for row in rendered["rows"]] == ["fake_session"]
    manager, builder = capsules_of(rendered)["fake manager"], capsules_of(rendered)["fake builder"]
    for capsule in (manager, builder):
        assert capsule["pill"] == "Idle" and "working" not in capsule["pillClass"]
        assert capsule["badge"] is None and capsule["last"] == "" and capsule["watching"] == ""
        assert "incomplete" not in capsule["className"]
    assert (manager["id"], manager["pid"], manager["meta"]) == ("session-32813", "32813", "fake-session-manager · pid 32813")


def test_frame_2_manager_working_with_last_line_and_watching(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:10.400Z"))
    manager, builder = capsules_of(rendered)["fake manager"], capsules_of(rendered)["fake builder"]
    assert rendered["count"] == "2 sessions, 2 identified, 1 working"
    assert manager["pill"] == "Working" and "working" in manager["pillClass"] and "working" in manager["className"]
    assert manager["last"] == "second hello to fake-session-builder"
    assert manager["watching"] == "👁 watching fake builder"
    assert manager["badge"] is None
    assert builder["pill"] == "Idle" and builder["badge"] is None and builder["last"] == ""


def test_frame_3_builder_shows_inbox_badge(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:11.000Z"))
    manager, builder = capsules_of(rendered)["fake manager"], capsules_of(rendered)["fake builder"]
    assert builder["badge"] == "1" and builder["pill"] == "Idle" and builder["last"] == ""
    assert manager["pill"] == "Working" and manager["watching"] == "👁 watching fake builder"


def test_frame_4_builder_working_with_delivered_text(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:11.200Z"))
    builder = capsules_of(rendered)["fake builder"]
    assert builder["pill"] == "Working" and builder["badge"] is None
    assert builder["last"].startswith("Hi again from fake-session-manager")
    assert builder["lastTitle"].startswith("Hi again from fake-session-manager")
    assert rendered["count"] == "2 sessions, 2 identified, 2 working"


def test_final_frame_both_idle_watching_cleared(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, None))
    manager, builder = capsules_of(rendered)["fake manager"], capsules_of(rendered)["fake builder"]
    assert manager["pill"] == "Idle" and builder["pill"] == "Idle"
    assert manager["watching"] == "" and manager["badge"] is None
    assert manager["last"].startswith("Hi again from fake-session-builder")
    assert builder["last"] == "Second hi back to fake-session-manager"
    assert rendered["count"] == "2 sessions, 2 identified, 0 working"


def test_event_deltas_reach_the_same_render_as_the_final_snapshot(watcher, tmp_path):
    model = registered_model(watcher)
    changes = replay_until(watcher, model, None)
    from_stream = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:00.000Z"), frames=changes)
    from_snapshot = render(tmp_path, snapshot_at(watcher, None))
    assert from_stream["rows"] == from_snapshot["rows"]
    assert from_stream["count"] == from_snapshot["count"]
    assert from_stream["updated"] == "updated 2026-10-08T04:31:23.218Z"
    assert from_stream["link"] == f"live · {len(changes)} events"


def test_snapshot_frame_on_the_stream_replaces_state(watcher, tmp_path):
    initial = snapshot_at(watcher, "2026-10-08T04:31:00.000Z")
    final = snapshot_at(watcher, None)
    rendered = render(tmp_path, initial, frames=[{"event": "snapshot", **final}])
    assert capsules_of(rendered)["fake builder"]["last"] == "Second hi back to fake-session-manager"


def test_session_removed_drops_the_capsule(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, None), frames=[{"event": "session_removed", "at": "2026-10-08T05:00:00.000Z", "pid": 33993}])
    assert list(capsules_of(rendered)) == ["fake manager"]
    assert rendered["count"] == "1 sessions, 1 identified, 0 working"


def test_unidentified_session_and_long_last_line(tmp_path):
    long_text = "x" * 120
    snapshot = {"generated_at": "t", "messages": [], "sessions": [
        {"pid": 7, "name": "nameless-7", "role": None, "label": None, "cwd": "/home/user/other", "status": "IDLE", "inbox": 3, "last_text": long_text, "watching": ["someone"], "socket": "uds:/tmp/cc-socks/7.sock"}]}
    rendered = render(tmp_path, snapshot)
    capsule = capsules_of(rendered)["nameless-7"]
    assert "incomplete" in capsule["className"]
    assert capsule["badge"] == "3"
    assert len(capsule["last"]) == 90 and capsule["last"].endswith("…") and capsule["lastTitle"] == long_text
    assert capsule["watching"] == "👁 watching someone"
    assert rendered["count"] == "1 sessions, 0 identified, 0 working"


def test_empty_state_and_reconnecting_indicator(tmp_path):
    rendered = render(tmp_path, {"generated_at": None, "sessions": [], "messages": []}, open_stream=False, error=True)
    assert rendered["rows"] == [{"empty": "No sessions discovered yet"}]
    assert rendered["count"] == ""
    assert (rendered["link"], rendered["linkClass"]) == ("reconnecting", "off")


FIRST_LABEL = "second hello to fake-session-buil…"
REPLY_LABEL = "Second hi back to fake-session-ma…"


def test_frame_2_pending_connector_and_watch_line(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:10.500Z"))
    assert lines_by_class(rendered) == ["connector PENDING", "watch"]
    assert tag_texts(rendered) == [("tag PENDING", f"… {FIRST_LABEL}")]
    assert rendered["tags"][0]["title"].startswith("PENDING\n")
    assert rendered["tags"][0]["clickable"] is True
    pending, watch = sorted(rendered["lines"], key=lambda l: l["class"])
    assert pending["x1"] < pending["x2"] and watch["x1"] < watch["x2"]
    assert (pending["y1"], pending["y2"]) != (watch["y1"], watch["y2"])


def test_frame_3_in_inbox_connector(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:11.000Z"))
    assert lines_by_class(rendered) == ["connector IN_INBOX", "watch"]
    assert tag_texts(rendered) == [("tag IN_INBOX", f"✓ {FIRST_LABEL}")]
    assert capsules_of(rendered)["fake builder"]["badge"] == "1"


def test_frame_4_read_connector_shows_body_until_sender_result_merges(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:11.200Z"))
    assert lines_by_class(rendered) == ["connector READ", "watch"]
    assert tag_texts(rendered) == [("tag READ", "✓✓ Hi again from fake-session-manage…")]
    merged = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:11.300Z"))
    assert tag_texts(merged) == [("tag READ", f"✓✓ {FIRST_LABEL}")]


def test_frames_5_to_7_reply_connector_in_both_directions(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:17.700Z"))
    assert lines_by_class(rendered) == ["connector READ", "connector READ", "watch"]
    assert sorted(tag_texts(rendered)) == sorted([("tag READ", f"✓✓ {FIRST_LABEL}"), ("tag READ", "✓✓ Hi again from fake-session-builde…")])
    merged = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:17.900Z"))
    assert sorted(tag_texts(merged)) == sorted([("tag READ", f"✓✓ {FIRST_LABEL}"), ("tag READ", f"✓✓ {REPLY_LABEL}")])
    first, second = [l for l in rendered["lines"] if l["class"] == "connector READ"]
    assert (first["x1"] < first["x2"]) != (second["x1"] < second["x2"])
    assert first["y1"] != second["y1"]
    manager, builder = capsules_of(rendered)["fake manager"], capsules_of(rendered)["fake builder"]
    assert manager["pill"] == "Working" and builder["pill"] == "Working"


def test_frame_8_idle_notice_appears_on_the_stream_and_expires(watcher, tmp_path):
    frozen = snapshot_at(watcher, "2026-10-08T04:31:20.100Z")
    assert lines_by_class(render(tmp_path, frozen)) == ["connector READ", "connector READ", "watch"]
    model = registered_model(watcher)
    rest = replay_until(watcher, model, None, after="2026-10-08T04:31:20.100Z")
    assert any(c["event"] == "message" and c["kind"] == "idle_notice" for c in rest)
    shown = render(tmp_path, frozen, frames=rest)
    assert lines_by_class(shown) == ["connector READ", "connector READ", "connector idle_notice"]
    assert ("tag idle_notice", "fake-session-builder is idle") in tag_texts(shown)
    assert capsules_of(shown)["fake manager"]["watching"] == ""
    expired = render(tmp_path, frozen, frames=rest, advance_ms=4000)
    assert lines_by_class(expired) == ["connector READ", "connector READ"]
    assert all(tag["class"] != "tag idle_notice" for tag in expired["tags"])


def test_frame_9_final_snapshot_has_no_notice_or_watch(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, None))
    assert lines_by_class(rendered) == ["connector READ", "connector READ"]
    assert all(tag["class"] == "tag READ" for tag in rendered["tags"])


def test_snapshot_loaded_within_notice_lifetime_shows_the_notice_once(watcher, tmp_path):
    recent = snapshot_at(watcher, None)
    recent["generated_at"] = "2026-10-08T04:31:22.000Z"
    rendered = render(tmp_path, recent)
    assert "connector idle_notice" in lines_by_class(rendered)
    later = dict(recent, generated_at="2026-10-08T04:32:00.000Z")
    assert "connector idle_notice" not in lines_by_class(render(tmp_path, later))


def test_clicking_a_tag_opens_the_panel_with_the_pair_history(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, None), click_tag=0)
    assert rendered["panel"]["open"] is True
    assert rendered["panel"]["title"] in ("fake manager → fake builder (1)", "fake builder → fake manager (1)")
    assert len(rendered["panel"]["entries"]) == 1
    stage, summary, body, times = rendered["panel"]["entries"][0]
    assert stage.startswith("✓✓ READ")
    assert summary in ("second hello to fake-session-builder", "Second hi back to fake-session-manager")
    assert times.startswith("sent ")


def test_failed_message_and_unresolved_target_by_name(tmp_path):
    sessions = [
        {"pid": 1, "name": "alpha", "role": "r", "label": "alpha", "cwd": "/x", "status": "IDLE", "inbox": 0, "last_text": None, "watching": [], "socket": "s"},
        {"pid": 2, "name": "beta", "role": "r", "label": "beta", "cwd": "/x", "status": "IDLE", "inbox": 0, "last_text": None, "watching": [], "socket": "s"},
    ]
    messages = [
        {"key": "pending:t1", "pending_key": "pending:t1", "msg_id": None, "kind": "message", "from_pid": 1, "to_pid": None, "to": "beta [ab12]", "summary": "will fail", "body": "b", "stage": "FAILED", "reason": "Not sent: refused", "sent_at": "2026-10-08T04:31:10.000Z", "accepted_at": "2026-10-08T04:31:10.500Z", "enqueued_at": None, "read_at": None, "notify_when_idle": False, "tool_use_id": "t1"},
        {"key": "pending:t2", "pending_key": "pending:t2", "msg_id": None, "kind": "message", "from_pid": 1, "to_pid": None, "to": "nobody", "summary": "lost", "body": "b", "stage": "PENDING", "reason": None, "sent_at": "2026-10-08T04:31:11.000Z", "accepted_at": None, "enqueued_at": None, "read_at": None, "notify_when_idle": False, "tool_use_id": "t2"},
    ]
    rendered = render(tmp_path, {"generated_at": "2026-10-08T04:31:12.000Z", "sessions": sessions, "messages": messages})
    assert lines_by_class(rendered) == ["connector FAILED"]
    assert tag_texts(rendered) == [("tag FAILED", "✗ will fail")]
    assert rendered["tags"][0]["title"].startswith("FAILED: Not sent: refused")
