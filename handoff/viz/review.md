# Review: V20 round 2 2026-10-21

PASS

## Verified against SPEC V20

- Vendored copy: `viz/watcher.py` (round 2, three markers), `web.html` and `index.html` in a scratch folder outside the checkout, served with `PATH_FINDER_HOME` at a temp data dir holding one identity file for this session's PID (spare port 4796, `--no-log`, stopped). `/state` has `data_dir` = the temp data dir and the session with role `vendored-check-role`, label `vendored-check`; `/web`, `/` and `/index.html` answer 200 with the V19 page from the copy's own folder; `tasks` is empty because the copy has no `../SPEC.md`. Nothing was written to `~/.path_finder` and the vendored folder gained no files.
- The three branches, imported from a scratch folder with the variable unset, empty, set to a `~` path, from a vendor-like `_vendor/discovery/` + `_vendor/viz/` tree with and without a `pyproject.toml`, and from the checkout's `viz/`: the override wins and is expanded; the empty variable counts as unset; the checkout resolves `<checkout>/discovery`; the vendor-like tree resolves `~/.path_finder` until a `pyproject.toml` file sits beside the two folders; the checkout's own module still resolves `<checkout>/discovery/identity`, so the 4780 watcher is unchanged after its restart.
- Existing tests: on a scratch export of HEAD plus only the V20 watcher and the validator's tests, the suite is green apart from one test that needs the checkout's `fake_session/` folder (absent from the export; unrelated). In the working tree the three remaining failures (`test_discovery_cli` two cases, `test_repo_not_found_is_exit_1`) come from the discovery-builder's uncommitted P3 edits to `discovery/discover.py`, `path_finder/repo.py` and `path_finder/cli.py`, judged separately with P3 as the manager instructed.

## Tests

- `tests/unit/test_watcher_server.py`: the two `/state` key sets gain `data_dir`, pinned to `IDENTITY_DIR.parent`; new `test_is_checkout_needs_the_two_folders_and_the_pyproject_file` (folder marker as a directory, vendor-like tree), `test_checkout_root_walks_up_from_the_script_folder_to_the_first_checkout`, `test_resolve_data_dir_prefers_the_env_var_then_the_checkout_then_the_home_folder` (override, `~`, empty, checkout from `viz/` and deeper, no checkout, missing `pyproject.toml`, vendor-like tree, defaults from the environment and `Path.home()`), `test_module_constants_follow_the_rule_and_identity_sits_under_the_data_dir` (no `DISCOVERY_DIR`, `STATIC_DIRS` unchanged).
- `tests/integration/test_watcher_cli.py`: the map sandbox writes an empty `repo/pyproject.toml`; `run_map` drops any inherited `PATH_FINDER_HOME` and can set one; new `test_map_reads_identity_from_the_data_directory_rule` (checkout label, name fallback without the marker, override, `$HOME/.path_finder`).
- `python3 -m pytest tests` → 407 passed, 3 failed (the P3 work-in-progress cases above); HEAD + V20 watcher + these tests → 409 passed plus the export-only `fake_session` case.

## Notes

- From ready.md, for the manager: restart the 4780 watcher on the new `viz/watcher.py` for `data_dir` in `/state`; the discovery-builder's `discover.py` should use the same three markers (its current uncommitted copy checks only the two folders and walks from the script's parents, so it would disagree with the watcher in a vendor-like tree without `pyproject.toml` and in a checkout whose `pyproject.toml` is missing).
- `EVENT_LOG_PATH` stays beside the watcher, so a vendored copy run with the default `--log` writes `events.jsonl` next to itself; `--no-log` or `--log` elsewhere avoids it. `SPEC_PATH` stays `<watcher>/../SPEC.md`; a vendored copy shows no tasks. Both are outside V20.
- Docs user items (from ready.md): plan §3 / README: data directory rule and `PATH_FINDER_HOME`; `/state` field `data_dir`; earlier items unchanged.
