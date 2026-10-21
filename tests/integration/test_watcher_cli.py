import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from conftest import WATCHER_SCRIPT

ROOT = "/home/user/path_finder"
FAKE_ROOT = f"{ROOT}/fake_session"


def encoded(cwd):
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


@pytest.fixture
def sandbox(tmp_path):
    home = tmp_path / "home"
    sessions_dir = home / ".claude" / "sessions"
    projects_dir = home / ".claude" / "projects"
    viz_dir = tmp_path / "repo" / "viz"
    identity_dir = tmp_path / "repo" / "discovery" / "identity"
    for folder in (sessions_dir, projects_dir, viz_dir, identity_dir):
        folder.mkdir(parents=True)
    shutil.copy(WATCHER_SCRIPT, viz_dir / "watcher.py")
    (tmp_path / "repo" / "pyproject.toml").write_text("")
    return {"home": home, "sessions_dir": sessions_dir, "projects_dir": projects_dir, "viz_dir": viz_dir, "identity_dir": identity_dir, "pyproject": tmp_path / "repo" / "pyproject.toml"}


def run_map(sandbox, *args, data_home=None):
    env = {**os.environ, "HOME": str(sandbox["home"])}
    env.pop("PATH_FINDER_HOME", None)
    if data_home is not None:
        env["PATH_FINDER_HOME"] = str(data_home)
    return subprocess.run([sys.executable, "-I", str(sandbox["viz_dir"] / "watcher.py"), "map", *args], capture_output=True, text=True, env=env)


def register(sandbox, pid, name, cwd, session_id, started_at_ms=1_791_349_700_855):
    (sandbox["sessions_dir"] / f"{pid}.json").write_text(json.dumps({"pid": pid, "name": name, "cwd": cwd, "sessionId": session_id, "startedAt": started_at_ms}))


def write_transcript(sandbox, cwd, session_id):
    folder = sandbox["projects_dir"] / encoded(cwd)
    folder.mkdir(exist_ok=True)
    path = folder / f"{session_id}.jsonl"
    path.write_text(json.dumps({"type": "user", "sessionId": session_id, "cwd": cwd}) + "\n")
    return path


def test_map_prints_pid_session_id_and_transcript_for_two_fake_sessions(sandbox):
    first = subprocess.Popen(["sleep", "30"])
    second = subprocess.Popen(["sleep", "30"])
    try:
        ids = {first.pid: "aaaaaaaa-0000-0000-0000-000000000001", second.pid: "bbbbbbbb-0000-0000-0000-000000000002"}
        register(sandbox, first.pid, "fake-session-manager", FAKE_ROOT, ids[first.pid])
        register(sandbox, second.pid, "fake-session-builder", FAKE_ROOT, ids[second.pid])
        paths = {pid: write_transcript(sandbox, FAKE_ROOT, sid) for pid, sid in ids.items()}
        (sandbox["identity_dir"] / f"{first.pid}.json").write_text(json.dumps({"role": "fake manager", "label": "fake manager"}))

        result = run_map(sandbox, "--root", FAKE_ROOT)
        assert result.returncode == 0, result.stderr
        rows = [line.split("\t") for line in result.stdout.splitlines()]
        assert sorted(int(r[0]) for r in rows) == sorted(ids)
        for pid_text, session_id, transcript, label, method in rows:
            pid = int(pid_text)
            assert session_id == ids[pid]
            assert transcript == str(paths[pid])
            assert method == "registry sessionId"
        labels = {int(r[0]): r[3] for r in rows}
        assert labels[first.pid] == "fake manager"
        assert labels[second.pid] == "fake-session-builder"

        as_json = run_map(sandbox, "--root", FAKE_ROOT, "--json")
        assert as_json.returncode == 0
        assert {row["pid"] for row in json.loads(as_json.stdout)} == set(ids)
    finally:
        for child in (first, second):
            child.terminate()
            child.wait()


def test_map_exit_1_when_transcript_missing(sandbox):
    register(sandbox, os.getpid(), "me", FAKE_ROOT, "cccccccc-0000-0000-0000-000000000003")
    result = run_map(sandbox, "--root", FAKE_ROOT)
    assert result.returncode == 1
    assert "transcript not written yet" in result.stdout


def test_map_fallback_without_session_id_resolves_single_transcript(sandbox):
    (sandbox["sessions_dir"] / f"{os.getpid()}.json").write_text(json.dumps({"pid": os.getpid(), "name": "me", "cwd": FAKE_ROOT, "startedAt": 0}))
    path = write_transcript(sandbox, FAKE_ROOT, "dddddddd-0000-0000-0000-000000000004")
    result = run_map(sandbox, "--root", FAKE_ROOT)
    assert result.returncode == 0, result.stderr
    fields = result.stdout.rstrip("\n").split("\t")
    assert fields[1] == "dddddddd-0000-0000-0000-000000000004"
    assert fields[2] == str(path)
    assert fields[4] == "cwd folder, single transcript since start"


def test_map_ignores_dead_pids(sandbox):
    child = subprocess.Popen(["true"])
    child.wait()
    register(sandbox, child.pid, "gone", FAKE_ROOT, "eeeeeeee-0000-0000-0000-000000000005")
    result = run_map(sandbox, "--root", FAKE_ROOT)
    assert result.stdout == ""


def test_map_reads_identity_from_the_data_directory_rule(sandbox):
    child = subprocess.Popen(["sleep", "30"])
    try:
        register(sandbox, child.pid, "fake-session-manager", FAKE_ROOT, "cccccccc-0000-0000-0000-000000000003")
        write_transcript(sandbox, FAKE_ROOT, "cccccccc-0000-0000-0000-000000000003")
        (sandbox["identity_dir"] / f"{child.pid}.json").write_text(json.dumps({"role": "fake manager", "label": "fake manager"}))
        label_of = lambda result: {int(line.split("\t")[0]): line.split("\t")[3] for line in result.stdout.splitlines()}[child.pid]
        assert label_of(run_map(sandbox, "--root", FAKE_ROOT)) == "fake manager"
        sandbox["pyproject"].unlink()
        assert label_of(run_map(sandbox, "--root", FAKE_ROOT)) == "fake-session-manager"
        assert label_of(run_map(sandbox, "--root", FAKE_ROOT, data_home=sandbox["identity_dir"].parent)) == "fake manager"
        elsewhere = sandbox["home"] / ".path_finder" / "identity"
        elsewhere.mkdir(parents=True)
        (elsewhere / f"{child.pid}.json").write_text(json.dumps({"role": "home manager", "label": "home manager"}))
        assert label_of(run_map(sandbox, "--root", FAKE_ROOT)) == "home manager"
        assert label_of(run_map(sandbox, "--root", FAKE_ROOT, data_home=sandbox["identity_dir"].parent)) == "fake manager"
    finally:
        child.kill()
        child.wait()
