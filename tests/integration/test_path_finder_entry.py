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
