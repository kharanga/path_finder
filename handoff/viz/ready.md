# Ready: V20 2026-10-21 (round 2: pyproject.toml marker)

## Done

`viz/watcher.py` no longer anchors the identity folder to its own location; it follows the shared data-directory rule and reports the directory in `/state`.

`viz/watcher.py`:

- `HOME_ENV_VAR = "PATH_FINDER_HOME"`, `CHECKOUT_FOLDERS = ("discovery", "viz")`, `CHECKOUT_FILES = ("pyproject.toml",)`, `USER_DATA_DIR_NAME = ".path_finder"`.
- `is_checkout(folder)` is true when the folder holds the `discovery/` and `viz/` folders and the `pyproject.toml` file (the manager's V20 decision: the vendored copies in a wheel have no `pyproject.toml` beside them, so they never match). `checkout_root(start)` walks `start` and its parents for the first such folder.
- `resolve_data_dir(environ=None, script_dir=None, home=None)`: `$PATH_FINDER_HOME` when set and non-empty (expanded and resolved); else the checkout's `discovery/` when the script sits inside one; else `<home>/.path_finder`. The arguments default to `os.environ`, the watcher's own folder, and `Path.home()`, and exist so the rule can be tested without the environment.
- `DATA_DIR = resolve_data_dir()` and `IDENTITY_DIR = DATA_DIR / "identity"` replace `DISCOVERY_DIR` / `IDENTITY_DIR`. `read_identity` still reads `IDENTITY_DIR` at call time, so the test fixture that redirects `IDENTITY_DIR` works unchanged. In this checkout the values are the same as before (`<checkout>/discovery/identity`), so the 4780 watcher behaves as today after a restart.
- `Watcher.snapshot()` adds `"data_dir": str(IDENTITY_DIR.parent)` (the folder that holds `identity/`), so `/state` and the SSE snapshot carry it.
- Unchanged: `STATIC_DIRS = (VIZ_DIR,)` still serves `web.html` and `index.html` from the watcher's own folder; `SPEC_PATH`, `EVENT_LOG_PATH`, the CLI, the registry and transcript readers, the model, the pages.

Files: `viz/watcher.py`.

## How to test

Vendored copy outside the checkout with a temp data dir holding one identity file for a live PID (use your own session's PID from `discovery/identity/`):

```
V=$(mktemp -d); mkdir -p $V/vendored $V/data/identity
cp viz/watcher.py viz/web.html viz/index.html $V/vendored/
python3 -c "import json; json.dump({'pid': <pid>, 'role': 'vendored-check-role', 'label': 'vendored-check'}, open('$V/data/identity/<pid>.json', 'w'))"
(cd $V/vendored && PATH_FINDER_HOME=$V/data python3 watcher.py serve --port 4792 --no-log &)
curl -s http://127.0.0.1:4792/state | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data_dir'], [(s['pid'], s['role'], s['label']) for s in d['sessions'] if s['pid'] == <pid>])"
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:4792/web
```

Expected: `data_dir` is `$V/data`, the session shows `vendored-check-role` / `vendored-check`, `/web` answers 200 with the page (and `/` with `index.html`). Without `PATH_FINDER_HOME`, `python3 -c "import watcher; print(watcher.DATA_DIR)"` from `$V/vendored` prints `~/.path_finder`; from `viz/` in the checkout it prints `<checkout>/discovery`.

Checked here: exactly that (the temp copy served `/state` with `data_dir` = the temp data dir and PID 74170 as `vendored-check-role`, `/web` 200 with the V19 page, `/` 200, `/index.html` 200; without the variable the copy resolves `~/.path_finder`); a vendor-like tree `_vendor/discovery/` beside `_vendor/viz/watcher.py` with no `pyproject.toml` resolves `~/.path_finder`; `resolve_data_dir` with a fake tree: override wins (`~` expanded), a script in `<repo>/viz` or deeper resolves `<repo>/discovery` once `pyproject.toml` exists, the same tree without it or with `pyproject.toml` as a folder resolves `<home>/.path_finder`, an empty variable counts as unset. In the checkout the module still resolves `<checkout>/discovery/identity`.

Suite: `python3 -m pytest tests` → 399 passed, 6 failed. Three are expected pins of this task: the `/state` key set in `tests/unit/test_watcher_server.py` (`test_fixture_watcher_first_poll_registers_sessions_and_replays_history`, `test_watcher_emits_the_tasks_change_on_the_first_poll_and_on_edits`) gains `data_dir`; and `tests/integration/test_watcher_cli.py::test_map_prints_pid_session_id_and_transcript_for_two_fake_sessions`, whose `sandbox` copies `watcher.py` into `tmp/repo/viz/` beside `tmp/repo/discovery/identity/` but writes no `tmp/repo/pyproject.toml`, so under the three-marker rule the copy resolves `$HOME/.path_finder` and the identity label is not found (add an empty `tmp/repo/pyproject.toml` to the sandbox, or pass `PATH_FINDER_HOME=tmp/repo/discovery`). The other three (`tests/integration/test_discovery_cli.py::test_two_sessions_listed_with_roles_then_one_exit_removes_it`, `::test_stale_identity_of_dead_pid_is_dropped`, `tests/unit/test_path_finder_cli.py::test_repo_not_found_is_exit_1`) come from the discovery-builder's uncommitted P3 edits to `discovery/discover.py`, `path_finder/repo.py`, and `path_finder/cli.py`: with the committed copies of those three files and this watcher, those test files pass (31 passed). I did not touch them.

## Requests

- Validator: re-pin the two key-set assertions with `data_dir` and give the map test's sandbox a `pyproject.toml` (or `PATH_FINDER_HOME`); `resolve_data_dir(environ, script_dir, home)`, `checkout_root`, and `is_checkout` are plain functions for unit tests of the three branches and the three markers; the server test can assert `snapshot["data_dir"] == str(watcher.IDENTITY_DIR.parent)`.
- Manager: restart the 4780 watcher on the new `viz/watcher.py` for `data_dir` in `/state`.
- Discovery-builder (P3): `discovery/discover.py` should use the same three markers (`discovery/`, `viz/`, `pyproject.toml`) so both scripts resolve one directory.
- Note: `EVENT_LOG_PATH` stays `<watcher folder>/events.jsonl` (not in this task), so a vendored watcher with the default `--log` writes its event log next to itself; `--no-log` or `--log` elsewhere avoids that. `SPEC_PATH` likewise stays `<watcher folder>/../SPEC.md` and a missing file yields an empty task list.
- Docs (user): plan §3 / README: data directory rule and `PATH_FINDER_HOME`; `/state` field `data_dir`.

## Blocked

Nothing.
