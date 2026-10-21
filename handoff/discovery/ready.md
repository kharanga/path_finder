# Ready: P3 2026-10-21

## Done

(1) Data directory in `discovery/discover.py`. `data_dir()` returns `$PATH_FINDER_HOME` when set; else, when a parent of the script holds `discovery/`, `viz/`, and `pyproject.toml` together (the amended rule from the manager's P3 note), that checkout's `discovery/`; else `~/.path_finder`. `DISCOVERY_DIR`, `DIRECTORY_PATH`, and `IDENTITY_DIR` keep their names and are derived from it, so the test fixtures' monkeypatches still apply. The directory and `identity/` are created on first write as before (`write_identity`, `lock_directory`, `drop_identities_of_dead_sessions` all mkdir). Nothing else in the script changed.

(2) Self-contained wheel. `pyproject.toml` now builds with hatchling (version 0.2.0, `readme = "README.md"`). `force-include` copies `discovery/discover.py` to `path_finder/_vendor/discovery/discover.py` and `viz/watcher.py`, `viz/web.html`, `viz/index.html` to `path_finder/_vendor/viz/` at build time; the originals stay where they are. The sdist carries the four source files so a wheel can be built from it. `path_finder/repo.py` gains `VENDOR_DIR`, `vendored_copies_present()`, `data_dir()`, and `data_dir_description()`; `find_repo`, `candidate_folders`, `discover_script`, `watcher_script`, and `RepoNotFound` are unchanged. `path_finder/cli.py` resolves the code folder with `find_code_folder()`: the checkout as before, else the vendored folder, else the old error. Because an editable install has no `_vendor/`, `pip install -e .` and the test suite behave exactly as before.

(3) `path-finder --help` ends with two lines: which code runs (checkout path or "vendored copies inside the package") and the data directory in use, followed by the rule naming `PATH_FINDER_HOME`. `plugin/README.md` gains a "Where the data lives" section with the same rule.

(4) `README.md` at the repo root: install for use (pipx from the GitHub repo or from a wheel, the three commands per session, the plugin from GitHub via `claude plugin marketplace add kharanga/path_finder` or `--plugin-dir plugin` for a trial), where the data lives, and install for development (clone, editable venv, pytest, direct script runs, `pip wheel`).

Verified on 2026-10-21:

- `pip wheel . --no-deps` in a scratch venv outside the checkout built `path_finder-0.2.0-py3-none-any.whl`; its listing has exactly the four vendored files under `path_finder/_vendor/` plus the package and metadata.
- With that wheel installed, from `/` with `PATH_FINDER_REPO` unset and `PATH_FINDER_HOME` set to a temp dir: `--help` says "vendored copies inside the package" and prints the temp dir; `identify --role x` wrote `<temp>/identity/74018.json` (the checkout's `discovery/identity/74018.json` was untouched); `list --root <checkout>` printed four sessions; `serve --port 4795 --no-log` answered `/state` with `data_dir` equal to the temp dir and the `x` role present, and `/web` and `/` with HTTP 200. The vendored watcher is the V20 one (it reports `data_dir`). The checkout was not renamed, since other sessions are running in it; the validator may do that instead.
- A plain copy of `discover.py` under `<tmp>/_vendor/discovery/` with `HOME` pointed at a temp folder resolved its data dir to `<temp HOME>/.path_finder`.
- From the checkout, `python3 discovery/discover.py self` and `path-finder --help` still use the checkout's `discovery/`; `PATH_FINDER_HOME=<dir> discover.py list` created `<dir>/identity/` and `<dir>/sessions.json`.
- `python3 -m pytest tests`: 408 passed, 2 failed. The two are `tests/integration/test_discovery_cli.py::test_two_sessions_listed_with_roles_then_one_exit_removes_it` and `::test_stale_identity_of_dead_pid_is_dropped`. Their sandbox copies `discover.py` into a bare `<tmp>/discovery/` with no `viz/` or `pyproject.toml` and writes identities beside it; under the new rule the copy uses `<tmp HOME>/.path_finder` instead, so the identities are not seen. That is the intended P3 behaviour. In a scratch copy of the suite with one change in `run_cli`, `"PATH_FINDER_HOME": str(sandbox["discovery_dir"])` added to `env`, both tests and the rest of the discovery tests pass (57 passed). Earlier in the run four `viz/watcher.py` tests failed while the viz-builder was mid-edit on V20; they pass now.

## How to test

```
python3 -m venv /tmp/pf-wheel && cd /tmp && /tmp/pf-wheel/bin/pip wheel /Users/khangnguyen/Documents/path_finder --no-deps -w /tmp/pf-dist
python3 -c "import zipfile,glob; print([n for n in zipfile.ZipFile(glob.glob('/tmp/pf-dist/*.whl')[0]).namelist() if '_vendor' in n])"
/tmp/pf-wheel/bin/pip install /tmp/pf-dist/path_finder-0.2.0-py3-none-any.whl
cd / && unset PATH_FINDER_REPO && export PATH_FINDER_HOME=/tmp/pf-data
/tmp/pf-wheel/bin/path-finder --help
/tmp/pf-wheel/bin/path-finder identify --role x && ls /tmp/pf-data/identity
/tmp/pf-wheel/bin/path-finder list --root /Users/khangnguyen/Documents/path_finder
/tmp/pf-wheel/bin/path-finder serve --port 4795 --no-log &   # then curl :4795/state and :4795/web, then kill it
```

Expect the four `_vendor` files in the listing, help naming the vendored copies and `/tmp/pf-data`, the identity file in `/tmp/pf-data/identity/`, the live sessions, and `/state` with `"data_dir": "/tmp/pf-data"`. Rename the checkout first if you want the "not on disk" form; the walk-up from `/` does not reach it either way. Re-run `identify` with your real role afterwards if you ran it in a session that matters, and unset `PATH_FINDER_HOME` before using the checkout's data again.

## Requests
- Validator (owner of `tests/`): in `tests/integration/test_discovery_cli.py` `run_cli`, add `"PATH_FINDER_HOME": str(sandbox["discovery_dir"])` to the subprocess env. That is the whole fix for the two failures. Tests for the new pieces would go against `discover.data_dir` / `checkout_holding` (env var, checkout with and without `pyproject.toml`, home fallback), `repo.vendored_copies_present`, `cli.find_code_folder`, and the wheel listing if a build in tests is acceptable.
- Manager: mark P3 done in `SPEC.md`; CLAUDE.md "What exists" could mention the wheel's vendored copies and `PATH_FINDER_HOME`. The README's GitHub lines use the `origin` remote, `kharanga/path_finder`.

## Blocked
None.
