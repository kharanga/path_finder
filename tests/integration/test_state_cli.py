import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import FIXTURES_DIR, WATCHER_SCRIPT

MANAGER_FIXTURE = FIXTURES_DIR / "viz" / "round_trip_manager_32813_33993.jsonl"
BUILDER_FIXTURE = FIXTURES_DIR / "viz" / "round_trip_builder_32813_33993.jsonl"


@pytest.fixture
def sandbox(tmp_path):
    home = tmp_path / "home"
    (home / ".claude" / "sessions").mkdir(parents=True)
    (home / ".claude" / "projects").mkdir(parents=True)
    viz_dir = tmp_path / "repo" / "viz"
    viz_dir.mkdir(parents=True)
    (tmp_path / "repo" / "discovery" / "identity").mkdir(parents=True)
    shutil.copy(WATCHER_SCRIPT, viz_dir / "watcher.py")
    return {"home": home, "script": viz_dir / "watcher.py"}


def run_state(sandbox, *args):
    env = {**os.environ, "HOME": str(sandbox["home"])}
    return subprocess.run([sys.executable, "-I", str(sandbox["script"]), "state", *args], capture_output=True, text=True, env=env)


def test_state_snapshot_from_fixtures(sandbox):
    result = run_state(sandbox, f"32813={MANAGER_FIXTURE}", f"33993={BUILDER_FIXTURE}")
    assert result.returncode == 0, result.stderr
    snapshot = json.loads(result.stdout)
    assert [(m["kind"], m["stage"], m["from_pid"], m["to_pid"]) for m in snapshot["messages"]] == [
        ("message", "READ", 32813, 33993),
        ("message", "READ", 33993, 32813),
        ("idle_notice", "READ", 33993, 32813),
    ]
    assert [m["read_at"] for m in snapshot["messages"]] == ["2026-10-08T04:31:11.097Z", "2026-10-08T04:31:17.638Z", "2026-10-08T04:31:21.055Z"]
    assert [(s["pid"], s["status"], s["inbox"], s["watching"], s["name"]) for s in snapshot["sessions"]] == [
        (32813, "IDLE", 0, [], "fake-session-manager"),
        (33993, "IDLE", 0, [], "fake-session-builder"),
    ]


def test_state_events_stream(sandbox):
    result = run_state(sandbox, f"32813={MANAGER_FIXTURE}", f"33993={BUILDER_FIXTURE}", "--events")
    assert result.returncode == 0, result.stderr
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(lines) == 23
    assert all(line["event"] in ("session", "message") and "at" in line for line in lines)
    assert lines[0]["watching"] == ["fake-session-builder"]
    final_manager = [l for l in lines if l["event"] == "session" and l["pid"] == 32813][-1]
    assert final_manager["watching"] == []


def test_state_rejects_bad_fixture_argument(sandbox):
    result = run_state(sandbox, "notapid=/x.jsonl")
    assert result.returncode == 2
    assert "expected PID=PATH" in result.stderr
