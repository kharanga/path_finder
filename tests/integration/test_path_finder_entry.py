import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

from conftest import REPO_ROOT

PORT = 4797


def run_cli(arguments, cwd=REPO_ROOT, env=None, timeout=30):
    return subprocess.run([sys.executable, "-m", "path_finder.cli", *arguments], cwd=cwd, env=env or {**os.environ, "PYTHONPATH": str(REPO_ROOT)}, capture_output=True, text=True, timeout=timeout)


def test_help_unknown_and_blank_role_exit_codes():
    assert run_cli(["--help"]).returncode == 0
    unknown = run_cli(["frobnicate"])
    assert unknown.returncode == 2 and "unknown command" in unknown.stderr
    blank = run_cli(["identify", "--role", "  "])
    assert blank.returncode == 2 and "role is blank" in blank.stderr


def test_installed_elsewhere_the_cli_needs_the_checkout_or_the_env_var(tmp_path):
    shutil.copytree(REPO_ROOT / "path_finder", tmp_path / "site" / "path_finder", ignore=shutil.ignore_patterns("__pycache__"))
    env = {**os.environ, "PYTHONPATH": str(tmp_path / "site")}
    env.pop("PATH_FINDER_REPO", None)
    lost = run_cli(["self"], cwd="/", env=env)
    assert lost.returncode == 1 and "cannot find the path_finder checkout" in lost.stderr
    found = run_cli(["state", f"32813={REPO_ROOT / 'tests' / 'fixtures' / 'viz' / 'round_trip_manager_32813_33993.jsonl'}"], cwd="/", env={**env, "PATH_FINDER_REPO": str(REPO_ROOT)})
    assert found.returncode == 0 and len(json.loads(found.stdout)["messages"]) == 3
    walked = run_cli(["state", f"32813={REPO_ROOT / 'tests' / 'fixtures' / 'viz' / 'round_trip_manager_32813_33993.jsonl'}"], cwd=REPO_ROOT / "fake_session", env=env)
    assert walked.returncode == 0


def test_serve_through_the_entry_point_answers_state_and_web_with_the_working_directory_as_root(tmp_path):
    process = subprocess.Popen([sys.executable, "-m", "path_finder.cli", "serve", "--port", str(PORT), "--no-log"], cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(REPO_ROOT)}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/state", timeout=1) as response:
                    state = json.load(response)
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise AssertionError("no /state on the spare port")
        assert state["sessions"] == [] and "tasks" in state
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/web", timeout=2) as response:
            assert response.status == 200 and b"<title>" in response.read()
    finally:
        process.terminate()
        process.wait(timeout=5)


def vendored_site(tmp_path):
    site = tmp_path / "site"
    shutil.copytree(REPO_ROOT / "path_finder", site / "path_finder", ignore=shutil.ignore_patterns("__pycache__"))
    vendor = site / "path_finder" / "_vendor"
    (vendor / "discovery").mkdir(parents=True)
    (vendor / "viz").mkdir()
    shutil.copy(REPO_ROOT / "discovery" / "discover.py", vendor / "discovery" / "discover.py")
    for name in ("watcher.py", "web.html", "index.html"):
        shutil.copy(REPO_ROOT / "viz" / name, vendor / "viz" / name)
    return site


def test_a_package_with_vendored_copies_runs_them_outside_the_checkout_with_the_data_dir_from_the_env(tmp_path):
    site = vendored_site(tmp_path)
    data = tmp_path / "data"
    env = {**os.environ, "PYTHONPATH": str(site), "PATH_FINDER_HOME": str(data)}
    env.pop("PATH_FINDER_REPO", None)
    helped = run_cli(["--help"], cwd="/", env=env)
    assert helped.returncode == 0 and "code: vendored copies inside the package" in helped.stdout and f"data directory: {data}" in helped.stdout
    listed = run_cli(["list", "--root", str(tmp_path / "nowhere")], cwd="/", env=env)
    assert listed.returncode == 0 and listed.stdout == "" and (data / "sessions.json").is_file() and (data / "identity").is_dir()
    assert not (site / "path_finder" / "_vendor" / "discovery" / "sessions.json").exists()
    state = run_cli(["state", f"32813={REPO_ROOT / 'tests' / 'fixtures' / 'viz' / 'round_trip_manager_32813_33993.jsonl'}"], cwd="/", env=env)
    assert state.returncode == 0 and len(json.loads(state.stdout)["messages"]) == 3
    process = subprocess.Popen([sys.executable, "-m", "path_finder.cli", "serve", "--port", str(PORT), "--no-log"], cwd="/", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/state", timeout=1) as response:
                    served = json.load(response)
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise AssertionError("no /state on the spare port")
        assert served["data_dir"] == str(data) and served["tasks"] == []
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/web", timeout=2) as response:
            assert response.status == 200 and b"ROW_STORAGE_PREFIX" in response.read()
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2) as response:
            assert response.status == 200
    finally:
        process.terminate()
        process.wait(timeout=5)
    assert not (site / "path_finder" / "_vendor" / "viz" / "events.jsonl").exists()
