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


def replay_until(watcher, model, until):
    tailer = watcher.TranscriptTailer(FIXTURES[0][1])
    changes = []
    for timestamp, _index, pid, line in watcher.entries_in_time_order(FIXTURES):
        if until and timestamp and timestamp > until:
            break
        entry = tailer.parse_line(line)
        if entry is not None:
            changes += model.apply(pid, entry)
    return changes


def render(tmp_path, snapshot, frames=(), open_stream=True, error=False):
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"snapshot": snapshot, "frames": list(frames), "open": open_stream, "error": error}))
    result = subprocess.run(["node", str(HARNESS), str(PAGE), str(input_path)], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def capsules_of(rendered):
    return {c["label"]: c for row in rendered["rows"] for c in row["capsules"]}


def snapshot_at(watcher, until):
    model = registered_model(watcher)
    replay_until(watcher, model, until)
    return {"generated_at": "2026-10-08T04:31:00.000Z", **model.snapshot()}


def test_frame_1_both_idle_and_empty(watcher, tmp_path):
    rendered = render(tmp_path, snapshot_at(watcher, "2026-10-08T04:31:00.000Z"))
    assert rendered["count"] == "2 sessions, 2 identified, 0 working"
    assert rendered["link"] == "live"
    assert rendered["eventsUrl"] == "./events"
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
