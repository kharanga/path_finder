import json
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import FIXTURES_DIR, REPO_ROOT

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
PENDING_STROKE, OK_STROKE, FAILED_STROKE = "#8a8a8a", "#4ad17a", "#ff6b6b"

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


def render(tmp_path, snapshot, steps, wall_start=START, graph_width=None):
    input_path = tmp_path / "input.json"
    payload = {"snapshot": snapshot, "steps": steps, "wallStart": wall_start}
    if graph_width:
        payload["graphWidth"] = graph_width
    input_path.write_text(json.dumps(payload))
    result = subprocess.run(["node", str(HARNESS), str(PAGE), str(input_path)], capture_output=True, text=True, check=True)
    return {step["name"]: step["view"] for step in json.loads(result.stdout)}


def nodes_of(view):
    return {node["name"]: node for node in view["nodes"]}


def chips_of(view):
    return {chip["pid"]: chip for chip in view["chips"]}


def pills(node):
    return [text for _class, text in node["pills"]]


def only_path(view):
    assert len(view["paths"]) == 1, view["paths"]
    return view["paths"][0]


def only_label(view):
    assert len(view["labels"]) == 1, view["labels"]
    return view["labels"][0]


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
        {"name": "toast gone", "advanceMs": 5000},
        cut("reply pending", "11.300", "17.000"),
        cut("reply in inbox", "17.000", "17.600"),
        cut("reply read", "17.600", "17.700"),
        cut("idle notice", "17.700", "21.100"),
        {"name": "pulse gone", "advanceMs": 1500},
        {"name": "end", "frames": frames_between(timed, at("21.100"), None), "advanceMs": 9000},
        {"name": "eleven minutes later", "advanceMs": 660000},
    ]
    assert all(step["frames"] for step in steps if "frames" in step)
    return render(tmp_path, snapshot_at(watcher, START), steps)


def test_start_is_a_quiet_pod(round_views):
    view = round_views["start"]
    assert view["title"] == "fake_session · 2 sessions · 0 working · 0 in flight"
    assert (view["link"], view["eventsUrl"], view["pod"], view["viewBox"]) == ("live", "./events", True, "0 0 356 150")
    assert 250 in view["intervals"]
    assert view["caption"][0] == "registry"
    manager, builder = nodes_of(view)["fake manager"], nodes_of(view)["fake builder"]
    assert (manager["left"], builder["left"], manager["top"]) == ("20px", "220px", "59px")
    for node in (manager, builder):
        assert node["className"] == "node" and pills(node) == ["Idle"] and node["last"] == "" and node["eye"] is None
    assert view["paths"] == [] and view["labels"] == []
    assert [(chip["pid"], chip["className"], chip["text"], chip["count"]) for chip in view["chips"]] == [(32813, "chip", "fake manager", None), (33993, "chip", "fake builder", None)]
    assert view["toasts"] == [{"className": "quiet-toasts", "text": "No traffic"}]


def test_send_shows_pending_arrow_toast_and_sending_pill(round_views):
    view = round_views["send"]
    assert view["title"] == "fake_session · 2 sessions · 1 working · 1 in flight"
    assert view["caption"] == ["assistant → tool_use SendMessage", "fake manager → fake builder"]
    manager, builder = nodes_of(view)["fake manager"], nodes_of(view)["fake builder"]
    assert manager["className"] == "node hot" and pills(manager) == ["Sending"]
    assert manager["last"] == "👁 Watching fake builder" and manager["eye"] == "eye"
    assert builder["className"] == "node hot" and pills(builder) == ["Idle"] and builder["last"] == ""
    path = only_path(view)
    assert (path["key"], path["stage"], path["stroke"], path["marker"], path["width"], path["opacity"], path["className"]) == ("32813>33993", "PENDING", PENDING_STROKE, "url(#mp)", "2.4", "1", "")
    assert path["d"].startswith("M") and " Q" in path["d"] and path["hoverable"]
    label = only_label(view)
    assert (label["key"], label["summary"], label["stage"], label["opacity"]) == ("32813>33993", FIRST_SUMMARY, ["pend", "Pending"], "1")
    assert label["title"].startswith("PENDING\n" + FIRST_BODY)
    assert chips_of(view)[32813]["className"] == "chip on" and chips_of(view)[32813]["dotClass"] == "dot work"
    assert chips_of(view)[33993]["className"] == "chip"
    toast = view["toasts"][0]
    assert len(view["toasts"]) == 1
    assert (toast["className"], toast["key"], toast["from"], toast["stage"][:2], toast["sum"]) == ("toast pend", "32813>33993", "fake manager→fake builder", ["st pend", "Pending"], FIRST_BODY)
    assert toast["hoverable"]


def test_enqueue_turns_the_arrow_green_and_counts_the_inbox(round_views):
    view = round_views["enqueue"]
    assert view["caption"] == ["queue-operation · enqueue", "fake manager → fake builder"]
    manager, builder = nodes_of(view)["fake manager"], nodes_of(view)["fake builder"]
    assert pills(manager) == ["Working"] and manager["last"] == "👁 Watching fake builder"
    assert pills(builder) == ["Idle", "Inbox 1"] and builder["pills"][1][0] == "pill inbox"
    path = only_path(view)
    assert (path["stage"], path["stroke"], path["marker"]) == ("IN_INBOX", OK_STROKE, "url(#mg)")
    assert only_label(view)["stage"] == ["ok", "✓ In inbox"]
    chip = chips_of(view)[33993]
    assert (chip["className"], chip["count"], chip["text"]) == ("chip hot", "1", "fake builder1")
    assert (view["toasts"][0]["className"], view["toasts"][0]["stage"][:2]) == ("toast ", ["st ok", "✓ In inbox"])
    assert view["title"].endswith("1 working · 1 in flight")


def test_read_flashes_then_fades_and_the_toast_lingers_eight_seconds(round_views):
    view = round_views["read"]
    assert view["title"] == "fake_session · 2 sessions · 2 working · 0 in flight"
    manager, builder = nodes_of(view)["fake manager"], nodes_of(view)["fake builder"]
    assert pills(builder) == ["Working"] and builder["className"] == "node"
    assert builder["last"].startswith("“" + FIRST_BODY[:40]) and builder["last"].endswith("…”")
    assert builder["lastTitle"] == builder["last"]
    assert pills(manager) == ["Working"] and manager["last"] == "👁 Watching fake builder"
    path = only_path(view)
    assert (path["stage"], path["stroke"]) == ("READ", OK_STROKE)
    assert 0.9 < float(path["opacity"]) < 1
    label = only_label(view)
    assert label["stage"] == ["ok", "✓✓ Read"] and label["opacity"] == path["opacity"]
    assert chips_of(view)[33993]["className"] == "chip on" and chips_of(view)[33993]["count"] is None
    toast = view["toasts"][0]
    assert (toast["className"], toast["stage"][:2], toast["msg"]) == ("toast ", ["st ok", "✓✓ Read"], "693b9bd4-a916-40de-9ff1-aee2ee5dd741")
    faded = round_views["flash gone"]
    assert faded["paths"] == [] and faded["labels"] == []
    assert faded["toasts"][0]["className"] == "toast gone"
    assert nodes_of(faded)["fake builder"]["className"] == "node"
    gone = round_views["toast gone"]
    assert gone["toasts"] == [{"className": "quiet-toasts", "text": "No traffic"}]
    assert gone["paths"] == []


def test_reply_runs_right_to_left_through_the_same_stages(round_views):
    pending = round_views["reply pending"]
    manager, builder = nodes_of(pending)["fake manager"], nodes_of(pending)["fake builder"]
    assert pills(builder) == ["Sending"] and builder["last"] == REPLY_SUMMARY and builder["className"] == "node hot"
    assert pills(manager) == ["Idle"] and manager["last"] == "👁 Watching fake builder"
    path = only_path(pending)
    assert (path["key"], path["stage"], path["stroke"]) == ("33993>32813", "PENDING", PENDING_STROKE)
    assert only_label(pending)["summary"] == REPLY_SUMMARY
    assert pending["toasts"][0]["from"] == "fake builder→fake manager" and pending["toasts"][0]["className"] == "toast pend"
    assert pending["caption"] == ["assistant → tool_use SendMessage", "fake builder → fake manager"]
    inbox = round_views["reply in inbox"]
    assert only_path(inbox)["stage"] == "IN_INBOX"
    assert pills(nodes_of(inbox)["fake manager"]) == ["Idle", "Inbox 1"]
    assert pills(nodes_of(inbox)["fake builder"]) == ["Working"] and nodes_of(inbox)["fake builder"]["last"] == ""
    assert (chips_of(inbox)[32813]["className"], chips_of(inbox)[32813]["count"]) == ("chip hot", "1")
    read = round_views["reply read"]
    assert only_path(read)["stage"] == "READ" and 0.9 < float(only_path(read)["opacity"]) <= 1
    assert pills(nodes_of(read)["fake manager"]) == ["Working"]
    assert nodes_of(read)["fake manager"]["last"] == "👁 Watching fake builder"
    assert read["toasts"][0]["stage"][1] == "✓✓ Read" and read["toasts"][0]["from"] == "fake builder→fake manager"
    assert read["title"].endswith("0 in flight")


def test_idle_notice_pulses_the_eye_and_is_a_muted_toast_without_an_arrow(round_views):
    view = round_views["idle notice"]
    assert view["caption"] == ["user · cross-session idle notice", "fake builder → fake manager"]
    manager = nodes_of(view)["fake manager"]
    assert pills(manager) == ["Working"]
    assert manager["last"] == "👁 idle notice" and manager["eye"] == "eye pulse"
    assert nodes_of(view)["fake builder"]["eye"] is None
    assert view["paths"] == [] and view["labels"] == []
    notice, reply = view["toasts"][:2]
    assert (notice["className"], notice["from"], notice["stage"][:2]) == ("toast notice", "fake builderidle notice tofake manager", ["st pend", "👁"])
    assert notice["key"] is None and notice["sum"] is None
    assert reply["className"] == "toast gone" and reply["from"] == "fake builder→fake manager"
    after = round_views["pulse gone"]
    manager = nodes_of(after)["fake manager"]
    assert manager["eye"] is None
    assert manager["last"].startswith("“" + REPLY_BODY_START)
    assert after["toasts"][0]["className"] == "toast notice"


def test_round_ends_quiet_and_the_ring_keeps_both_after_the_horizon(round_views):
    end = round_views["end"]
    assert end["title"] == "fake_session · 2 sessions · 0 working · 0 in flight"
    assert end["toasts"] == [{"className": "quiet-toasts", "text": "No traffic"}]
    assert end["paths"] == []
    assert [pills(node) for node in end["nodes"]] == [["Idle"], ["Idle"]]
    assert nodes_of(end)["fake manager"]["last"].startswith("“" + REPLY_BODY_START)
    assert nodes_of(end)["fake builder"]["last"] == ""
    later = round_views["eleven minutes later"]
    assert [node["pid"] for node in later["nodes"]] == [32813, 33993]
    assert all(chip["className"] == "chip" for chip in later["chips"])
    assert later["pod"] is True


def test_change_stream_matches_the_frozen_snapshot_at_each_cut(watcher, tmp_path):
    timed = timed_changes(watcher)
    for until in ("10.500", "11.000", "17.600", "21.060"):
        streamed = render(tmp_path, snapshot_at(watcher, START), [{"name": "s", "frames": frames_between(timed, START, at(until))}], wall_start=at(until))["s"]
        frozen = render(tmp_path, snapshot_at(watcher, at(until)), [{"name": "s"}], wall_start=at(until))["s"]
        for part in ("nodes", "paths", "labels", "chips", "toasts", "title", "pod"):
            assert streamed[part] == frozen[part], (until, part)
        assert streamed["caption"][0] == frozen["caption"][0]


def test_picking_a_chip_or_node_thickens_its_arrows_and_toggles_off(watcher, tmp_path):
    timed = timed_changes(watcher)
    steps = [
        {"name": "send", "frames": frames_between(timed, START, at("10.500"))},
        {"name": "pick chip", "clickChip": 32813},
        {"name": "unpick chip", "clickChip": 32813},
        {"name": "pick node", "clickNode": 33993},
        {"name": "hover toast", "hoverToast": 0},
        {"name": "leave toast", "leaveToast": 0},
        {"name": "error", "error": True},
        {"name": "reopen", "reopen": True},
    ]
    views = render(tmp_path, snapshot_at(watcher, START), steps)
    picked = views["pick chip"]
    assert chips_of(picked)[32813]["className"] == "chip on picked"
    assert set(nodes_of(picked)["fake manager"]["className"].split()) == {"node", "hot", "picked"}
    assert (only_path(picked)["width"], only_path(picked)["className"]) == ("2.4", "")
    unpicked = views["unpick chip"]
    assert chips_of(unpicked)[32813]["className"] == "chip on" and nodes_of(unpicked)["fake manager"]["className"] == "node hot"
    assert set(nodes_of(views["pick node"])["fake builder"]["className"].split()) == {"node", "hot", "picked"}
    hovered = views["hover toast"]
    assert hovered["toasts"][0]["className"] == "toast pend lit" and only_path(hovered)["width"] == "2.4"
    assert views["leave toast"]["toasts"][0]["className"] == "toast pend"
    assert (views["error"]["link"], views["error"]["linkClass"]) == ("reconnecting", "off")
    assert (views["reopen"]["link"], views["reopen"]["linkClass"]) == ("live", "")


def session(pid, label, cwd="/home/user/path_finder", role="r", status="IDLE", inbox=0, watching=(), last_seen_at="2026-10-20T12:00:05.000Z"):
    return {"pid": pid, "name": label, "role": role, "label": label, "cwd": cwd, "status": status, "inbox": inbox, "last_text": None, "watching": list(watching), "socket": f"uds:/tmp/cc-socks/{pid}.sock", "last_seen_at": last_seen_at}


def message(key, from_pid, to_pid, stage, summary, sent_at, body=None, reason=None, accepted_at=None, enqueued_at=None, read_at=None, kind="message"):
    return {"key": key, "pending_key": None, "msg_id": key, "kind": kind, "from_pid": from_pid, "to_pid": to_pid, "to": f"uds:/tmp/cc-socks/{to_pid}.sock", "summary": summary, "body": body or f"{summary} body line\nsecond line",
        "stage": stage, "reason": reason, "sent_at": sent_at, "accepted_at": accepted_at, "enqueued_at": enqueued_at, "read_at": read_at, "notify_when_idle": False, "tool_use_id": key}


def source(pid, label, seq, at="2026-10-20T12:00:05.000Z"):
    return {"pid": pid, "at": at, "source": label, "seq": seq}


TEN_START = "2026-10-20T12:00:05.000Z"


def ten_snapshot():
    labels = ["manager", "viz-builder", "validator", "discovery-builder", "e", "f", "g", "h", "i", "j", "stale"]
    sessions = [session(pid, label, cwd="/home/user/other" if pid > 6 else "/home/user/path_finder", status="WORKING" if pid == 3 else "IDLE", inbox=1 if pid == 2 else 0) for pid, label in enumerate(labels, start=1)]
    messages = [
        message("m1", 1, 2, "IN_INBOX", "one to two first", "2026-10-20T12:00:00.000Z", enqueued_at="2026-10-20T12:00:01.000Z"),
        message("m2", 1, 2, "PENDING", "one to two second", "2026-10-20T12:00:04.000Z"),
        message("m3", 3, 4, "FAILED", "three to four", "2026-10-20T11:59:50.000Z", reason="Not sent: refused", accepted_at="2026-10-20T11:59:51.000Z"),
        message("m4", 5, 6, "IN_INBOX", "five to six", "2026-10-20T11:59:55.000Z", enqueued_at="2026-10-20T11:59:56.000Z"),
        message("m5", 7, 8, "READ", "seven to eight", "2026-10-20T11:59:00.000Z", read_at="2026-10-20T11:59:30.000Z"),
        message("m6", 9, 10, "PENDING", "nine to ten", "2026-10-20T12:00:03.000Z"),
        message("m7", 11, 1, "READ", "stale to one", "2026-10-20T11:40:00.000Z", read_at="2026-10-20T11:40:30.000Z"),
    ]
    return {"generated_at": TEN_START, "sessions": sessions, "messages": messages, "sources": [source(1, "assistant → tool_use SendMessage", 7, "2026-10-20T12:00:04.000Z")]}


def test_ten_sessions_render_compact_with_pair_counts_failed_arrow_and_toast_overflow(tmp_path):
    resend = message("m8", 3, 4, "IN_INBOX", "three to four again", "2026-10-20T12:00:05.500Z", enqueued_at="2026-10-20T12:00:06.000Z")
    resend_frame = {"event": "message", "at": "2026-10-20T12:00:06.000Z", "source": "queue-operation · enqueue", "source_pid": 4, **resend}
    notice = message("idle:n1", 2, 1, "READ", "viz-builder is idle", "2026-10-20T12:00:06.500Z", read_at="2026-10-20T12:00:06.500Z", kind="idle_notice")
    notice_frame = {"event": "message", "at": "2026-10-20T12:00:06.500Z", "source": "user · cross-session idle notice", "source_pid": 1, **notice}
    steps = [
        {"name": "compact"},
        {"name": "pick validator", "clickChip": 3},
        {"name": "unpick", "clickChip": 3},
        {"name": "resend resolves the failure", "frames": [resend_frame]},
        {"name": "notice pulses the head eye", "frames": [notice_frame]},
        {"name": "after two seconds", "advanceMs": 2000},
    ]
    views = render(tmp_path, ten_snapshot(), steps, wall_start=TEN_START)
    compact = views["compact"]
    assert compact["title"] == "all folders · 11 sessions · 1 working · 5 in flight"
    assert compact["pod"] is False and compact["viewBox"] == "0 0 356 380"
    assert [node["pid"] for node in compact["nodes"]] == list(range(1, 11))
    assert all(node["className"].startswith("node compact") and node["width"] == "100px" and node["height"] == "24px" for node in compact["nodes"])
    assert nodes_of(compact)["viz-builder"]["count"] == "1"
    assert nodes_of(compact)["validator"]["dotClass"] == "dot work"
    assert nodes_of(compact)["manager"]["className"] == "node compact hot"
    paths = {path["key"]: path for path in compact["paths"]}
    assert set(paths) == {"1>2", "3>4", "5>6", "9>10"}
    assert (paths["1>2"]["stage"], paths["1>2"]["width"]) == ("PENDING", "2.4")
    assert (paths["3>4"]["stage"], paths["3>4"]["stroke"], paths["3>4"]["marker"], paths["3>4"]["width"]) == ("FAILED", FAILED_STROKE, "url(#mr)", "1.5")
    labels = {label["key"]: label for label in compact["labels"]}
    assert labels["1>2"]["summary"] == "one to two second +1" and labels["1>2"]["opacity"] == "1"
    assert [labels[key]["opacity"] for key in ("3>4", "5>6", "9>10")] == ["0", "0", "0"]
    assert labels["3>4"]["title"].startswith("FAILED: Not sent: refused")
    stale = chips_of(compact)[11]
    assert stale["className"] == "chip out" and stale["title"].endswith("no message in the last 10 min")
    assert all(chip["className"] in ("chip", "chip on", "chip hot") for pid, chip in chips_of(compact).items() if pid != 11)
    assert [toast["msg"] for toast in compact["toasts"][:3]] == ["m2", "m6", "m1"]
    assert compact["toasts"][3] == {"className": "more", "text": "+2 more"}
    assert compact["toasts"][0]["sum"] == "one to two second body line"
    picked = views["pick validator"]
    picked_paths = {path["key"]: path for path in picked["paths"]}
    assert (picked_paths["3>4"]["width"], picked_paths["3>4"]["className"]) == ("2.4", "")
    assert all(picked_paths[key]["className"] == "dim" for key in ("1>2", "5>6", "9>10"))
    assert {label["key"]: label["opacity"] for label in picked["labels"]}["3>4"] == "1"
    assert all(path["className"] == "" for path in views["unpick"]["paths"])
    resolved = views["resend resolves the failure"]
    resolved_paths = {path["key"]: path for path in resolved["paths"]}
    assert (resolved_paths["3>4"]["stage"], resolved_paths["3>4"]["stroke"]) == ("IN_INBOX", OK_STROKE)
    assert "m3" not in [toast.get("msg") for toast in resolved["toasts"]]
    assert resolved["caption"] == ["queue-operation · enqueue", "validator → discovery-builder"]
    pulsing = views["notice pulses the head eye"]
    assert nodes_of(pulsing)["manager"]["headEye"] == "eye pulse"
    assert pulsing["toasts"][0]["className"] == "toast notice" and pulsing["toasts"][0]["from"] == "viz-builderidle notice tomanager"
    assert "1>2" in {path["key"] for path in pulsing["paths"]} and "2>1" not in {path["key"] for path in pulsing["paths"]}
    assert nodes_of(views["after two seconds"])["manager"]["headEye"] is None


def test_ring_drops_sessions_without_recent_traffic_and_falls_back_to_everyone(tmp_path):
    sessions = [session(1, "a"), session(2, "b"), session(3, "c")]
    recent = [message("m1", 1, 2, "READ", "a to b", "2026-10-20T11:59:00.000Z", read_at="2026-10-20T11:59:30.000Z")]
    views = render(tmp_path, {"generated_at": TEN_START, "sessions": sessions, "messages": recent, "sources": []}, [{"name": "now"}, {"name": "later", "advanceMs": 11 * 60 * 1000}], wall_start=TEN_START)
    now = views["now"]
    assert [node["pid"] for node in now["nodes"]] == [1, 2] and now["pod"] is True
    assert chips_of(now)[3]["className"] == "chip out"
    later = views["later"]
    assert [node["pid"] for node in later["nodes"]] == [1, 2, 3] and later["pod"] is False
    assert all(chip["className"] == "chip" for chip in later["chips"])


def test_watching_keeps_a_session_in_the_ring_and_unidentified_nodes_are_dashed(tmp_path):
    sessions = [session(1, "a", watching=[3]), session(2, "b"), session(3, "c", role=None)]
    views = render(tmp_path, {"generated_at": TEN_START, "sessions": sessions, "messages": [], "sources": [source(2, "registry", 1)]}, [{"name": "now"}], wall_start=TEN_START)["now"]
    assert [node["pid"] for node in views["nodes"]] == [1, 3]
    assert nodes_of(views)["a"]["last"] == "👁 Watching c"
    assert nodes_of(views)["c"]["className"] == "node incomplete"
    assert views["caption"] == ["registry", "b"]
    assert views["title"] == "path_finder · 3 sessions · 0 working · 0 in flight"


def test_empty_snapshot_and_snapshot_event_on_the_stream(tmp_path):
    replacement = {"event": "snapshot", "generated_at": TEN_START, "sessions": [session(5, "only")], "messages": [], "sources": [source(5, "registry", 1)]}
    views = render(tmp_path, {"generated_at": TEN_START, "sessions": [], "messages": [], "sources": []}, [{"name": "empty"}, {"name": "replaced", "frames": [replacement]}], wall_start=TEN_START)
    assert views["empty"]["title"] == "No sessions discovered yet" and views["empty"]["quiet"] == "No sessions discovered yet"
    assert views["empty"]["nodes"] == [] and views["empty"]["chips"] == []
    assert [node["name"] for node in views["replaced"]["nodes"]] == ["only"] and views["replaced"]["quiet"] is None
    assert views["replaced"]["caption"] == ["registry", "only"]
