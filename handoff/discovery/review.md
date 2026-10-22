# Review: D5 2026-10-22

PASS

## Verified against SPEC D5

- Move, not a change: every function and module constant of HEAD's `discovery/discover.py` (33 names) has the same source text in exactly one of `paths.py`, `processes.py`, `registry.py`, `identity.py` or the new `discover.py`; the only additions are `OWN_FOLDER`, `bound_to_this_namespace` and `re_export`. `git diff --stat -- discovery pyproject.toml`: `discover.py` 28 insertions, 179 deletions, `pyproject.toml` 8 insertions, four untracked modules. `wc -l discovery/discover.py` is 120.
- Requirement 1: `discover.py` inserts its own folder at the front of `sys.path` before the sibling imports. `python3 /…/discovery/discover.py --help` and `self` work from `/`; the sandbox tests run a copy with `python3 -I` from the checkout and the new split test from `/`; the vendored copy runs through `runpy.run_path` (see the wheel check). Running the script writes no `__pycache__` beside the siblings.
- Requirement 2: every re-exported function carries the sibling's code object and defaults but `discover`'s own globals, so the conftest patches of `SESSIONS_DIR`, `DISCOVERY_DIR`, `DIRECTORY_PATH`, `IDENTITY_DIR`, `SCRIPT_PATH` and `find_claude_ancestor_pid` on the `discover` module reach the exported functions and everything they call (checked by inspection and by a test that patches the module and rebuilds the directory into a temp folder). The siblings keep their own namespaces, so `identity.identity_path` still points at the real data dir; the tests only touch the entry's copies.
- Requirement 3 and 4, wheel check in a scratch venv outside the checkout: `pip wheel <checkout> --no-deps` lists eight vendored files, `_vendor/discovery/{discover,paths,processes,registry,identity}.py` and `_vendor/viz/{watcher.py,web.html,index.html}`. Installed with `--no-compile` and run from `/` with `PATH_FINDER_REPO` unset and `PATH_FINDER_HOME` on a temp dir: `--help` prints `code: vendored copies inside the package` and the temp data dir; `identify --role x` (exit 0), `self` (exit 0, role `x`), `list --root <checkout>` (four live sessions, mine as `x`) wrote only `<temp>/identity/74335.json`, `<temp>/sessions.json` and the lock; the vendored folder gained no files; the checkout's `discovery/identity/74335.json` still says `validator`; no `~/.path_finder` exists. The vendored `discover.py --help` also runs directly through `runpy.run_path`. `test_path_finder_entry.py` passes.
- Requirement 5: see the first item; `SCRIPT_PATH` is now `paths.py`'s path, whose parents are the same folders, so `checkout_holding` resolves the same directory (checkout: `discovery/`; vendored: the env var, else `~/.path_finder`).
- Existing tests: `python3 -m pytest tests` → 423 passed with the three helper edits the manager accepted (the suite was 411 passed, 12 failed before them, all 12 from those helpers), both in the working tree and on an export of HEAD plus only the five discovery files, `pyproject.toml` and the three edited test files.

## Tests

- The three accepted helper edits: `tests/integration/test_discovery_cli.py` `sandbox` and `tests/integration/test_path_finder_entry.py` `vendored_site` copy every `discovery/*.py`; `tests/unit/test_plugin_files.py` pins the eight `force-include` entries and the sdist includes (test renamed to `..._vendors_the_eight_files`).
- New `tests/unit/test_discover_split.py`: each sibling holds exactly the functions the SPEC assigns and the entry holds only the commands, parser, main and the two re-export helpers, under 150 lines, no `__init__.py`; the `sys.path` insert precedes the sibling imports; each re-export shares the sibling's code and defaults but the entry's globals; patching the entry redirects `identity_path` and `rebuild_directory` into a temp folder while the sibling keeps the real path; a copy of the five files runs `--help` from `/` under `-I` and leaves no bytecode.
- `python3 -m pytest tests` → 428 passed.

## Notes

- `discover.py` sets `sys.dont_write_bytecode = True` for the whole process; inside `path-finder` that also covers the watcher run later in the same process. Harmless, noted for the record.
- The siblings are imported by the bare names `paths`, `processes`, `registry`, `identity`; if a host process already holds a module of one of those names in `sys.modules`, that one would win. Not the case for `path-finder` or the test process; noted as a user item if the script is ever embedded elsewhere.
- For the manager (from ready.md): mark D5 done; CLAUDE.md "What exists" line for the four siblings; the `path_finder/cli.py` blank-line removal predates D5 and is the user's. Commit `tests/unit/test_discover_split.py` with the three edited test files.
