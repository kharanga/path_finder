import json
import os
import select
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from conftest import FIXTURES_DIR, WATCHER_SCRIPT

MANAGER_FIXTURE = FIXTURES_DIR / "viz" / "round_trip_manager_32813_33993.jsonl"
BUILDER_FIXTURE = FIXTURES_DIR / "viz" / "round_trip_builder_32813_33993.jsonl"


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def sandbox(tmp_path):
    home = tmp_path / "home"
    sessions_dir = home / ".claude" / "sessions"
    projects_dir = home / ".claude" / "projects"
    repo = tmp_path / "repo"
    viz_dir = repo / "viz"
    discovery_dir = repo / "discovery"
    for folder in (sessions_dir, projects_dir, viz_dir, discovery_dir / "identity"):
        folder.mkdir(parents=True)
    shutil.copy(WATCHER_SCRIPT, viz_dir / "watcher.py")
    (discovery_dir / "index.html").write_text("<!doctype html><title>d2</title>")
    (discovery_dir / "sessions.json").write_text('{"updated_at": "x", "sessions": []}')
    return {"home": home, "sessions_dir": sessions_dir, "projects_dir": projects_dir, "script": viz_dir / "watcher.py", "viz_dir": viz_dir}


def start_server(sandbox, *args):
    port = free_port()
    env = {**os.environ, "HOME": str(sandbox["home"])}
    process = subprocess.Popen([sys.executable, "-I", str(sandbox["script"]), "serve", "--port", str(port), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{base}/state", timeout=0.5)
            return process, base
        except OSError:
            if process.poll() is not None:
                raise AssertionError(process.stderr.read().decode())
            time.sleep(0.05)
    process.kill()
    raise AssertionError("server did not come up")


def stop(process):
    process.terminate()
    process.wait(timeout=5)


def get(url):
    with urllib.request.urlopen(url, timeout=2) as response:
        return response.status, response.headers, response.read()


def open_event_stream(base):
    sock = socket.create_connection(("127.0.0.1", int(base.rsplit(":", 1)[1])), timeout=5)
    sock.sendall(b"GET /events HTTP/1.1\r\nHost: localhost\r\n\r\n")
    return sock


def read_frames(sock, count, seconds):
    deadline = time.monotonic() + seconds
    buffer = b""
    frames = []
    while time.monotonic() < deadline and len(frames) < count:
        ready, _, _ = select.select([sock], [], [], max(0.0, deadline - time.monotonic()))
        if not ready:
            continue
        chunk = sock.recv(65536)
        if not chunk:
            break
        buffer += chunk
        while b"\n\n" in buffer:
            frame, buffer = buffer.split(b"\n\n", 1)
            for line in frame.split(b"\n"):
                if line.startswith(b"data: "):
                    frames.append(json.loads(line[6:]))
    return frames


@pytest.fixture
def fixture_copies(tmp_path):
    manager = tmp_path / "m.jsonl"
    builder = tmp_path / "b.jsonl"
    manager.write_text(MANAGER_FIXTURE.read_text())
    builder.write_text(BUILDER_FIXTURE.read_text())
    return manager, builder


def test_state_returns_both_sessions_and_messages(sandbox, fixture_copies):
    manager, builder = fixture_copies
    process, base = start_server(sandbox, "--fixture", f"32813={manager}", "--fixture", f"33993={builder}")
    try:
        status, headers, body = get(f"{base}/state")
        assert status == 200
        assert headers["Content-Type"] == "application/json"
        assert headers["Cache-Control"] == "no-store"
        snapshot = json.loads(body)
        assert [s["pid"] for s in snapshot["sessions"]] == [32813, 33993]
        assert [(m["kind"], m["stage"]) for m in snapshot["messages"]] == [("message", "READ"), ("message", "READ"), ("idle_notice", "READ")]
        assert snapshot["generated_at"].endswith("Z")
    finally:
        stop(process)


def test_events_streams_snapshot_then_change_within_one_second(sandbox, fixture_copies):
    manager, builder = fixture_copies
    process, base = start_server(sandbox, "--fixture", f"32813={manager}", "--fixture", f"33993={builder}")
    try:
        stream = open_event_stream(base)
        first = read_frames(stream, 1, 3)
        assert first[0]["event"] == "snapshot"
        assert [s["pid"] for s in first[0]["sessions"]] == [32813, 33993]
        appended_at = time.monotonic()
        with open(builder, "a") as handle:
            handle.write(json.dumps({"type": "assistant", "timestamp": "2026-10-08T05:00:01.000Z", "message": {"content": [{"type": "text", "text": "hi"}]}}) + "\n")
        change = read_frames(stream, 1, 1.0)
        elapsed = time.monotonic() - appended_at
        assert change, "no change frame within 1 s"
        assert elapsed < 1.0
        assert (change[0]["event"], change[0]["pid"], change[0]["status"]) == ("session", 33993, "WORKING")
        with open(builder, "a") as handle:
            handle.write(json.dumps({"type": "system", "subtype": "turn_duration", "timestamp": "2026-10-08T05:00:02.000Z"}) + "\n")
        idle = read_frames(stream, 1, 1.0)
        assert idle[0]["status"] == "IDLE"
        stream.close()
    finally:
        stop(process)


def test_events_response_headers(sandbox, fixture_copies):
    manager, builder = fixture_copies
    process, base = start_server(sandbox, "--fixture", f"32813={manager}", "--fixture", f"33993={builder}")
    try:
        stream = open_event_stream(base)
        head = b""
        while b"\r\n\r\n" not in head:
            head += stream.recv(4096)
        header_text = head.split(b"\r\n\r\n", 1)[0].decode().lower()
        assert "200" in header_text.splitlines()[0]
        assert "content-type: text/event-stream" in header_text
        assert "cache-control: no-store" in header_text
        stream.close()
    finally:
        stop(process)


def test_static_files_come_from_viz_only_and_web_route_serves_the_compact_page(sandbox, fixture_copies):
    manager, builder = fixture_copies
    shutil.copy(WATCHER_SCRIPT.parent / "index.html", sandbox["viz_dir"] / "index.html")
    shutil.copy(WATCHER_SCRIPT.parent / "web.html", sandbox["viz_dir"] / "web.html")
    (sandbox["viz_dir"] / "app.js").write_text("console.log(1)")
    process, base = start_server(sandbox, "--fixture", f"32813={manager}", "--fixture", f"33993={builder}")
    try:
        status, headers, body = get(f"{base}/")
        assert status == 200 and "text/html" in headers["Content-Type"] and b"<title>Session Messages</title>" in body
        for route in ("/web", "/web.html"):
            status, headers, body = get(f"{base}{route}")
            assert status == 200 and "text/html" in headers["Content-Type"] and b"<title>Session Web</title>" in body
        status, _, body = get(f"{base}/app.js")
        assert status == 200 and body == b"console.log(1)"
        for missing_route in ("/sessions.json", "/index.html.bak", "/identity/32813.json", "/nope.txt", "/../home/.claude/sessions/"):
            with pytest.raises(urllib.error.HTTPError) as missing:
                get(f"{base}{missing_route}")
            assert missing.value.code == 404, missing_route
    finally:
        stop(process)


def test_registry_mode_adds_live_session_and_removes_it_on_exit(sandbox):
    cwd = "/home/user/path_finder/fake_session"
    encoded = "-home-user-path-finder-fake-session"
    folder = sandbox["projects_dir"] / encoded
    folder.mkdir()
    child = subprocess.Popen(["sleep", "30"])
    try:
        (sandbox["sessions_dir"] / f"{child.pid}.json").write_text(json.dumps({"pid": child.pid, "name": "fake-one", "cwd": cwd, "sessionId": "sid-one"}))
        (folder / "sid-one.jsonl").write_text(json.dumps({"type": "agent-name", "agentName": "fake-one"}) + "\n")
        process, base = start_server(sandbox, "--root", "/home/user/path_finder")
        try:
            deadline = time.monotonic() + 2
            sessions = []
            while time.monotonic() < deadline and not sessions:
                sessions = json.loads(get(f"{base}/state")[2])["sessions"]
                time.sleep(0.1)
            assert [(s["pid"], s["name"]) for s in sessions] == [(child.pid, "fake-one")]
            stream = open_event_stream(base)
            read_frames(stream, 1, 3)
            child.terminate()
            child.wait()
            removed = read_frames(stream, 1, 2.0)
            assert removed and (removed[0]["event"], removed[0]["pid"]) == ("session_removed", child.pid)
            assert json.loads(get(f"{base}/state")[2])["sessions"] == []
            stream.close()
        finally:
            stop(process)
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait()


def test_bind_failure_exits_1(sandbox):
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    port = holder.getsockname()[1]
    try:
        env = {**os.environ, "HOME": str(sandbox["home"])}
        result = subprocess.run([sys.executable, "-I", str(sandbox["script"]), "serve", "--port", str(port)], capture_output=True, text=True, env=env, timeout=10)
        assert result.returncode == 1
        assert f"cannot bind 127.0.0.1:{port}" in result.stderr
    finally:
        holder.close()


def test_event_log_written_during_the_v3_style_test(sandbox, fixture_copies):
    manager, builder = fixture_copies
    log_path = sandbox["viz_dir"].parent / "events.jsonl"
    process, base = start_server(sandbox, "--fixture", f"32813={manager}", "--fixture", f"33993={builder}", "--log", str(log_path))
    try:
        get(f"{base}/state")
        stream = open_event_stream(base)
        read_frames(stream, 1, 3)
        with open(builder, "a") as handle:
            handle.write(json.dumps({"type": "assistant", "timestamp": "2026-10-08T05:00:01.000Z", "message": {"content": [{"type": "text", "text": "hi"}]}}) + "\n")
        change = read_frames(stream, 1, 1.0)
        assert change and change[0]["status"] == "WORKING"
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and not log_path.exists():
            time.sleep(0.05)
        lines = [json.loads(l) for l in log_path.read_text().splitlines()]
        assert lines[-1] == change[0]
        assert len(lines) == 2 + 30 + 1
        assert all({"event", "at"} <= set(line) for line in lines)
        stream.close()
    finally:
        stop(process)
    first_run = len(log_path.read_text().splitlines())
    process, base = start_server(sandbox, "--fixture", f"32813={manager}", "--fixture", f"33993={builder}", "--log", str(log_path))
    stop(process)
    assert len(log_path.read_text().splitlines()) == first_run * 2


def test_default_log_is_next_to_the_script_and_no_log_disables_it(sandbox, fixture_copies):
    manager, builder = fixture_copies
    default_log = sandbox["viz_dir"] / "events.jsonl"
    process, _ = start_server(sandbox, "--fixture", f"32813={manager}", "--fixture", f"33993={builder}")
    stop(process)
    assert default_log.exists() and len(default_log.read_text().splitlines()) == 32
    default_log.unlink()
    process, _ = start_server(sandbox, "--fixture", f"32813={manager}", "--fixture", f"33993={builder}", "--no-log")
    stop(process)
    assert not default_log.exists()


def read_sse_frames(sock, want, timeout=3.0):
    sock.settimeout(0.2)
    buffer = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            buffer += sock.recv(65536)
        except socket.timeout:
            pass
        frames = [json.loads(line[5:]) for line in buffer.decode().splitlines() if line.startswith("data:")]
        if want(frames):
            return frames
    return [json.loads(line[5:]) for line in buffer.decode().splitlines() if line.startswith("data:")]


def test_serve_spec_exposes_tasks_and_streams_an_edit_within_a_second(sandbox, fixture_copies):
    manager, builder = fixture_copies
    spec = sandbox["home"] / "SPEC.md"
    spec.write_text("## Tasks\n- [x] V8: web window follow-ups. Done.\n- [~] V9: task panel. A side panel.\n")
    process, base = start_server(sandbox, "--fixture", f"32813={manager}", "--fixture", f"33993={builder}", "--spec", str(spec))
    try:
        _, _, body = get(f"{base}/state")
        state = json.loads(body)
        assert set(state) >= {"tasks", "task_counts", "spec_path"}
        assert state["spec_path"] == str(spec) and state["task_counts"] == {"done": 1, "in_progress": 1, "todo": 0}
        assert [(t["id"], t["state"], t["title"], t["owner"]) for t in state["tasks"]] == [("V8", "done", "web window follow-ups", "viz-builder"), ("V9", "in_progress", "task panel", "viz-builder")]
        sock = socket.create_connection(("127.0.0.1", int(base.rsplit(":", 1)[1])), timeout=5)
        sock.sendall(b"GET /events HTTP/1.1\r\nHost: x\r\nAccept: text/event-stream\r\n\r\n")
        frames = read_sse_frames(sock, lambda frames: len(frames) >= 1)
        assert frames[0]["event"] == "snapshot" and frames[0]["task_counts"] == {"done": 1, "in_progress": 1, "todo": 0}
        assert all(frame["event"] != "tasks" for frame in frames)
        started = time.monotonic()
        spec.write_text("## Tasks\n- [ ] V8: web window follow-ups. Done.\n- [x] V9: task panel. A side panel.\n")
        frames = read_sse_frames(sock, lambda frames: any(frame["event"] == "tasks" for frame in frames))
        elapsed = time.monotonic() - started
        tasks_frames = [frame for frame in frames if frame["event"] == "tasks"]
        assert len(tasks_frames) == 1 and elapsed < 1.0, elapsed
        assert [(t["id"], t["state"]) for t in tasks_frames[0]["tasks"]] == [("V8", "todo"), ("V9", "done")]
        assert tasks_frames[0]["task_counts"] == {"done": 1, "in_progress": 0, "todo": 1} and tasks_frames[0]["source"] == "spec"
        _, _, body = get(f"{base}/state")
        assert json.loads(body)["task_counts"] == {"done": 1, "in_progress": 0, "todo": 1}
        spec.write_text(spec.read_text())
        assert all(frame["event"] != "tasks" for frame in read_sse_frames(sock, lambda frames: False, timeout=0.8))
        sock.close()
    finally:
        stop(process)


def test_serve_without_a_spec_file_serves_empty_tasks(sandbox, fixture_copies):
    manager, builder = fixture_copies
    process, base = start_server(sandbox, "--fixture", f"32813={manager}", "--fixture", f"33993={builder}", "--spec", str(sandbox["home"] / "missing.md"))
    try:
        state = json.loads(get(f"{base}/state")[2])
        assert (state["tasks"], state["task_counts"]) == ([], {"done": 0, "in_progress": 0, "todo": 0})
    finally:
        stop(process)
