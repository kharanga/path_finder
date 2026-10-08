import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import DISCOVER_SCRIPT, dead_pid

ROOT = "/home/user/path_finder"
FAKE_ROOT = f"{ROOT}/fake_session"


@pytest.fixture
def sandbox(tmp_path):
    home = tmp_path / "home"
    sessions_dir = home / ".claude" / "sessions"
    sessions_dir.mkdir(parents=True)
    discovery_dir = tmp_path / "discovery"
    discovery_dir.mkdir()
    shutil.copy(DISCOVER_SCRIPT, discovery_dir / "discover.py")
    return {"home": home, "sessions_dir": sessions_dir, "discovery_dir": discovery_dir}


def run_cli(sandbox, *args):
    env = {**os.environ, "HOME": str(sandbox["home"])}
    return subprocess.run(
        [sys.executable, "-I", str(sandbox["discovery_dir"] / "discover.py"), *args],
        capture_output=True, text=True, env=env,
    )


def register(sandbox, pid, name, cwd):
    (sandbox["sessions_dir"] / f"{pid}.json").write_text(json.dumps({"pid": pid, "name": name, "cwd": cwd, "sessionId": f"sid-{pid}"}))


def identify_on_disk(sandbox, pid, role):
    identity_dir = sandbox["discovery_dir"] / "identity"
    identity_dir.mkdir(exist_ok=True)
    (identity_dir / f"{pid}.json").write_text(json.dumps({"pid": pid, "role": role, "label": role, "identified_at": "2026-10-08T00:00:00Z"}))


def rows_of(result):
    return [json.loads(line) for line in result.stdout.splitlines()]


def test_two_sessions_listed_with_roles_then_one_exit_removes_it(sandbox):
    keeper = subprocess.Popen(["sleep", "30"])
    leaver = subprocess.Popen(["sleep", "30"])
    try:
        register(sandbox, keeper.pid, "fake-session-manager", FAKE_ROOT)
        register(sandbox, leaver.pid, "fake-session-builder", FAKE_ROOT)
        register(sandbox, os.getpid(), "outside-root", "/elsewhere")
        identify_on_disk(sandbox, keeper.pid, "fake manager")
        identify_on_disk(sandbox, leaver.pid, "fake builder")

        listed = run_cli(sandbox, "list", "--root", FAKE_ROOT)
        assert listed.returncode == 0, listed.stderr
        rows = rows_of(listed)
        assert sorted(r["pid"] for r in rows) == sorted([keeper.pid, leaver.pid])
        assert {r["role"] for r in rows} == {"fake manager", "fake builder"}
        assert all(r["identified"] for r in rows)
        assert all(r["socket"] == f"uds:/tmp/cc-socks/{r['pid']}.sock" for r in rows)
        assert all(r["session_id"] == f"sid-{r['pid']}" for r in rows)

        done = run_cli(sandbox, "done", "--root", FAKE_ROOT)
        assert done.returncode == 0, done.stderr

        directory = json.loads((sandbox["discovery_dir"] / "sessions.json").read_text())
        assert sorted(s["pid"] for s in directory["sessions"]) == sorted([keeper.pid, leaver.pid, os.getpid()])

        leaver.terminate()
        leaver.wait()

        relisted = run_cli(sandbox, "list", "--root", FAKE_ROOT)
        assert [r["pid"] for r in rows_of(relisted)] == [keeper.pid]
        assert not (sandbox["discovery_dir"] / "identity" / f"{leaver.pid}.json").exists()
        assert (sandbox["discovery_dir"] / "identity" / f"{keeper.pid}.json").exists()
    finally:
        for child in (keeper, leaver):
            if child.poll() is None:
                child.terminate()
                child.wait()


def test_unidentified_session_is_marked_and_fails_done(sandbox):
    register(sandbox, os.getpid(), "fresh-session", FAKE_ROOT)
    listed = run_cli(sandbox, "list", "--root", FAKE_ROOT)
    rows = rows_of(listed)
    assert rows[0]["identified"] is False
    assert rows[0]["role"] is None and rows[0]["label"] is None
    done = run_cli(sandbox, "done", "--root", FAKE_ROOT)
    assert done.returncode == 1
    assert f"fresh-session (pid {os.getpid()})" in done.stderr


def test_stale_identity_of_dead_pid_is_dropped(sandbox):
    stale = dead_pid()
    identify_on_disk(sandbox, stale, "ghost")
    listed = run_cli(sandbox, "list", "--root", FAKE_ROOT)
    assert listed.returncode == 0
    assert listed.stdout == ""
    assert not (sandbox["discovery_dir"] / "identity" / f"{stale}.json").exists()


@pytest.mark.parametrize("removed", ["record", "protocol"])
def test_removed_commands_exit_2(sandbox, removed):
    result = run_cli(sandbox, removed)
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_self_exits_1_when_registry_has_no_entry_for_caller(sandbox):
    result = run_cli(sandbox, "self")
    assert result.returncode == 1
    assert "not running inside a Claude Code session" in result.stderr
    assert result.stdout == ""
