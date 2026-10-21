# Review: P3 2026-10-21

PASS

## Verified against SPEC P3

- Wheel: in a scratch venv outside the checkout, `pip wheel <checkout> --no-deps` built `path_finder-0.2.0-py3-none-any.whl` whose listing holds exactly the four vendored files under `path_finder/_vendor/` (`discovery/discover.py`, `viz/watcher.py`, `viz/web.html`, `viz/index.html`) plus the package modules and metadata. An sdist built with `python -m build --sdist` carries the four source files, `pyproject.toml` and `README.md`, and `pip wheel <sdist>` gives the same four vendored files.
- Installed wheel, run from `/` with `PATH_FINDER_REPO` unset and `PATH_FINDER_HOME` at a temp dir (the walk-up from `/` does not reach the checkout, so it is off the path; I did not rename it while the other sessions run in it): `--help` prints `code: vendored copies inside the package` and the temp data dir with the rule naming `PATH_FINDER_HOME`; `identify --role x` wrote `<temp>/identity/74335.json` and `<temp>/sessions.json`, and the checkout's `discovery/identity/74335.json` still says `validator`; `list --root <checkout>` printed the four live sessions; `self` printed the temp identity; `serve --port 4796 --no-log` (stopped) ran the vendored watcher (process command line points into the venv) and answered `/state` with `data_dir` = the temp dir and PID 74335 as role `x`, and `/web`, `/` and `/index.html` with 200 (the V19/V20 page). No `~/.path_finder` was created at any point.
- `discovery/discover.py` rule: `checkout_holding` needs `discovery/`, `viz/` and a `pyproject.toml` file in one parent of the script (a vendor-like `_vendor/discovery/discover.py` and a checkout without the file both fall back); `data_dir` prefers the variable (expanded), treats an empty one as unset, then the checkout's `discovery/`, then `~/.path_finder`. End to end, a sandbox copy with the three markers writes `sessions.json` beside itself, without the marker writes `<HOME>/.path_finder/` (created on first write with `identity/`), and with the variable writes there.
- `path_finder`: `find_code_folder` takes the checkout, else the vendored folder when both scripts are present, else the old `RepoNotFound`; commands run the vendored scripts in place; `--help` reports the three cases. An editable install has no `_vendor/`, so the existing entry-point tests behave as before.
- Plugin README has the "Where the data lives" section; the root `README.md` gives pipx from the repo and from a wheel, the three per-session commands, the marketplace and plugin install lines, the trial line, the data rule and the developer steps.
- Existing tests: `python3 -m pytest tests` → 423 passed on HEAD (V20 committed) plus the builder's uncommitted P3 files.

## Tests

- `tests/integration/test_discovery_cli.py`: `run_cli` drops any inherited `PATH_FINDER_HOME` and sets it to the sandbox's `discovery/` by default (the builder's requested fix); new `test_list_reads_and_writes_the_data_directory_by_the_rule`.
- `tests/unit/test_discover.py`: `checkout_holding` markers (folder-as-marker, vendor-like tree), `data_dir` branches, module paths derived from it.
- `tests/unit/test_path_finder_cli.py`: `find_code_folder`, `vendored_copies_present`, `repo.data_dir`, the three `--help` forms, commands running fake vendored scripts.
- `tests/integration/test_path_finder_entry.py`: a copied package with a `_vendor/` tree built from the real scripts runs `--help`, `list`, `state` and `serve` (port 4797) from `/` with the data dir from the environment, writes nothing into `_vendor/`.
- `tests/unit/test_plugin_files.py`: plugin README section, root README lines, `pyproject.toml` backend, version, readme, force-include mapping and sdist includes.

## Notes

- `pyproject.toml` now declares `readme = "README.md"`, so the build needs the untracked root `README.md`; the manager should commit it with P3.
- The root README's install lines use `github.com/kharanga/path_finder`; whether that repository is public is a user item.
- The vendored watcher's `SPEC_PATH` is `_vendor/SPEC.md` (absent, so `/state` has no tasks) and its default `--log` would write `events.jsonl` into `_vendor/viz/`; running it also leaves a `__pycache__` there. All outside P3 as specified.
- If a venv lives inside the checkout, the vendored copies sit under the checkout and both scripts resolve the checkout's `discovery/` through the walk-up; the same data either way.
- For the manager (from ready.md): mark P3 done; CLAUDE.md "What exists" could mention the vendored copies and `PATH_FINDER_HOME`.
