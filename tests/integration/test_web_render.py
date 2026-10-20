import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import FIXTURES_DIR, REPO_ROOT
from fixtures.viz.ten_sessions import PIDS, ten_sessions_round

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
PENDING_STROKE, OK_STROKE, FAILED_STROKE = "#8a8a8a", "#4ad17a", "#ff6b6b"
LABEL_CHAR_PX, LABEL_HEIGHT, LABEL_MAX_WIDTH = 6.3, 30, 170
COMPACT_NODE_HEIGHT = 24
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


def render(tmp_path, snapshot, steps, wall_start=START):
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"snapshot": snapshot, "steps": steps, "wallStart": wall_start}))
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


def node_rect(node):
    left, top, width = (float(node[key][:-2]) for key in ("left", "top", "width"))
    height = float(node["height"][:-2]) if node["height"].endswith("px") else 62
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
    assert (view["link"], view["eventsUrl"], view["pod"], view["viewBox"]) == ("live", "./events", True, "0 0 356 150")
    assert 250 in view["intervals"]
    assert view["caption"][0] == "registry"
    manager, builder = nodes_of(view)["fake manager"], nodes_of(view)["fake builder"]
    assert (manager["left"], builder["left"], manager["top"]) == ("20px", "220px", "59px")
    for node in (manager, builder):
        assert node["className"] == "node" and pills(node) == ["Idle"] and node["mail"] is None and node["last"] == "" and node["eye"] is None
    assert view["paths"] == [] and view["labels"] == []
    assert [(chip["pid"], chip["className"], chip["text"], chip["count"]) for chip in view["chips"]] == [(32813, "chip", "fake manager", None), (33993, "chip", "fake builder", None)]
    assert rows_of(view) == [("fake manager", "Idle", "idle"), ("fake builder", "Idle", "idle")]
    assert all(row["className"] == "arow" and row["pill"] == ["pill idle", "Idle"] and row["clickable"] for row in view["rows"])


def test_send_shows_pending_arrow_and_sending_row_first(round_views):
    view = round_views["send"]
    assert view["title"] == "fake_session · 2 sessions · 1 working · 1 in flight"
    assert view["caption"] == ["assistant → tool_use SendMessage", "fake manager → fake builder"]
    manager, builder = nodes_of(view)["fake manager"], nodes_of(view)["fake builder"]
    assert manager["className"] == "node hot" and pills(manager) == ["Sending"]
    assert manager["last"] == "👁Watching fake builder" and manager["eye"] == "eye"
    assert builder["className"] == "node hot" and pills(builder) == ["Idle"] and builder["mail"] is None
    path = only_path(view)
    assert (path["key"], path["stage"], path["stroke"], path["marker"], path["width"], path["opacity"], path["className"]) == ("32813>33993", "PENDING", PENDING_STROKE, "url(#mp)", "2.4", "1", "")
    label = only_label(view)
    assert (label["key"], label["summary"], label["stage"], label["opacity"], label["clear"]) == ("32813>33993", FIRST_SUMMARY, ["pend", "Pending"], "1", "1")
    assert label["title"].startswith("PENDING\n" + FIRST_BODY)
    assert chips_of(view)[32813]["className"] == "chip on" and chips_of(view)[32813]["dotClass"] == "dot work"
    assert rows_of(view) == [("fake manager", "Sending", f"SendMessage: {FIRST_SUMMARY}"), ("fake builder", "Idle", "idle")]
    manager_row = view["rows"][0]
    assert manager_row["className"] == "arow work" and manager_row["pill"] == ["pill work", "Sending"] and manager_row["dotClass"] == "dot work"
    assert manager_row["activityTitle"] == f"SendMessage: {FIRST_SUMMARY}\n{at('10.318')}"


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
    assert rows_of(view) == [("fake manager", "Working", f"SendMessage: {FIRST_SUMMARY}"), ("fake builder", "Idle", "idle 0 min")]


def test_read_clears_the_envelope_flashes_and_sets_the_builder_row_working(round_views):
    view = round_views["read"]
    assert view["title"] == "fake_session · 2 sessions · 2 working · 0 in flight"
    builder = nodes_of(view)["fake builder"]
    assert pills(builder) == ["Working"] and builder["mail"] is None and builder["className"] == "node"
    assert builder["last"].startswith("“" + FIRST_BODY[:40]) and builder["last"].endswith("…”")
    path = only_path(view)
    assert (path["stage"], path["stroke"]) == ("READ", OK_STROKE) and 0.9 < float(path["opacity"]) < 1
    assert only_label(view)["stage"] == ["ok", "✓✓ Read"]
    assert chips_of(view)[33993]["className"] == "chip on" and chips_of(view)[33993]["count"] is None
    assert rows_of(view) == [("fake builder", "Working", "working"), ("fake manager", "Working", f"SendMessage: {FIRST_SUMMARY}")]
    faded = round_views["flash gone"]
    assert faded["paths"] == [] and faded["labels"] == []
    ended = round_views["manager turn end"]
    manager_row = ended["rows"][1]
    assert rows_of(ended)[0] == ("fake builder", "Working", "working")
    assert (manager_row["name"], manager_row["status"], manager_row["className"]) == ("fake manager", "Idle", "arow")
    assert manager_row["activity"].startswith(MANAGER_TEXT_START) and manager_row["activity"].endswith("…") and len(manager_row["activity"]) == 140
    assert manager_row["activityTitle"].endswith("\n" + at("13.303"))
    assert nodes_of(ended)["fake manager"]["last"] == "👁Watching fake builder"


def test_reply_shows_the_envelope_on_the_manager_and_the_rows_follow(round_views):
    pending = round_views["reply pending"]
    builder = nodes_of(pending)["fake builder"]
    assert pills(builder) == ["Sending"] and builder["last"] == REPLY_SUMMARY
    path = only_path(pending)
    assert (path["key"], path["stage"], path["stroke"]) == ("33993>32813", "PENDING", PENDING_STROKE)
    assert rows_of(pending)[0] == ("fake builder", "Sending", f"SendMessage: {REPLY_SUMMARY}")
    assert rows_of(pending)[1][:2] == ("fake manager", "Idle")
    inbox = round_views["reply in inbox"]
    assert only_path(inbox)["stage"] == "IN_INBOX"
    manager = nodes_of(inbox)["fake manager"]
    assert pills(manager) == ["Idle"] and manager["pills"] == [["pill idle", "Idle"], ["mail", "✉ 1"]]
    assert (chips_of(inbox)[32813]["className"], chips_of(inbox)[32813]["count"]) == ("chip hot", "1")
    read = round_views["reply read"]
    assert only_path(read)["stage"] == "READ"
    manager = nodes_of(read)["fake manager"]
    assert pills(manager) == ["Working"] and manager["mail"] is None
    assert rows_of(read)[0][:2] == ("fake manager", "Working") and rows_of(read)[0][2].startswith(MANAGER_TEXT_START)
    assert rows_of(read)[1] == ("fake builder", "Working", f"SendMessage: {REPLY_SUMMARY}")


def test_idle_notice_pulses_the_eye_without_an_arrow(round_views):
    view = round_views["idle notice"]
    assert view["caption"] == ["user · cross-session idle notice", "fake builder → fake manager"]
    manager = nodes_of(view)["fake manager"]
    assert manager["last"] == "👁idle notice" and manager["eye"] == "eye pulse"
    assert view["paths"] == [] and view["labels"] == []
    after = round_views["pulse gone"]
    assert nodes_of(after)["fake manager"]["eye"] is None
    assert nodes_of(after)["fake manager"]["last"].startswith("“" + REPLY_BODY_START)


def test_round_ends_with_idle_rows_ordered_by_last_change(round_views):
    end = round_views["end"]
    assert end["title"] == "fake_session · 2 sessions · 0 working · 0 in flight"
    assert end["paths"] == []
    assert [pills(node) for node in end["nodes"]] == [["Idle"], ["Idle"]]
    assert rows_of(end) == [("fake manager", "Idle", "The builder is idle again, so the charged trace on the dashboard has drained back to this capsule. Nothing further to do."),
        ("fake builder", "Idle", "Replied to fake-session-manager's second hello with another hi back. That's another pulse from this session to that one on the dashboard.")]
    picked = round_views["row pick"]
    assert picked["rows"][1]["className"] == "arow picked" and nodes_of(picked)["fake builder"]["className"] == "node picked"
    assert chips_of(picked)[33993]["className"] == "chip picked"
    assert round_views["row unpick"]["rows"][1]["className"] == "arow"
    later = round_views["eleven minutes later"]
    assert [node["pid"] for node in later["nodes"]] == [32813, 33993]
    assert [row["activity"] for row in later["rows"]] == [row["activity"] for row in end["rows"]]


def test_idle_rows_count_minutes_since_the_turn_end(tmp_path):
    sessions = [session(1, "a", idle_since="2026-10-20T11:50:00.000Z"), session(2, "b", status="WORKING")]
    views = render(tmp_path, synthetic(sessions), [{"name": "now"}, {"name": "later", "advanceMs": 5 * 60 * 1000}], wall_start=TEN_START)
    assert rows_of(views["now"]) == [("b", "Working", "working"), ("a", "Idle", "idle 10 min")]
    assert rows_of(views["later"]) == [("b", "Working", "working"), ("a", "Idle", "idle 15 min")]


def test_change_stream_matches_the_frozen_snapshot_at_each_cut(watcher, tmp_path):
    timed = timed_changes(watcher)
    for until in ("10.500", "11.000", "17.600", "21.060"):
        streamed = render(tmp_path, snapshot_at(watcher, START), [{"name": "s", "frames": frames_between(timed, START, at(until))}], wall_start=at(until))["s"]
        frozen = render(tmp_path, snapshot_at(watcher, at(until)), [{"name": "s"}], wall_start=at(until))["s"]
        for part in ("nodes", "paths", "labels", "chips", "rows", "title", "pod"):
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
    assert set(nodes_of(picked)["fake manager"]["className"].split()) == {"node", "hot", "picked"}
    assert (only_path(picked)["width"], only_path(picked)["className"]) == ("2.4", "")
    assert views["pick chip"]["rows"][0]["className"] == "arow work picked"
    unpicked = views["unpick chip"]
    assert chips_of(unpicked)[32813]["className"] == "chip on" and nodes_of(unpicked)["fake manager"]["className"] == "node hot"
    assert set(nodes_of(views["pick node"])["fake builder"]["className"].split()) == {"node", "hot", "picked"}
    assert only_label(views["hover path"])["zIndex"] == "4" and only_label(views["leave path"])["zIndex"] == "2"
    assert (views["error"]["link"], views["error"]["linkClass"]) == ("reconnecting", "off")
    assert (views["reopen"]["link"], views["reopen"]["linkClass"]) == ("live", "")


def session(pid, label, cwd="/home/user/path_finder", role="r", status="IDLE", inbox=0, watching=(), last_seen_at="2026-10-20T12:00:05.000Z", activity=None, idle_since=None):
    return {"pid": pid, "name": label, "role": role, "label": label, "cwd": cwd, "status": status, "inbox": inbox, "last_text": None, "watching": list(watching), "socket": f"uds:/tmp/cc-socks/{pid}.sock",
        "last_seen_at": last_seen_at, "activity": activity, "activity_at": last_seen_at if activity else None, "idle_since": idle_since, "last_assistant_text": None}


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
    assert [node["pid"] for node in failed["nodes"]] == [1, 2]
    assert (only_path(failed)["stage"], only_path(failed)["stroke"], only_path(failed)["marker"]) == ("FAILED", FAILED_STROKE, "url(#mr)")
    assert only_label(failed)["stage"] == ["fail", "✗ Failed"] and only_label(failed)["title"].startswith("FAILED: Not sent: refused")
    assert chips_of(failed)[3]["className"] == "chip out"
    resolved = views["resolved"]
    assert only_path(resolved)["stage"] == "IN_INBOX" and only_label(resolved)["summary"] == "resend"


def test_ring_drops_sessions_without_recent_traffic_and_falls_back_to_everyone(tmp_path):
    sessions = [session(1, "a"), session(2, "b"), session(3, "c")]
    recent = [message("m1", 1, 2, "READ", "a to b", "2026-10-20T11:59:00.000Z", read_at="2026-10-20T11:59:30.000Z")]
    views = render(tmp_path, synthetic(sessions, recent), [{"name": "now"}, {"name": "later", "advanceMs": 11 * 60 * 1000}], wall_start=TEN_START)
    assert [node["pid"] for node in views["now"]["nodes"]] == [1, 2] and views["now"]["pod"] is True
    assert chips_of(views["now"])[3]["className"] == "chip out"
    assert [node["pid"] for node in views["later"]["nodes"]] == [1, 2, 3] and views["later"]["pod"] is False
    assert len(views["later"]["rows"]) == 3


def test_watching_keeps_a_session_in_the_ring_and_unidentified_nodes_are_dashed(tmp_path):
    sessions = [session(1, "a", watching=[3]), session(2, "b"), session(3, "c", role=None)]
    view = render(tmp_path, synthetic(sessions, sources=[source(2, "registry", 1)]), [{"name": "now"}], wall_start=TEN_START)["now"]
    assert [node["pid"] for node in view["nodes"]] == [1, 3]
    assert nodes_of(view)["a"]["last"] == "👁Watching c"
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
    assert rows_of(views["replaced"]) == [("only", "Idle", "idle 0 min")]


@pytest.fixture
def ten_view(watcher, tmp_path):
    fixtures = ten_sessions_round().write(tmp_path / "ten")
    w = watcher.Watcher(fixtures=fixtures)
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
        ("listings-e6", "Working", "Edit scores.py"),
        ("tag-analyzer", "Working", "SendMessage: tags done"),
        ("viz-builder", "Working", "SendMessage: V7 ready, handoff written"),
        ("fake manager", "Working", "SendMessage: second hello"),
        ("manager", "Working", "SendMessage: rerun scores"),
        ("semantic-scores", "Working", "SendMessage: batch 3 written"),
        ("validator", "Idle", "SendMessage: V6 review: PASS"),
        ("fake builder", "Idle", "Replied with a hi back."),
        ("discovery-builder", "Idle", "idle 0 min"),
        ("listings-bc", "Idle", "idle 0 min"),
    ]
    assert len(view["paths"]) == 9
    stages = {path["key"]: path["stage"] for path in view["paths"]}
    assert stages["902>900"] == "FAILED" and stages["908>906"] == "READ" and sum(stage == "IN_INBOX" for stage in stages.values()) == 7
    shown = {label["key"]: label for label in view["labels"] if label["clear"] == "1"}
    hidden = {label["key"]: label for label in view["labels"] if label["clear"] == "0"}
    assert len(shown) + len(hidden) == 9
    assert all(label["opacity"] == "0" for label in hidden.values())
    assert all(label["opacity"] != "0" for label in shown.values())
    assert {key: label["text"] for key, label in shown.items()} == {"908>906": "tags done✓✓ Read", "906>907": "rerun scores✓ In inbox", "900>903": "D4 assigned✓ In inbox", "900>909": "rerun scores✓ In inbox", "902>901": "V6 review: PASS✓ In inbox"}
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
