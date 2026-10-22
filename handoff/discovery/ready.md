# Ready: D5 2026-10-22

## Done

`discovery/discover.py` is split into four flat modules beside it; no package folder. Behaviour, command names, flags, output, and exit codes are unchanged. Every function body moved verbatim; the only edits are import lines.

- `discovery/paths.py`: `SESSIONS_DIR`, `SCRIPT_PATH`, `HOME_ENV_VAR`, `checkout_holding`, `data_dir`, the derived `DISCOVERY_DIR`, `DIRECTORY_PATH`, `IDENTITY_DIR`, and `now_iso`.
- `discovery/processes.py`: `pid_is_alive`, `parent_and_command`, `find_claude_ancestor_pid`.
- `discovery/registry.py`: `socket_address`, `read_registry_entry`, `live_sessions`, `under_root`, `own_session`.
- `discovery/identity.py`: `identity_path`, `read_identity`, `write_identity`, `drop_identities_of_dead_sessions`, `with_identity`, `is_identified`, `directory_entries`, `lock_directory`, `write_directory`, `rebuild_directory`.
- `discovery/discover.py` (120 lines): inserts its own folder at the front of `sys.path`, imports the four siblings, re-exports their names, then holds the four command functions, `build_parser`, and `main`.
- `pyproject.toml`: the four new modules are force-included under `path_finder/_vendor/discovery/` and listed in the sdist include.

How the re-export works, and why. The test fixtures patch `SESSIONS_DIR`, `DISCOVERY_DIR`, `DIRECTORY_PATH`, `IDENTITY_DIR`, `SCRIPT_PATH`, and `find_claude_ancestor_pid` on the `discover` module object and then call `discover.rebuild_directory()`, `discover.data_dir()`, `discover.command_identify(...)` and so on. A plain `from identity import rebuild_directory` would hand back a function whose globals are `identity`'s, so the patches would be ignored and about forty unit tests would fail or write into the real `~/.claude/sessions`. `discover.py` therefore re-exports each sibling function rebound to run in discover's own namespace (`types.FunctionType(code, globals(), ...)`), through one helper `re_export(module, names)`. Bodies stay untouched, the siblings stay ordinary importable modules, and every existing unit test passes without edits. The explicit name tuples in `re_export` double as the list of what `discover` exports.

`discover.py` also sets `sys.dont_write_bytecode = True` before the sibling imports, so running the script does not create `discovery/__pycache__/` next to the data directory or inside `_vendor/` in site-packages. Without it the integration test "identify with a blank role writes nothing" sees a new `__pycache__` entry and fails.

Data directory: unchanged rule. `SCRIPT_PATH` is now `paths.py`'s own path; its parents are the same folders as `discover.py`'s, so `checkout_holding` resolves identically (checked: in the checkout it writes to `discovery/`, vendored it falls to `PATH_FINDER_HOME` or `~/.path_finder`).

## How to test

- `python3 -m pytest tests -q`: 411 pass, 12 fail on HEAD tests. All 12 come from three test helpers that copy or list `discover.py` alone (see Requests). With the three edits applied in a scratch copy of the repo, 423 pass.
- `wc -l discovery/discover.py` → 120.
- `git diff --stat -- discovery pyproject.toml` → `discover.py` 28 insertions, 179 deletions; four new untracked modules.
- From any cwd: `python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py --help`, `... self` (prints this session with role `discovery-builder`).
- Wheel, in a scratch venv with hatchling: `pip wheel <checkout> --no-deps -w dist` → `path_finder-0.2.0-py3-none-any.whl` lists eight vendored files: `_vendor/discovery/{discover,paths,processes,registry,identity}.py` and `_vendor/viz/{watcher.py,web.html,index.html}`. Install it, then from `/` with `PATH_FINDER_REPO` unset and `PATH_FINDER_HOME=<temp>`: `path-finder --help` prints `code: vendored copies inside the package`; `path-finder identify --role x`, `self`, and `list --root <checkout>` work and write only `<temp>/identity/<pid>.json`, `<temp>/sessions.json`, and the lock. The checkout's `discovery/identity/74018.json` still says `discovery-builder`. A `__pycache__` under `_vendor/` after install is pip's byte-compile step, not a run.

## Requests

For the validator, three test-helper edits that the split makes necessary (the sandbox and the vendored site need the siblings beside `discover.py`; the pyproject check hard-codes four files). All proven together in a scratch copy: 423 passed.

1. `tests/integration/test_discovery_cli.py`, `sandbox`: replace
   `shutil.copy(DISCOVER_SCRIPT, discovery_dir / "discover.py")`
   with
   `for module in DISCOVER_SCRIPT.parent.glob("*.py"): shutil.copy(module, discovery_dir / module.name)`
2. `tests/integration/test_path_finder_entry.py`, `vendored_site`: replace
   `shutil.copy(REPO_ROOT / "discovery" / "discover.py", vendor / "discovery" / "discover.py")`
   with
   `for module in (REPO_ROOT / "discovery").glob("*.py"): shutil.copy(module, vendor / "discovery" / module.name)`
3. `tests/unit/test_plugin_files.py`, `test_pyproject_builds_with_hatchling_and_vendors_the_four_files`: the expected `force-include` dict gains `discovery/{paths,processes,registry,identity}.py` → `path_finder/_vendor/discovery/<same>.py` (eight entries). The sdist subset check needs no change; the four new sources exist, so the `is_file` loop passes.

For the manager:

- Mark D5 done in `SPEC.md`. In `CLAUDE.md` "What exists", `discovery/discover.py` is now the entry script over `paths.py`, `processes.py`, `registry.py`, `identity.py` (all vendored in the wheel).
- `path_finder/cli.py` carries a one-blank-line removal that predates D5 and is not part of it; revert or commit as you prefer.

## Blocked

Nothing.
