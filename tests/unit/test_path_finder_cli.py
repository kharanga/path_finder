import json
import os
import socket
import stat
import subprocess
import sys
import time
import urllib.request

import pytest

from conftest import FIXTURES_DIR, REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))

from path_finder import cli, repo, window  # noqa: E402

MANAGER_FIXTURE = FIXTURES_DIR / "viz" / "round_trip_manager_32813_33993.jsonl"


def make_repo(folder):
    for relative in repo.REQUIRED_FILES:
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    return folder


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_find_repo_prefers_the_environment_variable(tmp_path, monkeypatch):
    other = make_repo(tmp_path / "other")
    monkeypatch.setenv(repo.REPO_ENV_VAR, str(other))
    assert repo.find_repo() == other
    assert repo.discover_script(other) == other / "discovery" / "discover.py" and repo.watcher_script(other) == other / "viz" / "watcher.py"


def test_find_repo_falls_back_to_the_package_checkout_then_the_working_directory_parents(tmp_path, monkeypatch):
    monkeypatch.delenv(repo.REPO_ENV_VAR, raising=False)
    assert repo.find_repo() == REPO_ROOT
    nested = make_repo(tmp_path / "checkout") / "deep" / "inside"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.setattr(repo, "candidate_folders", lambda: iter([nested, nested.parent, nested.parent.parent]))
    assert repo.find_repo() == tmp_path / "checkout"


def test_find_repo_without_a_checkout_raises_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv(repo.REPO_ENV_VAR, str(tmp_path / "missing"))
    monkeypatch.setattr(repo, "candidate_folders", lambda: iter([tmp_path / "missing", tmp_path]))
    with pytest.raises(repo.RepoNotFound, match="PATH_FINDER_REPO"):
        repo.find_repo()


@pytest.mark.parametrize("command, arguments, expected", [
    ("list", [], ["--root", "CWD"]),
    ("done", ["--quiet"], ["--quiet", "--root", "CWD"]),
    ("serve", ["--port", "4797"], ["--port", "4797", "--root", "CWD"]),
    ("map", [], ["--root", "CWD"]),
    ("serve", ["--root", "/x"], ["--root", "/x"]),
    ("list", ["--root=/x"], ["--root=/x"]),
    ("state", ["1=a.jsonl"], ["1=a.jsonl"]),
    ("self", [], []),
    ("tail", ["1=a.jsonl"], ["1=a.jsonl"]),
])
def test_default_root_is_added_only_for_commands_that_take_it(command, arguments, expected, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cwd = os.getcwd()
    assert cli.with_default_root(command, arguments) == [cwd if part == "CWD" else part for part in expected]


def test_help_and_unknown_commands(capsys):
    assert cli.main([]) == 0 and cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert out.count("usage: path-finder <command> [arguments]") == 2 and "identify  self  list  done" in out and "serve  state  replay  map  tail" in out and "window [--port 4780] [--page web] [--root DIR]" in out
    assert cli.main(["frobnicate"]) == 2
    err = capsys.readouterr().err
    assert "usage: path-finder" in err and "unknown command 'frobnicate'" in err


def test_commands_run_the_scripts_in_place(capsys, monkeypatch, tmp_path):
    assert cli.main(["state", f"32813={MANAGER_FIXTURE}"]) == 0
    snapshot = json.loads(capsys.readouterr().out)
    assert {"sessions", "messages", "sources"} <= set(snapshot) and len(snapshot["messages"]) == 3
    monkeypatch.chdir(tmp_path)
    direct = subprocess.run([sys.executable, str(REPO_ROOT / "viz" / "watcher.py"), "map", "--root", str(tmp_path)], capture_output=True, text=True)
    assert cli.main(["map"]) == direct.returncode and capsys.readouterr().out == direct.stdout == ""
    assert cli.main(["identify", "--role", "  "]) == 2
    assert "role is blank" in capsys.readouterr().err
    assert cli.main(["state"]) == 2
    assert "usage: watcher.py state" in capsys.readouterr().err


def test_repo_not_found_is_exit_1(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "find_repo", lambda: (_ for _ in ()).throw(repo.RepoNotFound("nowhere")))
    assert cli.main(["self"]) == 1
    assert capsys.readouterr().err.strip() == "path-finder: nowhere"


def test_page_url():
    assert window.page_url(4780, "web") == "http://127.0.0.1:4780/web"
    assert window.page_url(4797, "/index.html") == "http://127.0.0.1:4797/index.html"
    assert window.page_url(4780, "index") == "http://127.0.0.1:4780/" and window.page_url(4780, "") == "http://127.0.0.1:4780/"


def test_app_mode_browser_is_none_without_a_known_browser(monkeypatch):
    monkeypatch.setattr(window.platform, "system", lambda: "Linux")
    monkeypatch.setattr(window.shutil, "which", lambda name: None)
    assert window.app_mode_browser() is None
    monkeypatch.setattr(window.shutil, "which", lambda name: "/usr/bin/chromium" if name == "chromium" else None)
    assert window.app_mode_browser() == "/usr/bin/chromium"


def test_app_mode_browser_finds_a_mac_application(monkeypatch, tmp_path):
    binary = tmp_path / "Applications" / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(window.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(window.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(window.shutil, "which", lambda name: None)
    found = window.app_mode_browser()
    assert found == str(binary) or found.endswith(("Google Chrome", "Chromium", "Brave Browser", "Microsoft Edge"))


def test_open_app_window_uses_the_app_flags_or_falls_back_to_the_default_browser(monkeypatch, tmp_path, capsys):
    record = tmp_path / "argv.txt"
    fake = tmp_path / "browser"
    fake.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {record}\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(window, "app_mode_browser", lambda: str(fake))
    assert window.open_app_window("http://127.0.0.1:4797/web") is True
    for _ in range(50):
        if record.exists() and record.read_text().count("\n") >= 2:
            break
        time.sleep(0.05)
    assert record.read_text().splitlines() == ["--app=http://127.0.0.1:4797/web", "--window-size=380,720"]
    assert capsys.readouterr().out.strip() == "opened http://127.0.0.1:4797/web in an app-mode window (380,720) with browser"
    opened = []
    monkeypatch.setattr(window, "app_mode_browser", lambda: None)
    monkeypatch.setattr(window.webbrowser, "open", lambda url: opened.append(url))
    assert window.open_app_window("http://127.0.0.1:4797/web") is False
    assert opened == ["http://127.0.0.1:4797/web"]
    assert capsys.readouterr().out.strip() == "no Chrome, Chromium, Brave, or Edge found for an app-mode window; opened http://127.0.0.1:4797/web in the default browser"


def test_start_server_in_background_serves_state_and_web_for_the_given_root(tmp_path):
    port = free_port()
    assert window.server_answers(port) is False
    process, log_path = window.start_server_in_background(REPO_ROOT, port, tmp_path)
    try:
        assert window.server_answers(port) is True and log_path == window.server_log_path(port)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/state", timeout=2) as response:
            assert json.load(response)["sessions"] == []
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/web", timeout=2) as response:
            assert response.status == 200
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_open_window_reuses_an_answering_watcher_or_starts_one(monkeypatch, tmp_path, capsys):
    opened = []
    monkeypatch.setattr(window, "open_app_window", lambda url: opened.append(url) or True)
    monkeypatch.setattr(window, "server_answers", lambda port: True)
    monkeypatch.setattr(window, "start_server_in_background", lambda *args: (_ for _ in ()).throw(AssertionError("must not start")))
    assert window.open_window(REPO_ROOT, 4797, "web", tmp_path) == 0
    assert opened == ["http://127.0.0.1:4797/web"] and capsys.readouterr().out.strip() == "watcher already answering on port 4797"
    monkeypatch.setattr(window, "server_answers", lambda port: False)
    monkeypatch.setattr(window, "start_server_in_background", lambda repo_path, port_number, root: (type("P", (), {"pid": 4242})(), tmp_path / "log"))
    assert window.open_window(REPO_ROOT, 4798, "index", tmp_path) == 0
    assert opened[-1] == "http://127.0.0.1:4798/" and capsys.readouterr().out.strip() == f"started watcher pid 4242 on port 4798, log {tmp_path / 'log'}"


def test_start_server_reports_a_watcher_that_never_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(window, "SERVER_START_TIMEOUT_S", 1.0)
    monkeypatch.setattr(window, "server_answers", lambda port: False)
    broken = make_repo(tmp_path / "broken")
    (broken / "viz" / "watcher.py").write_text("import sys\nsys.exit(3)\n")
    with pytest.raises(RuntimeError, match="did not answer"):
        window.start_server_in_background(broken, free_port(), tmp_path)
