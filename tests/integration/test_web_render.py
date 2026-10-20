import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import FIXTURES_DIR, REPO_ROOT
from fixtures.viz.ten_sessions import LONG_DESCRIPTION, PIDS, seven_sessions_round, six_sessions_round, ten_sessions_round

PAGE = REPO_ROOT / "viz" / "web.html"
HARNESS = Path(__file__).resolve().parent.parent / "page" / "render_web.mjs"
FIXTURES = [(32813, str(FIXTURES_DIR / "viz" / "round_trip_manager_32813_33993.jsonl")), (33993, str(FIXTURES_DIR / "viz" / "round_trip_builder_32813_33993.jsonl"))]
CWD = "/home/user/path_finder/fake_session"
REGISTERED_AT = "2026-10-08T04:31:00.000Z"
START = "2026-10-08T04:31:10.300Z"
FIRST_SUMMARY = "second hello to fake-session-builder"
REPLY_SUMMARY = "Second hi back to fake-session-manager"
FIRST_BODY = "Hi again from fake-session-manager. Please reply with a hi back when you see this."
REPLY_BODY_START = "Hi again from fake-session-builder"
MANAGER_TEXT_START = "The hello is in `fake-session-builder`'s inbox."
MANAGER_REPLY_TEXT_START = "The reply came back from `fake-session-builder`"
PENDING_STROKE, OK_STROKE, FAILED_STROKE = "#8a8a8a", "#4ad17a", "#ff6b6b"
LABEL_CHAR_PX, LABEL_HEIGHT, LABEL_MAX_WIDTH = 6.3, 30, 170
COMPACT_NODE_HEIGHT = 24
NODE_BASE_HEIGHT, NODE_CHAR_PX, NODE_LINE_PX = 62, 5.6, 15
TEN_WALL = "2026-10-20T13:00:20.000Z"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is needed to run the page script")


def at(seconds):
    return f"2026-10-08T04:31:{seconds}Z"


def registered_model(watcher):
    model = watcher.StateModel()
    model.register_session({"pid": 32813, "name": "fake-session-manager", "role": "fake session manager", "label": "fake manager", "cwd": CWD})
    model.register_session({"pid": 33993, "name": "fake-session-builder", "role": "fake-session-builder", "label": "fake builder", "cwd": CWD})
    for pid in (32813, 33993):
        model.note_source(pid, REGISTERED_AT, watcher.REGISTRY_SOURCE)
    return model


def timed_changes(watcher):
    model = registered_model(watcher)
    tailer = watcher.TranscriptTailer(FIXTURES[0][1])
    timed = []
    for timestamp, _index, pid, line in watcher.entries_in_time_order(FIXTURES):
        entry = tailer.parse_line(line)
        if entry is None:
            continue
        timed += [(timestamp or "", change) for change in model.apply(pid, entry)]
    return timed


def frames_between(timed, after, until):
    return [change for timestamp, change in timed if after < timestamp <= (until or "9")]


def snapshot_at(watcher, until):
    model = registered_model(watcher)
    tailer = watcher.TranscriptTailer(FIXTURES[0][1])
    for timestamp, _index, pid, line in watcher.entries_in_time_order(FIXTURES):
        if timestamp and timestamp > until:
            break
        entry = tailer.parse_line(line)
        if entry is not None:
            model.apply(pid, entry)
    return {"generated_at": until, **model.snapshot()}


def render(tmp_path, snapshot, steps, wall_start=START, local_storage=None, storage_throws=False):
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"snapshot": snapshot, "steps": steps, "wallStart": wall_start, "localStorage": local_storage or {}, "storageThrows": storage_throws}))
    result = subprocess.run(["node", str(HARNESS), str(PAGE), str(input_path)], capture_output=True, text=True, check=True)
    return {step["name"]: step["view"] for step in json.loads(result.stdout)}


def nodes_of(view):
    return {node["name"]: node for node in view["nodes"]}


def chips_of(view):
    return {chip["pid"]: chip for chip in view["chips"]}


def rows_of(view):
    return [(row["name"], row["status"], row["activity"]) for row in view["rows"]]


def pills(node):
    return [text for class_name, text in node["pills"] if class_name.startswith("pill")]


def only_path(view):
    assert len(view["paths"]) == 1, view["paths"]
    return view["paths"][0]


def only_label(view):
    assert len(view["labels"]) == 1, view["labels"]
    return view["labels"][0]


def label_rect(label):
    width = min(LABEL_MAX_WIDTH, max(len(label["summary"]), len(label["stage"][1])) * LABEL_CHAR_PX + 14)
    return (label["left"] - width / 2, label["top"] - LABEL_HEIGHT / 2, label["left"] + width / 2, label["top"] + LABEL_HEIGHT / 2)


def estimated_node_height(line, width):
    chars_per_line = max(8, math.floor((width - 16) / NODE_CHAR_PX))
    lines = math.ceil(len(line) / chars_per_line) if line else 1
    return NODE_BASE_HEIGHT + (lines - 1) * NODE_LINE_PX


def node_rect(node):
    left, top, width = (float(node[key][:-2]) for key in ("left", "top", "width"))
    height = float(node["height"][:-2]) if node["height"].endswith("px") else estimated_node_height(node["line"] or "", width)
    return (left, top, left + width, top + height)


def rects_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def curve_points(d, samples=16):
    numbers = [float(x) for x in re.findall(r"-?\d+\.?\d*", d)]
    start, control, end = numbers[0:2], numbers[2:4], numbers[4:6]
    points = []
    for i in range(samples + 1):
        t = i / samples
        u = 1 - t
        points.append((u * u * start[0] + 2 * u * t * control[0] + t * t * end[0], u * u * start[1] + 2 * u * t * control[1] + t * t * end[1]))
    return points


def control_y(d):
    return float(re.findall(r"-?\d+\.?\d*", d)[3])


def point_in(point, rect):
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


@pytest.fixture
def round_views(watcher, tmp_path):
    timed = timed_changes(watcher)
    cut = lambda name, after, until, **extra: {"name": name, "frames": frames_between(timed, at(after), at(until)), **extra}
    steps = [
        {"name": "start"},
        cut("send", "10.300", "10.500"),
        cut("enqueue", "10.500", "11.000"),
        cut("read", "11.000", "11.300"),
        {"name": "flash gone", "advanceMs": 3500},
        cut("manager turn end", "11.300", "13.500"),
        cut("reply pending", "13.500", "17.000"),
        cut("reply in inbox", "17.000", "17.600"),
        cut("reply read", "17.600", "17.700"),
        cut("idle notice", "17.700", "21.100"),
        {"name": "pulse gone", "advanceMs": 1500},
        {"name": "end", "frames": frames_between(timed, at("21.100"), None), "advanceMs": 9000},
        {"name": "row pick", "clickRow": 33993},
        {"name": "row unpick", "clickRow": 33993},
        {"name": "eleven minutes later", "advanceMs": 660000},
    ]
    assert all(step["frames"] for step in steps if "frames" in step)
    return render(tmp_path, snapshot_at(watcher, START), steps)


def test_start_is_a_quiet_pod_with_idle_rows(round_views):
    view = round_views["start"]
    assert view["title"] == "fake_session · 2 sessions · 0 working · 0 in flight"
    assert (view["link"], view["eventsUrl"], view["pod"], view["viewBox"], view["graphHeight"]) == ("live", "./events", True, "0 0 356 150", "150px")
    assert 250 in view["intervals"]
    assert view["caption"][0] == "registry"
    manager, builder = nodes_of(view)["fake manager"], nodes_of(view)["fake builder"]
    assert (manager["left"], builder["left"], manager["top"]) == ("20px", "220px", "59px")
    for node in (manager, builder):
        assert node["className"] == "node" and pills(node) == ["Idle"] and node["mail"] is None and node["last"] == "" and node["line"] == "" and node["eye"] is None
    assert view["paths"] == [] and view["labels"] == []
    assert [(chip["pid"], chip["className"], chip["text"], chip["count"]) for chip in view["chips"]] == [(32813, "chip", "fake manager", None), (33993, "chip", "fake builder", None)]
    assert rows_of(view) == [("fake manager", "Idle", ""), ("fake builder", "Idle", "")]
    assert all(row["activityTitle"] == "" for row in view["rows"])
    assert all(row["className"] == "arow" and row["pill"] == ["pill idle", "Idle"] and row["clickable"] for row in view["rows"])


def test_send_shows_pending_arrow_and_sending_row_first(round_views):
    view = round_views["send"]
    assert view["title"] == "fake_session · 2 sessions · 1 working · 1 in flight"
    assert view["caption"] == ["assistant → tool_use SendMessage", "fake manager → fake builder"]
    manager, builder = nodes_of(view)["fake manager"], nodes_of(view)["fake builder"]
    assert manager["className"] == "node work hot" and pills(manager) == ["Sending"]
    assert (manager["last"], manager["lastTitle"], manager["eye"]) == ("waiting on fake builder", "waiting on fake builder", None)
    assert builder["className"] == "node hot" and pills(builder) == ["Idle"] and builder["mail"] is None and builder["last"] == ""
    assert (manager["top"], builder["top"]) == ("59px", "66.5px")
    path = only_path(view)
    assert (path["key"], path["stage"], path["stroke"], path["marker"], path["width"], path["opacity"], path["className"]) == ("32813>33993", "PENDING", PENDING_STROKE, "url(#mp)", "2.4", "1", "")
    label = only_label(view)
    assert (label["key"], label["summary"], label["stage"], label["opacity"], label["clear"]) == ("32813>33993", FIRST_SUMMARY, ["pend", "Pending"], "1", "1")
    assert label["title"].startswith("PENDING\n" + FIRST_BODY)
    assert chips_of(view)[32813]["className"] == "chip on" and chips_of(view)[32813]["dotClass"] == "dot work"
    assert rows_of(view) == [("fake manager", "Sending", "waiting on fake builder"), ("fake builder", "Idle", "")]
    manager_row = view["rows"][0]
    assert manager_row["className"] == "arow work" and manager_row["pill"] == ["pill work", "Sending"] and manager_row["dotClass"] == "dot work"
    assert manager_row["activityTitle"] == "waiting on fake builder"


def test_enqueue_shows_the_envelope_on_the_receiver(round_views):
    view = round_views["enqueue"]
    assert view["caption"] == ["queue-operation · enqueue", "fake manager → fake builder"]
    manager, builder = nodes_of(view)["fake manager"], nodes_of(view)["fake builder"]
    assert pills(manager) == ["Working"] and manager["mail"] is None
    assert pills(builder) == ["Idle"] and builder["pills"] == [["pill idle", "Idle"], ["mail", "✉ 1"]]
    assert (builder["mail"], builder["mailTitle"]) == ("✉ 1", "1 queued message")
    path = only_path(view)
    assert (path["stage"], path["stroke"], path["marker"]) == ("IN_INBOX", OK_STROKE, "url(#mg)")
    assert only_label(view)["stage"] == ["ok", "✓ In inbox"]
    assert (chips_of(view)[33993]["className"], chips_of(view)[33993]["count"]) == ("chip hot", "1")
    assert rows_of(view) == [("fake manager", "Working", "waiting on fake builder"), ("fake builder", "Idle", "")]


def test_read_clears_the_envelope_flashes_and_sets_the_builder_row_working(round_views):
    view = round_views["read"]
    assert view["title"] == "fake_session · 2 sessions · 2 working · 0 in flight"
    builder = nodes_of(view)["fake builder"]
    assert pills(builder) == ["Working"] and builder["mail"] is None and builder["className"] == "node work"
    assert (builder["last"], builder["lastTitle"]) == ("working", "working")
    path = only_path(view)
    assert (path["stage"], path["stroke"]) == ("READ", OK_STROKE) and 0.9 < float(path["opacity"]) < 1
    assert only_label(view)["stage"] == ["ok", "✓✓ Read"]
    assert chips_of(view)[33993]["className"] == "chip on" and chips_of(view)[33993]["count"] is None
    assert rows_of(view) == [("fake builder", "Working", "working"), ("fake manager", "Working", "waiting on fake builder")]
    assert view["rows"][0]["activityTitle"] == "working"
    faded = round_views["flash gone"]
    assert (only_path(faded)["stage"], only_path(faded)["opacity"], only_path(faded)["width"]) == ("READ", "0.550", "2.4")
    assert (only_label(faded)["opacity"], only_label(faded)["clear"], only_label(faded)["stage"]) == ("0.550", "1", ["ok", "✓✓ Read"])
    ended = round_views["manager turn end"]
    manager_row = ended["rows"][1]
    assert rows_of(ended)[0] == ("fake builder", "Working", "working")
    assert (manager_row["name"], manager_row["status"], manager_row["className"]) == ("fake manager", "Idle", "arow")
    assert (manager_row["activity"], manager_row["activityTitle"]) == ("waiting on fake builder", "waiting on fake builder")
    assert nodes_of(ended)["fake manager"]["last"] == "waiting on fake builder" and nodes_of(ended)["fake manager"]["className"] == "node"


def test_reply_shows_the_envelope_on_the_manager_and_the_rows_follow(round_views):
    pending = round_views["reply pending"]
    builder = nodes_of(pending)["fake builder"]
    assert pills(builder) == ["Sending"] and builder["last"] == "waiting on fake manager" and builder["className"] == "node work hot"
    paths = {path["key"]: path for path in pending["paths"]}
    assert set(paths) == {"32813>33993", "33993>32813"}
    assert (paths["33993>32813"]["stage"], paths["33993>32813"]["stroke"], paths["33993>32813"]["opacity"], paths["33993>32813"]["width"]) == ("PENDING", PENDING_STROKE, "1", "2.4")
    assert (paths["32813>33993"]["stage"], paths["32813>33993"]["opacity"], paths["32813>33993"]["width"]) == ("READ", "0.550", "1.5")
    labels = {label["key"]: label for label in pending["labels"]}
    assert control_y(paths["33993>32813"]["d"]) < 57 < 138 < control_y(paths["32813>33993"]["d"])
    assert labels["33993>32813"]["top"] < 60 < 150 < labels["32813>33993"]["top"] and pending["graphHeight"] == "206px" and pending["viewBox"] == "0 0 356 206"
    assert label_rect(labels["32813>33993"])[3] <= 206
    assert rows_of(pending)[0] == ("fake builder", "Sending", "waiting on fake manager")
    assert rows_of(pending)[1] == ("fake manager", "Idle", "waiting on fake builder")
    inbox = round_views["reply in inbox"]
    assert only_path(inbox)["stage"] == "IN_INBOX"
    manager = nodes_of(inbox)["fake manager"]
    assert pills(manager) == ["Idle"] and manager["pills"] == [["pill idle", "Idle"], ["mail", "✉ 1"]]
    assert (chips_of(inbox)[32813]["className"], chips_of(inbox)[32813]["count"]) == ("chip hot", "1")
    read = round_views["reply read"]
    assert only_path(read)["stage"] == "READ"
    manager = nodes_of(read)["fake manager"]
    assert pills(manager) == ["Working"] and manager["mail"] is None and manager["last"] == "waiting on fake builder"
    assert nodes_of(read)["fake builder"]["last"] == REPLY_SUMMARY
    assert rows_of(read)[0] == ("fake manager", "Working", "waiting on fake builder")
    assert rows_of(read)[1] == ("fake builder", "Working", REPLY_SUMMARY)
    assert read["rows"][1]["activityTitle"] == f"{REPLY_SUMMARY}\n{at('16.750')}"


def test_idle_notice_pulses_the_eye_without_an_arrow(round_views):
    view = round_views["idle notice"]
    assert view["caption"] == ["user · cross-session idle notice", "fake builder → fake manager"]
    manager = nodes_of(view)["fake manager"]
    assert manager["last"] == "👁idle notice" and manager["eye"] == "eye pulse"
    assert (only_path(view)["key"], only_path(view)["stage"], only_path(view)["opacity"]) == ("33993>32813", "READ", "0.550") and only_label(view)["opacity"] == "0.550"
    assert nodes_of(view)["fake builder"]["last"] == "" and rows_of(view)[1] == ("fake builder", "Idle", "")
    assert rows_of(view)[0][:2] == ("fake manager", "Working") and rows_of(view)[0][2].startswith(MANAGER_REPLY_TEXT_START)
    after = round_views["pulse gone"]
    assert nodes_of(after)["fake manager"]["eye"] is None
    assert nodes_of(after)["fake manager"]["last"].startswith(MANAGER_REPLY_TEXT_START) and nodes_of(after)["fake manager"]["className"] == "node work"


def test_round_ends_with_idle_rows_ordered_by_last_change(round_views):
    end = round_views["end"]
    assert end["title"] == "fake_session · 2 sessions · 0 working · 0 in flight"
    assert (only_path(end)["key"], only_path(end)["stage"], only_path(end)["opacity"]) == ("33993>32813", "READ", "0.550")
    assert [pills(node) for node in end["nodes"]] == [["Idle"], ["Idle"]]
    assert rows_of(end) == [("fake manager", "Idle", ""), ("fake builder", "Idle", "")]
    assert [node["last"] for node in end["nodes"]] == ["", ""] and end["graphHeight"] == "150px"
    picked = round_views["row pick"]
    assert picked["rows"][1]["className"] == "arow picked" and nodes_of(picked)["fake builder"]["className"] == "node picked"
    assert chips_of(picked)[33993]["className"] == "chip picked"
    assert round_views["row unpick"]["rows"][1]["className"] == "arow"
    later = round_views["eleven minutes later"]
    assert [node["pid"] for node in later["nodes"]] == [32813, 33993] and later["paths"] == [] and later["labels"] == []
    assert [row["activity"] for row in later["rows"]] == [row["activity"] for row in end["rows"]]


def test_idle_rows_stay_blank_however_long_the_session_has_been_idle(tmp_path):
    sessions = [session(1, "a", idle_since="2026-10-20T11:50:00.000Z", activity="Edit old.py"), session(2, "b", status="WORKING")]
    views = render(tmp_path, synthetic(sessions), [{"name": "now"}, {"name": "later", "advanceMs": 5 * 60 * 1000}], wall_start=TEN_START)
    assert rows_of(views["now"]) == [("b", "Working", "working"), ("a", "Idle", "")]
    assert rows_of(views["later"]) == [("b", "Working", "working"), ("a", "Idle", "")]
    assert {node["name"]: node["last"] for node in views["later"]["nodes"]} == {"a": "", "b": "working"}


def test_change_stream_matches_the_frozen_snapshot_at_each_cut(watcher, tmp_path):
    timed = timed_changes(watcher)
    for until in ("10.500", "11.000", "17.600", "21.060"):
        streamed = render(tmp_path, snapshot_at(watcher, START), [{"name": "s", "frames": frames_between(timed, START, at(until))}], wall_start=at(until))["s"]
        frozen = render(tmp_path, snapshot_at(watcher, at(until)), [{"name": "s"}], wall_start=at(until))["s"]
        for part in ("nodes", "paths", "labels", "chips", "rows", "title", "pod", "graphHeight"):
            assert streamed[part] == frozen[part], (until, part)


def test_pod_labels_stay_inside_the_graph(watcher, tmp_path):
    for until in ("10.500", "11.000", "17.000", "17.600", "17.700"):
        view = render(tmp_path, snapshot_at(watcher, at(until)), [{"name": "s"}], wall_start=at(until))["s"]
        height = float(view["viewBox"].split()[3])
        for label in view["labels"]:
            rect = label_rect(label)
            assert rect[1] >= 0 and rect[3] <= height, (until, label["key"], rect)
            for node in view["nodes"]:
                assert not rects_overlap(rect, node_rect(node)), (until, label["key"], node["name"])


def test_picking_a_chip_or_node_thickens_its_arrows_and_toggles_off(watcher, tmp_path):
    timed = timed_changes(watcher)
    steps = [
        {"name": "send", "frames": frames_between(timed, START, at("10.500"))},
        {"name": "pick chip", "clickChip": 32813},
        {"name": "unpick chip", "clickChip": 32813},
        {"name": "hover path", "hoverPath": "32813>33993"},
        {"name": "leave path", "leavePath": "32813>33993"},
        {"name": "pick node", "clickNode": 33993},
        {"name": "error", "error": True},
        {"name": "reopen", "reopen": True},
    ]
    views = render(tmp_path, snapshot_at(watcher, START), steps)
    picked = views["pick chip"]
    assert chips_of(picked)[32813]["className"] == "chip on picked"
    assert set(nodes_of(picked)["fake manager"]["className"].split()) == {"node", "work", "hot", "picked"}
    assert (only_path(picked)["width"], only_path(picked)["className"]) == ("2.4", "")
    assert views["pick chip"]["rows"][0]["className"] == "arow work picked"
    unpicked = views["unpick chip"]
    assert chips_of(unpicked)[32813]["className"] == "chip on" and nodes_of(unpicked)["fake manager"]["className"] == "node work hot"
    assert set(nodes_of(views["pick node"])["fake builder"]["className"].split()) == {"node", "hot", "picked"}
    assert only_label(views["hover path"])["zIndex"] == "4" and only_label(views["leave path"])["zIndex"] == "2"
    assert (views["error"]["link"], views["error"]["linkClass"]) == ("reconnecting", "off")
    assert (views["reopen"]["link"], views["reopen"]["linkClass"]) == ("live", "")


def session(pid, label, cwd="/home/user/path_finder", role="r", status="IDLE", inbox=0, watching=(), last_seen_at="2026-10-20T12:00:05.000Z", activity=None, idle_since=None, waiting_on=()):
    return {"pid": pid, "name": label, "role": role, "label": label, "cwd": cwd, "status": status, "inbox": inbox, "last_text": None, "watching": list(watching), "socket": f"uds:/tmp/cc-socks/{pid}.sock",
        "last_seen_at": last_seen_at, "activity": activity, "activity_at": last_seen_at if activity else None, "idle_since": idle_since, "last_assistant_text": None, "waiting_on": list(waiting_on)}


def message(key, from_pid, to_pid, stage, summary, sent_at, body=None, reason=None, accepted_at=None, enqueued_at=None, read_at=None, kind="message"):
    return {"key": key, "pending_key": None, "msg_id": key, "kind": kind, "from_pid": from_pid, "to_pid": to_pid, "to": f"uds:/tmp/cc-socks/{to_pid}.sock", "summary": summary, "body": body or f"{summary} body line\nsecond line",
        "stage": stage, "reason": reason, "sent_at": sent_at, "accepted_at": accepted_at, "enqueued_at": enqueued_at, "read_at": read_at, "notify_when_idle": False, "tool_use_id": key}


def source(pid, label, seq, at="2026-10-20T12:00:05.000Z"):
    return {"pid": pid, "at": at, "source": label, "seq": seq}


TEN_START = "2026-10-20T12:00:05.000Z"


def synthetic(sessions, messages=(), sources=(), generated_at=TEN_START):
    return {"generated_at": generated_at, "sessions": list(sessions), "messages": list(messages), "sources": list(sources)}


def test_failed_arrow_stays_past_the_horizon_until_resolved(tmp_path):
    sessions = [session(1, "a"), session(2, "b"), session(3, "c")]
    old_failure = message("m3", 1, 2, "FAILED", "old failure", "2026-10-20T11:30:00.000Z", reason="Not sent: refused", accepted_at="2026-10-20T11:30:01.000Z")
    resend = message("m4", 1, 2, "IN_INBOX", "resend", "2026-10-20T12:00:04.000Z", enqueued_at="2026-10-20T12:00:05.000Z")
    resend_frame = {"event": "message", "at": "2026-10-20T12:00:05.000Z", "source": "queue-operation · enqueue", "source_pid": 2, **resend}
    views = render(tmp_path, synthetic(sessions, [old_failure]), [{"name": "failed"}, {"name": "resolved", "frames": [resend_frame]}], wall_start=TEN_START)
    failed = views["failed"]
    assert [node["pid"] for node in failed["nodes"]] == [1, 2, 3]
    assert (only_path(failed)["stage"], only_path(failed)["stroke"], only_path(failed)["marker"]) == ("FAILED", FAILED_STROKE, "url(#mr)")
    assert only_label(failed)["stage"] == ["fail", "✗ Failed"] and only_label(failed)["title"].startswith("FAILED: Not sent: refused")
    assert chips_of(failed)[3]["className"] == "chip"
    resolved = views["resolved"]
    assert only_path(resolved)["stage"] == "IN_INBOX" and only_label(resolved)["summary"] == "resend"


def test_every_session_is_a_node_idle_or_not_and_stays_after_ten_minutes(tmp_path):
    sessions = [session(1, "a"), session(2, "b", inbox=1), session(3, "c", idle_since="2026-10-20T10:00:00.000Z"), session(4, "d", status="WORKING")]
    recent = [message("m1", 1, 2, "IN_INBOX", "a to b", "2026-10-20T11:59:00.000Z", enqueued_at="2026-10-20T11:59:30.000Z")]
    views = render(tmp_path, synthetic(sessions, recent), [{"name": "now"}, {"name": "later", "advanceMs": 11 * 60 * 1000}, {"name": "joined", "frames": [{"event": "session", "at": "2026-10-20T12:12:00.000Z", "source": "registry", "source_pid": 5, **session(5, "e")}]}], wall_start=TEN_START)
    now = views["now"]
    assert [node["pid"] for node in now["nodes"]] == [1, 2, 3, 4] and now["pod"] is False
    assert [(chip["pid"], chip["className"], chip["title"]) for chip in now["chips"]] == [(1, "chip", "a · pid 1"), (2, "chip hot", "b · pid 2"), (3, "chip", "c · pid 3"), (4, "chip on", "d · pid 4")]
    assert len(now["paths"]) == 1 and now["title"] == "path_finder · 4 sessions · 1 working · 1 in flight"
    assert [(node["name"], pills(node), node["last"]) for node in now["nodes"]] == [("a", ["Idle"], ""), ("b", ["Idle"], ""), ("c", ["Idle"], ""), ("d", ["Working"], "working")]
    later = views["later"]
    assert [node["pid"] for node in later["nodes"]] == [1, 2, 3, 4] and [chip["pid"] for chip in later["chips"]] == [1, 2, 3, 4]
    assert later["paths"] == [] and later["title"] == "path_finder · 4 sessions · 1 working · 0 in flight" and len(later["rows"]) == 4
    assert [node["pid"] for node in views["joined"]["nodes"]] == [1, 2, 3, 4, 5]


def test_session_removed_leaves_the_ring_and_unidentified_nodes_are_dashed(tmp_path):
    sessions = [session(1, "a", watching=[3], waiting_on=[3]), session(2, "b"), session(3, "c", role=None)]
    removed = {"event": "session_removed", "at": "2026-10-20T12:00:06.000Z", "source": "registry", "source_pid": 2, "pid": 2}
    views = render(tmp_path, synthetic(sessions, sources=[source(2, "registry", 1)]), [{"name": "now"}, {"name": "removed", "frames": [removed]}], wall_start=TEN_START)
    view = views["now"]
    assert [node["pid"] for node in view["nodes"]] == [1, 2, 3]
    assert [node["pid"] for node in views["removed"]["nodes"]] == [1, 3] and [chip["pid"] for chip in views["removed"]["chips"]] == [1, 3]
    assert nodes_of(view)["a"]["last"] == "waiting on c" and nodes_of(view)["a"]["eye"] is None
    assert nodes_of(view)["c"]["className"] == "node incomplete"
    assert view["caption"] == ["registry", "b"]
    assert view["title"] == "path_finder · 3 sessions · 0 working · 0 in flight"


def test_empty_snapshot_and_snapshot_event_on_the_stream(tmp_path):
    replacement = {"event": "snapshot", **synthetic([session(5, "only")], sources=[source(5, "registry", 1)])}
    views = render(tmp_path, synthetic([]), [{"name": "empty"}, {"name": "replaced", "frames": [replacement]}], wall_start=TEN_START)
    assert views["empty"]["title"] == "No sessions discovered yet" and views["empty"]["quiet"] == "No sessions discovered yet"
    assert views["empty"]["nodes"] == [] and views["empty"]["chips"] == []
    assert views["empty"]["rows"] == [{"className": "quiet-rows", "text": "No sessions discovered yet"}]
    assert [node["name"] for node in views["replaced"]["nodes"]] == ["only"] and views["replaced"]["quiet"] is None
    assert rows_of(views["replaced"]) == [("only", "Idle", "")]


@pytest.fixture
def ten_view(watcher, tmp_path):
    fixtures = ten_sessions_round().write(tmp_path / "ten")
    w = watcher.Watcher(fixtures=fixtures, spec_path=None)
    w.poll_once()
    snapshot = w.snapshot()
    return render(tmp_path, snapshot, [{"name": "ten"}, {"name": "hover hidden", "hoverPath": "901>900"}], wall_start=TEN_WALL)


def test_ten_sessions_rows_envelopes_and_label_visibility(ten_view):
    view = ten_view["ten"]
    assert view["title"] == "10 sessions · 6 working · 8 in flight"
    assert [node["pid"] for node in view["nodes"]] == list(range(900, 910))
    assert all(node["className"].startswith("node compact") and node["height"] == f"{COMPACT_NODE_HEIGHT}px" for node in view["nodes"])
    assert {node["name"]: node["headMail"] for node in view["nodes"] if node["headMail"]} == {"manager": "✉ 1", "viz-builder": "✉ 1", "validator": "✉ 1", "discovery-builder": "✉ 1", "listings-bc": "✉ 2"}
    assert {chip["text"]: chip["count"] for chip in view["chips"] if chip["count"]} == {"manager1": "1", "viz-builder1": "1", "validator1": "1", "discovery-builder1": "1", "listings-bc2": "2"}
    assert rows_of(view) == [
        ("listings-e6", "Working", "waiting on listings-bc"),
        ("tag-analyzer", "Working", "tags done"),
        ("viz-builder", "Working", "waiting on validator, manager"),
        ("fake manager", "Working", "second hello"),
        ("manager", "Working", "waiting on discovery-builder, semantic-scores"),
        ("semantic-scores", "Working", "waiting on listings-bc"),
        ("validator", "Idle", "waiting on viz-builder"),
        ("fake builder", "Idle", ""),
        ("discovery-builder", "Idle", ""),
        ("listings-bc", "Idle", ""),
    ]
    assert view["graphHeight"] == "380px" and view["viewBox"] == "0 0 356 380"
    assert len(view["paths"]) == 10
    stages = {path["key"]: path["stage"] for path in view["paths"]}
    assert stages["902>900"] == "FAILED" and stages["908>906"] == "READ" and stages["904>905"] == "READ" and sum(stage == "IN_INBOX" for stage in stages.values()) == 7
    assert {path["key"]: path["opacity"] for path in view["paths"] if path["stage"] == "READ"} == {"908>906": "0.925", "904>905": "0.550"}
    shown = {label["key"]: label for label in view["labels"] if label["clear"] == "1"}
    hidden = {label["key"]: label for label in view["labels"] if label["clear"] == "0"}
    assert len(shown) + len(hidden) == 10
    assert all(label["opacity"] == "0" for label in hidden.values())
    assert all(label["opacity"] != "0" for label in shown.values())
    assert {key: label["text"] for key, label in shown.items()} == {"908>906": "tags done✓✓ Read", "906>907": "rerun scores✓ In inbox", "900>903": "D4 assigned✓ In inbox", "900>909": "rerun scores✓ In inbox", "902>901": "V6 review: PASS✓ In inbox", "904>905": "second hello✓✓ Read"}
    assert set(hidden) == {"902>900", "901>902", "901>900", "909>907"}
    hovered = {label["key"]: label for label in ten_view["hover hidden"]["labels"]}
    assert hovered["901>900"]["opacity"] == "1" and hovered["901>900"]["zIndex"] == "4"


def test_ten_sessions_shown_labels_do_not_overlap_nodes_or_each_other(ten_view):
    view = ten_view["ten"]
    shown = [label for label in view["labels"] if label["clear"] == "1"]
    node_rects = {node["pid"]: node_rect(node) for node in view["nodes"]}
    for label in shown:
        for pid, rect in node_rects.items():
            assert not rects_overlap(label_rect(label), rect), (label["key"], pid)
    for first in shown:
        for second in shown:
            if first["key"] < second["key"]:
                assert not rects_overlap(label_rect(first), label_rect(second)), (first["key"], second["key"])


def test_ten_sessions_arrows_do_not_pass_through_shown_labels_or_other_nodes(ten_view):
    view = ten_view["ten"]
    shown = {label["key"]: label_rect(label) for label in view["labels"] if label["clear"] == "1"}
    node_rects = {node["pid"]: node_rect(node) for node in view["nodes"]}
    crossings = []
    for path in view["paths"]:
        points = curve_points(path["d"])
        ends = [int(pid) for pid in path["key"].split(">")]
        for key, rect in shown.items():
            if key != path["key"] and any(point_in(point, rect) for point in points):
                crossings.append(("arrow through label", path["key"], key))
        for pid, rect in node_rects.items():
            if pid not in ends and any(point_in(point, rect) for point in points):
                crossings.append(("arrow through node", path["key"], pid))
    assert crossings == []


def task(task_id, state, title, owner="viz-builder", text=None):
    return {"id": task_id, "state": state, "title": title, "text": text or f"{title}. Full text of {task_id}.", "owner": owner}


TASKS = [task("V8", "done", "web window follow-ups"), task("V9", "in_progress", "task panel"), task("D5", "todo", "next discovery step", owner="discovery-builder"), task("D6", "in_progress", "discovery follow-up", owner="discovery-builder")]
TASK_COUNTS = {"done": 1, "in_progress": 2, "todo": 1}


def with_tasks(snapshot, tasks=TASKS, counts=TASK_COUNTS):
    return {**snapshot, "tasks": tasks, "task_counts": counts, "spec_path": "/home/user/path_finder/SPEC.md"}


def test_panel_lists_every_task_with_state_words_and_counts(tmp_path):
    sessions = [session(1, "manager"), session(2, "viz-builder", status="WORKING"), session(3, "validator")]
    view = render(tmp_path, with_tasks(synthetic(sessions)), [{"name": "open"}], wall_start=TEN_START)["open"]
    panel = view["panel"]
    assert panel["collapsed"] is False and panel["counts"] == "1 done · 2 in progress · 1 to do" and panel["chevron"] == "▾"
    assert panel["tab"].startswith("Tasks") and panel["tabTitle"] == "hide the task list"
    assert [(t["id"], t["state"], t["tid"], t["ttitle"], t["tstate"], t["className"]) for t in panel["tasks"]] == [
        ("V8", "done", "V8", "web window follow-ups", "Done", "task done"),
        ("V9", "in_progress", "V9", "task panel", "In progress", "task in_progress"),
        ("D5", "todo", "D5", "next discovery step", "To do", "task todo"),
        ("D6", "in_progress", "D6", "discovery follow-up", "In progress", "task in_progress"),
    ]
    assert [t["owner"] for t in panel["tasks"]] == [None, "viz-builder", None, "discovery-builder"]
    assert panel["tasks"][1]["ownerDot"] == "#3ed6a4" and panel["tasks"][3]["ownerDot"] is None
    assert all(t["full"] == f"{t['ttitle']}. Full text of {t['id']}." and t["clickable"] and t["title"] == "click for the full text" for t in panel["tasks"])
    assert panel["storage"] == {}


def test_in_progress_tasks_highlight_the_live_owner_node_and_row(tmp_path):
    sessions = [session(1, "manager"), session(2, "viz-builder", status="WORKING"), session(3, "validator")]
    messages = [message("m1", 1, 2, "IN_INBOX", "V9 assigned", "2026-10-20T12:00:00.000Z", enqueued_at="2026-10-20T12:00:01.000Z")]
    cleared = {"event": "tasks", "at": "2026-10-20T12:00:06.000Z", "source": "spec", "source_pid": None, "tasks": [task("V9", "done", "task panel")], "task_counts": {"done": 1, "in_progress": 0, "todo": 0}, "spec_path": "/x"}
    views = render(tmp_path, with_tasks(synthetic(sessions, messages)), [{"name": "open"}, {"name": "cleared", "frames": [cleared]}], wall_start=TEN_START)
    view = views["open"]
    builder = nodes_of(view)["viz-builder"]
    assert "tasked" in builder["className"].split() and (builder["badge"], builder["badgeTitle"]) == ("V9", "in progress: V9")
    assert nodes_of(view)["manager"]["badge"] is None and "tasked" not in nodes_of(view)["manager"]["className"]
    rows = {row["pid"]: row for row in view["rows"]}
    assert rows[2]["className"] == "arow work tasked" and rows[2]["badge"] == "V9" and rows[2]["name"] == "viz-builder V9"
    assert rows[1]["className"] == "arow" and rows[1]["badge"] is None
    assert view["panel"]["counts"] == "1 done · 2 in progress · 1 to do"
    after = views["cleared"]
    assert after["panel"]["counts"] == "1 done · 0 in progress · 0 to do"
    assert [(t["id"], t["tstate"]) for t in after["panel"]["tasks"]] == [("V9", "Done")]
    assert nodes_of(after)["viz-builder"]["badge"] is None and "tasked" not in nodes_of(after)["viz-builder"]["className"]
    assert {row["pid"]: row["className"] for row in after["rows"]}[2] == "arow work"


def test_owner_line_falls_back_to_the_owner_name_when_no_session_matches(tmp_path):
    sessions = [session(1, "manager"), session(2, "fake builder")]
    view = render(tmp_path, with_tasks(synthetic(sessions)), [{"name": "open"}], wall_start=TEN_START)["open"]
    assert [t["owner"] for t in view["panel"]["tasks"]] == [None, "viz-builder", None, "discovery-builder"]
    assert all(node["badge"] is None for node in view["nodes"]) and all(row["badge"] is None for row in view["rows"])


def test_owner_matches_on_role_or_label_or_name(tmp_path):
    sessions = [session(1, "a", role="viz-builder"), session(2, "b")]
    sessions[1]["label"] = "discovery-builder"
    view = render(tmp_path, with_tasks(synthetic(sessions)), [{"name": "open"}], wall_start=TEN_START)["open"]
    assert [t["owner"] for t in view["panel"]["tasks"]] == [None, "a", None, "discovery-builder"]
    assert {node["pid"]: node["badge"] for node in view["nodes"]} == {1: "V9", 2: "D6"}


def test_clicking_a_task_expands_its_full_text_and_the_tab_collapses_the_panel(tmp_path):
    steps = [{"name": "open"}, {"name": "expand", "clickTask": "V9"}, {"name": "expand second", "clickTask": "D5"}, {"name": "fold", "clickTask": "V9"}, {"name": "collapse", "clickTab": True}, {"name": "reopen", "clickTab": True}]
    views = render(tmp_path, with_tasks(synthetic([session(1, "a")])), steps, wall_start=TEN_START)
    by_id = lambda name: {t["id"]: t for t in views[name]["panel"]["tasks"]}
    assert by_id("open")["V9"]["className"] == "task in_progress"
    assert by_id("expand")["V9"]["className"] == "task in_progress open" and by_id("expand")["V9"]["title"] == "click to collapse"
    assert by_id("expand")["V9"]["full"] == "task panel. Full text of V9."
    assert by_id("expand second")["D5"]["className"] == "task todo open" and by_id("expand second")["V9"]["className"] == "task in_progress open"
    assert by_id("fold")["V9"]["className"] == "task in_progress" and by_id("fold")["D5"]["className"] == "task todo open"
    collapsed = views["collapse"]["panel"]
    assert collapsed["collapsed"] is True and collapsed["counts"] == "1 done · 2 in progress · 1 to do" and collapsed["chevron"] == "▸"
    assert collapsed["tabTitle"] == "show the task list" and collapsed["storage"] == {"viz-web-panel-collapsed": "1"}
    assert len(collapsed["tasks"]) == 4
    reopened = views["reopen"]["panel"]
    assert reopened["collapsed"] is False and reopened["storage"] == {"viz-web-panel-collapsed": "0"}


def test_panel_remembers_collapse_and_survives_blocked_storage(tmp_path):
    remembered = render(tmp_path, with_tasks(synthetic([session(1, "a")])), [{"name": "open"}], wall_start=TEN_START, local_storage={"viz-web-panel-collapsed": "1"})["open"]
    assert remembered["panel"]["collapsed"] is True and remembered["panel"]["counts"] == "1 done · 2 in progress · 1 to do"
    blocked = render(tmp_path, with_tasks(synthetic([session(1, "a")])), [{"name": "open"}, {"name": "toggle", "clickTab": True}], wall_start=TEN_START, storage_throws=True)
    assert blocked["open"]["panel"]["collapsed"] is False and blocked["toggle"]["panel"]["collapsed"] is True


def test_panel_without_tasks_says_so(tmp_path):
    view = render(tmp_path, synthetic([session(1, "a")]), [{"name": "open"}], wall_start=TEN_START)["open"]
    assert view["panel"]["counts"] == "0 done · 0 in progress · 0 to do"
    assert view["panel"]["tasks"] == [{"className": "quiet-rows", "text": "No tasks in SPEC.md"}]
    replaced = {"event": "snapshot", **with_tasks(synthetic([session(1, "a")]))}
    after = render(tmp_path, synthetic([session(1, "a")]), [{"name": "snapshot", "frames": [replaced]}], wall_start=TEN_START)["snapshot"]
    assert [t["id"] for t in after["panel"]["tasks"]] == ["V8", "V9", "D5", "D6"]


def folder_summary(view):
    return [(f["area"], f["closed"], f["className"], f["name"], f["counts"], f["chevron"], f["title"], [t["id"] for t in f["tasks"]]) for f in view["panel"]["folders"]]


def test_panel_groups_tasks_into_folders_with_their_own_counts(tmp_path):
    view = render(tmp_path, with_tasks(synthetic([session(1, "a")])), [{"name": "open"}], wall_start=TEN_START)["open"]
    assert folder_summary(view) == [
        ("Visualization", "0", "folder", "Visualization", "· 1 done · 1 in progress", "▾", "hide the Visualization tasks", ["V8", "V9"]),
        ("Discovery", "0", "folder", "Discovery", "· 1 in progress · 1 to do", "▾", "hide the Discovery tasks", ["D5", "D6"]),
    ]
    assert all(f["clickable"] for f in view["panel"]["folders"])
    assert view["panel"]["counts"] == "1 done · 2 in progress · 1 to do" and [t["id"] for t in view["panel"]["tasks"]] == ["V8", "V9", "D5", "D6"]
    assert view["panel"]["storage"] == {}


def test_folders_follow_the_area_field_and_name_other_series_after_the_letter(tmp_path):
    tasks = [{**task("D1", "done", "first", owner="discovery-builder"), "area": "Discovery"}, {**task("V1", "done", "second"), "area": "Visualization"}, {**task("X1", "todo", "third", owner=None), "area": "X"}, {**task("D2", "todo", "fourth", owner="discovery-builder"), "area": "Discovery"}]
    counts = {"done": 2, "in_progress": 0, "todo": 2}
    view = render(tmp_path, with_tasks(synthetic([session(1, "a")]), tasks, counts), [{"name": "open"}], wall_start=TEN_START)["open"]
    assert [(f["area"], f["counts"], [t["id"] for t in f["tasks"]]) for f in view["panel"]["folders"]] == [("Discovery", "· 1 done · 1 to do", ["D1", "D2"]), ("Visualization", "· 1 done", ["V1"]), ("X", "· 1 to do", ["X1"])]
    assert view["panel"]["counts"] == "2 done · 0 in progress · 2 to do"


def test_closing_a_folder_hides_its_tasks_and_the_choice_is_remembered(tmp_path):
    changed = {"event": "tasks", "at": "2026-10-20T12:00:06.000Z", "source": "spec", "source_pid": None, "tasks": [task("V9", "done", "task panel"), task("D5", "todo", "next discovery step", owner="discovery-builder")], "task_counts": {"done": 1, "in_progress": 0, "todo": 1}, "spec_path": "/x"}
    steps = [{"name": "open"}, {"name": "close", "clickFolder": "Discovery"}, {"name": "expand", "clickTask": "V9"}, {"name": "collapse", "clickTab": True}, {"name": "reopen", "clickTab": True}, {"name": "changed", "frames": [changed]}, {"name": "open again", "clickFolder": "Discovery"}]
    views = render(tmp_path, with_tasks(synthetic([session(1, "a")])), steps, wall_start=TEN_START)
    by_area = lambda name: {f["area"]: f for f in views[name]["panel"]["folders"]}
    closed = by_area("close")["Discovery"]
    assert (closed["closed"], closed["className"], closed["chevron"], closed["title"]) == ("1", "folder closed", "▸", "show the Discovery tasks")
    assert [t["id"] for t in closed["tasks"]] == ["D5", "D6"] and by_area("close")["Visualization"]["closed"] == "0"
    assert views["close"]["panel"]["storage"] == {"viz-web-folder-closed:Discovery": "1"} and views["close"]["panel"]["counts"] == "1 done · 2 in progress · 1 to do"
    assert by_area("expand")["Discovery"]["closed"] == "1" and by_area("expand")["Visualization"]["tasks"][1]["className"] == "task in_progress open"
    assert views["collapse"]["panel"]["collapsed"] is True and by_area("collapse")["Discovery"]["closed"] == "1"
    assert views["reopen"]["panel"]["collapsed"] is False and by_area("reopen")["Discovery"]["closed"] == "1"
    assert [(f["area"], f["closed"], f["counts"], [t["id"] for t in f["tasks"]]) for f in views["changed"]["panel"]["folders"]] == [("Visualization", "0", "· 1 done", ["V9"]), ("Discovery", "1", "· 1 to do", ["D5"])]
    assert views["changed"]["panel"]["counts"] == "1 done · 0 in progress · 1 to do"
    reopened = by_area("open again")["Discovery"]
    assert (reopened["closed"], reopened["className"], reopened["chevron"], reopened["title"]) == ("0", "folder", "▾", "hide the Discovery tasks")
    assert views["open again"]["panel"]["storage"] == {"viz-web-folder-closed:Discovery": "0", "viz-web-panel-collapsed": "0"}


def test_folder_state_survives_a_rerun_with_stored_choices_and_blocked_storage_means_open(tmp_path):
    stored = {"viz-web-folder-closed:Visualization": "1", "viz-web-folder-closed:Discovery": "0"}
    remembered = render(tmp_path, with_tasks(synthetic([session(1, "a")])), [{"name": "open"}], wall_start=TEN_START, local_storage=stored)["open"]
    assert [(f["area"], f["closed"]) for f in remembered["panel"]["folders"]] == [("Visualization", "1"), ("Discovery", "0")]
    assert remembered["panel"]["collapsed"] is False and remembered["panel"]["counts"] == "1 done · 2 in progress · 1 to do"
    blocked = render(tmp_path, with_tasks(synthetic([session(1, "a")])), [{"name": "open"}, {"name": "close", "clickFolder": "Visualization"}, {"name": "reopen", "clickFolder": "Visualization"}], wall_start=TEN_START, storage_throws=True)
    assert [(f["area"], f["closed"]) for f in blocked["open"]["panel"]["folders"]] == [("Visualization", "0"), ("Discovery", "0")]
    assert [(f["area"], f["closed"]) for f in blocked["close"]["panel"]["folders"]] == [("Visualization", "0"), ("Discovery", "0")]
    assert blocked["close"]["panel"]["storage"] == {}


def test_activity_line_waiting_beats_working_and_idle_is_blank(tmp_path):
    sessions = [session(1, "a", status="WORKING", activity="Edit x.py", waiting_on=[2, 3]), session(2, "b", waiting_on=[1]), session(3, "c", status="WORKING"), session(4, "d", activity="Read old.md"), session(5, "e", status="WORKING", activity="Bash: run it")]
    sessions[2]["label"] = None
    view = render(tmp_path, synthetic(sessions), [{"name": "now"}], wall_start=TEN_START)["now"]
    rows = {row["name"]: row for row in view["rows"]}
    assert {name: (row["status"], row["activity"], row["activityTitle"]) for name, row in rows.items()} == {
        "a": ("Working", "waiting on b, r", "waiting on b, r"), "b": ("Idle", "waiting on a", "waiting on a"), "r": ("Working", "working", "working"),
        "d": ("Idle", "", ""), "e": ("Working", "Bash: run it", f"Bash: run it\n{TEN_START}")}
    nodes = nodes_of(view)
    assert {name: (node["className"], node["last"], node["line"]) for name, node in nodes.items()} == {
        "a": ("node work", "waiting on b, r", "waiting on b, r"), "b": ("node", "waiting on a", "waiting on a"), "r": ("node work", "working", "working"),
        "d": ("node", "", ""), "e": ("node work", "Bash: run it", "Bash: run it")}


def test_waiting_label_falls_back_to_role_name_or_pid(tmp_path):
    sessions = [session(1, "a", waiting_on=[2, 3, 4, 9]), session(2, "b"), session(3, "c"), session(4, "d")]
    sessions[1]["label"] = None
    sessions[2]["label"] = sessions[2]["role"] = None
    sessions[3]["label"] = sessions[3]["role"] = sessions[3]["name"] = None
    view = render(tmp_path, synthetic(sessions), [{"name": "now"}], wall_start=TEN_START)["now"]
    assert rows_of(view)[0] == ("a", "Idle", "waiting on r, c, pid 4, 9")


@pytest.fixture(params=[(six_sessions_round, 356), (six_sessions_round, 720), (seven_sessions_round, 356), (seven_sessions_round, 720)], ids=["six-narrow", "six-wide", "seven-narrow", "seven-wide"])
def ring_view(watcher, tmp_path, request):
    build, width = request.param
    fixtures = build().write(tmp_path / "ring")
    w = watcher.Watcher(fixtures=fixtures, spec_path=None)
    w.poll_once()
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"snapshot": w.snapshot(), "steps": [{"name": "now"}, {"name": "later", "advanceMs": 11 * 60 * 1000}], "wallStart": TEN_WALL, "graphWidth": width, "localStorage": {}}))
    result = subprocess.run(["node", str(HARNESS), str(PAGE), str(input_path)], capture_output=True, text=True, check=True)
    views = {step["name"]: step["view"] for step in json.loads(result.stdout)}
    return len(fixtures), width, views["now"], views["later"]


def test_ring_shows_every_word_of_a_long_line_and_grows_without_overlap(ring_view):
    count, width, view, later = ring_view
    nodes = nodes_of(view)
    assert [node["pid"] for node in view["nodes"]] == list(range(900, 900 + count)) and len(view["chips"]) == count and len(view["rows"]) == count
    assert view["title"] == f"{count} sessions · 1 working · 1 in flight"
    assert [node["pid"] for node in later["nodes"]] == list(range(900, 900 + count)) and later["paths"] == [] and later["title"] == f"{count} sessions · 1 working · 0 in flight"
    if count == 7:
        assert (nodes["scribe"]["last"], pills(nodes["scribe"])) == ("", ["Idle"]) and rows_of(view)[-1] == ("scribe", "Idle", "")
    assert nodes["viz-builder"]["last"] == LONG_DESCRIPTION and nodes["viz-builder"]["height"] == "auto" and "work" in nodes["viz-builder"]["className"].split()
    assert nodes["manager"]["last"] == "waiting on viz-builder" and nodes["validator"]["last"] == "waiting on manager"
    assert [nodes[name]["last"] for name in ("discovery-builder", "fake manager", "fake builder")] == ["", "", ""]
    assert rows_of(view)[:6] == [("viz-builder", "Working", LONG_DESCRIPTION), ("fake manager", "Idle", ""), ("fake builder", "Idle", ""), ("validator", "Idle", "waiting on manager"), ("manager", "Idle", "waiting on viz-builder"), ("discovery-builder", "Idle", "")]
    graph_height = float(view["graphHeight"][:-2])
    assert view["viewBox"] == f"0 0 {width} {view['graphHeight'][:-2]}" and graph_height > 380
    rects = {node["name"]: node_rect(node) for node in view["nodes"]}
    assert rects["viz-builder"][3] - rects["viz-builder"][1] >= NODE_BASE_HEIGHT + 3 * NODE_LINE_PX
    for name, rect in rects.items():
        assert rect[0] >= 0 and rect[1] >= 0 and rect[2] <= width and rect[3] <= graph_height, (name, rect)
    names = list(rects)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            assert not rects_overlap(rects[first], rects[second]), (first, second)
    shown = [label for label in view["labels"] if label["clear"] == "1"]
    assert {(path["key"], path["stage"]) for path in view["paths"]} == {("900>901", "READ"), ("900>903", "READ"), ("902>900", "IN_INBOX"), ("904>905", "READ")}
    assert {label["key"] for label in view["labels"]} == {"900>901", "900>903", "902>900", "904>905"} and shown
    for label in shown:
        for name, rect in rects.items():
            assert not rects_overlap(label_rect(label), rect), (label["key"], name)


def test_read_arrow_lingers_thirty_seconds_muted_with_its_label(watcher, tmp_path):
    timed = timed_changes(watcher)
    steps = [{"name": "read", "frames": frames_between(timed, START, at("11.300"))}, {"name": "+5s", "advanceMs": 5000}, {"name": "+29s", "advanceMs": 24000}, {"name": "+31s", "advanceMs": 2000}]
    views = render(tmp_path, snapshot_at(watcher, START), steps)
    assert only_path(views["read"])["stage"] == "READ" and 0.9 < float(only_path(views["read"])["opacity"]) < 1
    for name in ("+5s", "+29s"):
        path, label = only_path(views[name]), only_label(views[name])
        assert (path["key"], path["stage"], path["opacity"], path["stroke"], path["width"]) == ("32813>33993", "READ", "0.550", OK_STROKE, "2.4"), name
        assert (label["opacity"], label["clear"], label["summary"], label["stage"]) == ("0.550", "1", FIRST_SUMMARY, ["ok", "✓✓ Read"]), name
    assert views["+31s"]["paths"] == [] and views["+31s"]["labels"] == []


def test_reply_on_the_reversed_pair_fades_the_read_arrow_within_600ms_and_takes_the_upper_lane(watcher, tmp_path):
    timed = timed_changes(watcher)
    steps = [{"name": "read", "frames": frames_between(timed, START, at("11.300"))}, {"name": "before reply", "advanceMs": 5400}, {"name": "reply sent", "frames": frames_between(timed, at("11.300"), at("17.000"))},
        {"name": "+0.3s", "advanceMs": 300}, {"name": "+0.7s", "advanceMs": 400}, {"name": "reply read", "frames": frames_between(timed, at("17.000"), at("17.700"))}, {"name": "+10s", "advanceMs": 10000}]
    views = render(tmp_path, snapshot_at(watcher, START), steps)
    assert only_path(views["before reply"])["opacity"] == "0.550" and views["before reply"]["graphHeight"] == "150px"
    sent = {path["key"]: path for path in views["reply sent"]["paths"]}
    assert (sent["32813>33993"]["stage"], sent["32813>33993"]["opacity"]) == ("READ", "0.550") and (sent["33993>32813"]["stage"], sent["33993>32813"]["opacity"]) == ("PENDING", "1")
    assert control_y(sent["33993>32813"]["d"]) < 57 and control_y(sent["32813>33993"]["d"]) > 138 and views["reply sent"]["graphHeight"] == "206px"
    labels = {label["key"]: label for label in views["reply sent"]["labels"]}
    assert labels["33993>32813"]["summary"] == REPLY_SUMMARY and labels["32813>33993"]["summary"] == FIRST_SUMMARY
    for label in labels.values():
        rect = label_rect(label)
        assert 0 <= rect[1] and rect[3] <= 206, label["key"]
        for node in views["reply sent"]["nodes"]:
            assert not rects_overlap(rect, node_rect(node)), (label["key"], node["name"])
    fading = {path["key"]: path for path in views["+0.3s"]["paths"]}
    assert fading["32813>33993"]["opacity"] == "0.500" and fading["33993>32813"]["opacity"] == "1"
    assert (only_path(views["+0.7s"])["key"], only_path(views["+0.7s"])["stage"]) == ("33993>32813", "PENDING") and views["+0.7s"]["graphHeight"] == "150px"
    assert (only_path(views["reply read"])["stage"], only_path(views["reply read"])["opacity"]) == ("READ", "1.000")
    assert (only_path(views["+10s"])["stage"], only_path(views["+10s"])["opacity"]) == ("READ", "0.550")


def test_newer_message_on_the_same_pair_replaces_the_lingering_read_arrow(tmp_path):
    sessions = [session(1, "a"), session(2, "b")]
    old = message("m1", 1, 2, "READ", "first", "2026-10-20T11:59:40.000Z", read_at="2026-10-20T11:59:55.000Z")
    newer = message("m2", 1, 2, "PENDING", "second", "2026-10-20T12:00:04.000Z")
    view = render(tmp_path, synthetic(sessions, [old, newer]), [{"name": "now"}], wall_start=TEN_START)["now"]
    assert (only_path(view)["key"], only_path(view)["stage"], only_path(view)["opacity"]) == ("1>2", "PENDING", "1") and only_label(view)["summary"] == "second +1"
    alone = render(tmp_path, synthetic(sessions, [old]), [{"name": "now"}], wall_start=TEN_START)["now"]
    assert (only_path(alone)["stage"], only_path(alone)["opacity"]) == ("READ", "0.550") and only_label(alone)["summary"] == "first"


def test_hovering_a_task_shows_its_full_text_until_the_pointer_leaves_and_click_pins(tmp_path):
    changed = {"event": "tasks", "at": "2026-10-20T12:00:06.000Z", "source": "spec", "source_pid": None, "tasks": TASKS, "task_counts": TASK_COUNTS, "spec_path": "/x"}
    steps = [{"name": "open"}, {"name": "hover", "hoverTask": "V9"}, {"name": "tick"}, {"name": "tasks change", "frames": [changed]}, {"name": "leave", "leaveTask": "V9"}, {"name": "hover second", "hoverTask": "D5"},
        {"name": "click second", "clickTask": "D5"}, {"name": "leave second", "leaveTask": "D5"}, {"name": "hover first again", "hoverTask": "V9"}]
    views = render(tmp_path, with_tasks(synthetic([session(1, "a")])), steps, wall_start=TEN_START)
    by_id = lambda name: {t["id"]: t for t in views[name]["panel"]["tasks"]}
    assert all(t["hoverable"] and t["clickable"] for t in views["open"]["panel"]["tasks"])
    assert by_id("open")["V9"]["className"] == "task in_progress"
    for name in ("hover", "tick", "tasks change"):
        assert by_id(name)["V9"]["className"] == "task in_progress hover" and by_id(name)["V9"]["title"] == "click for the full text", name
        assert by_id(name)["V9"]["full"] == "task panel. Full text of V9."
    assert by_id("leave")["V9"]["className"] == "task in_progress"
    assert by_id("hover second")["D5"]["className"] == "task todo hover"
    assert by_id("click second")["D5"]["className"] == "task todo open hover" and by_id("click second")["D5"]["title"] == "click to collapse"
    assert by_id("leave second")["D5"]["className"] == "task todo open"
    assert by_id("hover first again")["V9"]["className"] == "task in_progress hover" and by_id("hover first again")["D5"]["className"] == "task todo open"


def test_task_hover_and_wrap_rules_are_in_the_page_css():
    css = PAGE.read_text(encoding="utf-8")
    assert ".task.open .tfull, .task.hover .tfull, .task:hover .tfull { display: block; }" in css
    assert ".task.open .ttitle, .task.hover .ttitle, .task:hover .ttitle { white-space: normal; }" in css
    assert re.search(r"\.task \.tfull \{[^}]*white-space: pre-wrap;[^}]*word-break: break-word;", css)


def seven_render(watcher, tmp_path, steps, width=356, local_storage=None, window_height=1000, build=seven_sessions_round):
    fixtures = build().write(tmp_path / "ring")
    w = watcher.Watcher(fixtures=fixtures, spec_path=None)
    w.poll_once()
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"snapshot": w.snapshot(), "steps": steps, "wallStart": TEN_WALL, "graphWidth": width, "localStorage": local_storage or {}, "windowHeight": window_height}))
    result = subprocess.run(["node", str(HARNESS), str(PAGE), str(input_path)], capture_output=True, text=True, check=True)
    return {step["name"]: step["view"] for step in json.loads(result.stdout)}


def node_pos(view, pid):
    node = next(node for node in view["nodes"] if node["pid"] == pid)
    return float(node["left"][:-2]), float(node["top"][:-2])


def path_end(view, key):
    d = next(path for path in view["paths"] if path["key"] == key)["d"]
    numbers = [float(x) for x in re.findall(r"-?\d+\.?\d*", d)]
    return numbers[4], numbers[5]


def pin_keys(view):
    return {key: json.loads(value) for key, value in view["storage"].items() if key.startswith("viz-web-pin:")}


def test_dragging_a_node_pins_it_and_its_arrow_follows(watcher, tmp_path):
    steps = [{"name": "start"}, {"name": "hold", "pointer": {"pid": 901, "moves": [[-30, 60], [-100, 200]], "hold": True}}, {"name": "drop", "releaseNode": 901}, {"name": "tick"}]
    views = seven_render(watcher, tmp_path, steps)
    start = views["start"]
    assert all(node["draggable"] for node in start["nodes"]) and start["resetHidden"] is True and pin_keys(start) == {}
    left0, top0 = node_pos(start, 901)
    held = views["hold"]
    held_node = nodes_of(held)["viz-builder"]
    assert held_node["className"] == "node incomplete work pinned dragging" and held_node["captured"] is True and held["graphClass"] == "dragging"
    assert node_pos(held, 901) == pytest.approx((left0 - 100, top0 + 200))
    dropped = views["drop"]
    node = nodes_of(dropped)["viz-builder"]
    assert node["className"] == "node incomplete work pinned" and node["captured"] is False and dropped["graphClass"] == ""
    assert node_pos(dropped, 901) == pytest.approx((left0 - 100, top0 + 200)) and node_pos(views["tick"], 901) == pytest.approx((left0 - 100, top0 + 200))
    rect = node_rect(node)
    assert pin_keys(dropped) == {"viz-web-pin:901": {"x": round(left0 - 100 + 58), "y": round(top0 + 200 + (rect[3] - rect[1]) / 2)}}
    assert dropped["resetHidden"] is False
    before_end, after_end = path_end(start, "900>901"), path_end(dropped, "900>901")
    assert after_end[1] > before_end[1] + 150 and after_end[0] < before_end[0]
    assert node_pos(dropped, 900) == node_pos(start, 900) and node_pos(dropped, 906) == node_pos(start, 906)
    assert float(dropped["graphHeight"][:-2]) >= top0 + 200 + (rect[3] - rect[1]) + 12
    rects = {n["name"]: node_rect(n) for n in dropped["nodes"]}
    names = list(rects)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            assert not rects_overlap(rects[first], rects[second]), (first, second)
    for label in dropped["labels"]:
        if label["clear"] == "1":
            for name, r in rects.items():
                assert not rects_overlap(label_rect(label), r), (label["key"], name)


def test_a_press_under_four_pixels_is_a_click_and_a_click_right_after_a_drop_is_ignored(watcher, tmp_path):
    steps = [{"name": "start"}, {"name": "wiggle", "pointer": {"pid": 901, "moves": [[2, 2]], "thenClick": True}}, {"name": "unpick", "clickNode": 901},
        {"name": "drag", "pointer": {"pid": 901, "dx": -60, "dy": 120, "thenClick": True}}, {"name": "late click", "advanceMs": 1000, "clickNode": 901}, {"name": "cancelled", "pointer": {"pid": 903, "moves": [[20, 80]], "cancel": True}}]
    views = seven_render(watcher, tmp_path, steps)
    left0, top0 = node_pos(views["start"], 901)
    wiggled = nodes_of(views["wiggle"])["viz-builder"]
    assert wiggled["className"] == "node incomplete picked work" and node_pos(views["wiggle"], 901) == (left0, top0) and pin_keys(views["wiggle"]) == {} and views["wiggle"]["resetHidden"] is True
    assert "picked" not in nodes_of(views["unpick"])["viz-builder"]["className"].split()
    dragged = nodes_of(views["drag"])["viz-builder"]
    assert dragged["className"] == "node incomplete work pinned" and node_pos(views["drag"], 901) == pytest.approx((left0 - 60, top0 + 120))
    assert nodes_of(views["late click"])["viz-builder"]["className"] == "node incomplete picked work pinned"
    assert nodes_of(views["cancelled"])["discovery-builder"]["className"] == "node incomplete pinned" and "viz-web-pin:903" in pin_keys(views["cancelled"])


def test_drops_are_clamped_to_the_graph_sides_and_window_bottom_and_the_graph_grows(watcher, tmp_path):
    steps = [{"name": "start"}, {"name": "left", "pointer": {"pid": 905, "dx": -1000, "dy": 0}}, {"name": "up", "pointer": {"pid": 900, "dx": 0, "dy": -1000}}, {"name": "right", "pointer": {"pid": 902, "dx": 1000, "dy": 0}}, {"name": "down", "pointer": {"pid": 904, "dx": 0, "dy": 5000}}]
    views = seven_render(watcher, tmp_path, steps, window_height=900)
    assert node_pos(views["left"], 905)[0] == 0
    assert node_pos(views["up"], 900)[1] == 0
    assert node_pos(views["right"], 902)[0] == 356 - 116
    rect = node_rect(nodes_of(views["down"])["fake manager"])
    height = rect[3] - rect[1]
    assert node_pos(views["down"], 904)[1] == 900 - height and views["down"]["graphHeight"] == "912px" and views["down"]["viewBox"] == "0 0 356 912"
    assert pin_keys(views["down"])["viz-web-pin:904"] == {"x": round(node_pos(views["down"], 904)[0] + 58), "y": round(900 - height / 2)}


def test_pins_are_stored_by_label_then_role_then_pid(tmp_path):
    sessions = [session(1, "a"), session(2, "b"), session(3, "c")]
    sessions[1]["label"] = None
    sessions[2]["label"] = sessions[2]["role"] = None
    steps = [{"name": "start"}, {"name": "one", "pointer": {"pid": 1, "dx": 0, "dy": 150}}, {"name": "two", "pointer": {"pid": 2, "dx": 0, "dy": 150}}, {"name": "three", "pointer": {"pid": 3, "dx": 0, "dy": 150}}]
    views = render(tmp_path, synthetic(sessions), steps, wall_start=TEN_START, local_storage={"viz-web-panel-collapsed": "0"})
    assert set(pin_keys(views["three"])) == {"viz-web-pin:a", "viz-web-pin:r", "viz-web-pin:3"}
    assert views["three"]["storage"]["viz-web-panel-collapsed"] == "0"
    assert all("pinned" in node["className"].split() for node in views["three"]["nodes"])


def test_saved_pins_land_a_session_and_a_later_session_with_the_same_label_at_the_same_spot(tmp_path):
    sessions = [session(1, "a"), session(2, "b"), session(3, "c")]
    plain = render(tmp_path, synthetic(sessions), [{"name": "now"}], wall_start=TEN_START)["now"]
    seeded = render(tmp_path, synthetic(sessions), [{"name": "now"}], wall_start=TEN_START, local_storage={"viz-web-pin:b": json.dumps({"x": 70, "y": 300})})["now"]
    assert node_pos(seeded, 2) == (70 - 58, 300 - 31) and nodes_of(seeded)["b"]["className"] == "node pinned" and seeded["resetHidden"] is False
    assert node_pos(seeded, 1) == node_pos(plain, 1) and nodes_of(seeded)["a"]["className"] == "node"
    restarted = [session(1, "a"), session(9, "b"), session(3, "c")]
    again = render(tmp_path, synthetic(restarted), [{"name": "now"}], wall_start=TEN_START, local_storage={"viz-web-pin:b": json.dumps({"x": 70, "y": 300})})["now"]
    assert node_pos(again, 9) == (70 - 58, 300 - 31) and nodes_of(again)["b"]["className"] == "node pinned"
    broken = render(tmp_path, synthetic(sessions), [{"name": "now"}], wall_start=TEN_START, local_storage={"viz-web-pin:b": "not json"})["now"]
    assert node_pos(broken, 2) == node_pos(plain, 2) and broken["resetHidden"] is True
    blocked = render(tmp_path, synthetic(sessions), [{"name": "now"}, {"name": "drag", "pointer": {"pid": 2, "dx": 0, "dy": 100}}], wall_start=TEN_START, storage_throws=True)
    assert node_pos(blocked["drag"], 2) == pytest.approx((node_pos(blocked["now"], 2)[0], node_pos(blocked["now"], 2)[1] + 100)) and "pinned" in nodes_of(blocked["drag"])["b"]["className"].split()


def test_reset_layout_clears_every_pin_and_returns_to_the_ring(watcher, tmp_path):
    steps = [{"name": "start"}, {"name": "drag one", "pointer": {"pid": 901, "dx": -100, "dy": 200}}, {"name": "drag two", "pointer": {"pid": 905, "dx": 40, "dy": 10}}, {"name": "reset", "clickReset": True}, {"name": "tick"}]
    views = seven_render(watcher, tmp_path, steps, local_storage={"viz-web-folder-closed:Discovery": "1", "viz-web-pin:999": json.dumps({"x": 1, "y": 2})})
    assert set(pin_keys(views["drag two"])) == {"viz-web-pin:901", "viz-web-pin:905", "viz-web-pin:999"} and views["drag two"]["resetHidden"] is False
    reset = views["reset"]
    assert pin_keys(reset) == {} and reset["storage"] == {"viz-web-folder-closed:Discovery": "1"} and reset["resetHidden"] is True
    for pid in (900, 901, 902, 903, 904, 905, 906):
        assert node_pos(reset, pid) == node_pos(views["start"], pid) and node_pos(views["tick"], pid) == node_pos(views["start"], pid), pid
    assert not any("pinned" in node["className"].split() for node in reset["nodes"])
    assert reset["graphHeight"] == views["start"]["graphHeight"]


def test_pod_and_compact_nodes_drag_too(watcher, tmp_path):
    pod = render(tmp_path, snapshot_at(watcher, at("10.500")), [{"name": "now"}, {"name": "drag", "pointer": {"pid": 32813, "dx": 30, "dy": 120}}], wall_start=at("10.500"))
    left0, top0 = node_pos(pod["now"], 32813)
    assert node_pos(pod["drag"], 32813) == pytest.approx((left0 + 30, top0 + 120)) and "pinned" in nodes_of(pod["drag"])["fake manager"]["className"].split()
    assert path_end(pod["drag"], "32813>33993") != path_end(pod["now"], "32813>33993") and float(pod["drag"]["graphHeight"][:-2]) > 150
    compact = seven_render(watcher, tmp_path, [{"name": "now"}, {"name": "drag", "pointer": {"pid": 900, "dx": 50, "dy": 100}}], build=ten_sessions_round)
    left0, top0 = node_pos(compact["now"], 900)
    assert node_pos(compact["drag"], 900) == pytest.approx((left0 + 50, top0 + 100)) and {"compact", "pinned"} <= set(nodes_of(compact["drag"])["manager"]["className"].split())
    assert nodes_of(compact["drag"])["manager"]["height"] == f"{COMPACT_NODE_HEIGHT}px" and pin_keys(compact["drag"]) == {"viz-web-pin:900": {"x": round(left0 + 50 + 50), "y": round(top0 + 100 + 12)}}
