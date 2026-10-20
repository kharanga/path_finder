import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
DISCOVER_SCRIPT = REPO_ROOT / "discovery" / "discover.py"
WATCHER_SCRIPT = REPO_ROOT / "viz" / "watcher.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_discover_module():
    return load_module_from_path("discover_under_test", DISCOVER_SCRIPT)


def load_watcher_module():
    return load_module_from_path("watcher_under_test", WATCHER_SCRIPT)


def dead_pid():
    child = subprocess.Popen(["true"])
    child.wait()
    return child.pid


@pytest.fixture
def discover(tmp_path, monkeypatch):
    module = load_discover_module()
    sessions_dir = tmp_path / "home" / ".claude" / "sessions"
    discovery_dir = tmp_path / "discovery"
    sessions_dir.mkdir(parents=True)
    discovery_dir.mkdir()
    monkeypatch.setattr(module, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(module, "DISCOVERY_DIR", discovery_dir)
    monkeypatch.setattr(module, "DIRECTORY_PATH", discovery_dir / "sessions.json")
    monkeypatch.setattr(module, "IDENTITY_DIR", discovery_dir / "identity")
    return module


@pytest.fixture
def live_pid():
    return os.getpid()


@pytest.fixture
def gone_pid():
    return dead_pid()


@pytest.fixture
def write_registry_entry(discover):
    def write(pid, name, cwd, session_id="00000000-0000-0000-0000-000000000000"):
        entry = {"pid": pid, "name": name, "cwd": cwd, "sessionId": session_id}
        path = discover.SESSIONS_DIR / f"{pid}.json"
        path.write_text(json.dumps(entry))
        return path
    return write


@pytest.fixture
def write_identity_file(discover):
    def write(pid, role, label=None, stamp_field="identified_at"):
        discover.IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
        identity = {"pid": pid, "role": role, "label": label or role, stamp_field: "2026-10-08T00:00:00Z"}
        path = discover.IDENTITY_DIR / f"{pid}.json"
        path.write_text(json.dumps(identity))
        return path
    return write


@pytest.fixture
def watcher(tmp_path, monkeypatch):
    module = load_watcher_module()
    sessions_dir = tmp_path / "home" / ".claude" / "sessions"
    projects_dir = tmp_path / "home" / ".claude" / "projects"
    identity_dir = tmp_path / "discovery" / "identity"
    for folder in (sessions_dir, projects_dir, identity_dir):
        folder.mkdir(parents=True)
    monkeypatch.setattr(module, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(module, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(module, "IDENTITY_DIR", identity_dir)
    return module
