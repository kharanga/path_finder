# Review: P1 2026-10-21

PASS

## Verified against SPEC P1

- Two scratch venvs in the validator's scratchpad (`pip install -e .` and plain `pip install .`, the pipx shape): both put `path-finder` in the venv's `bin/`; the plain install carries only `path_finder/` and its dist-info in site-packages.
- From the editable venv: `--help` prints the usage and exits 0; an unknown command prints the usage and exits 2; `identify --role "  "` exits 2 through `discover.py`'s own check; `identify --role x` rewrote `discovery/identity/74335.json` (the validator's own file) with role `x`, and `identify --role validator` put it back; `self` and `list` print the four live sessions; `list` and `serve` from `fake_session/` get `--root` = that folder and show no sessions; `map` and `state` run `watcher.py` in place (`state` on the round-trip fixture prints the 3-message snapshot).
- From the plain venv with cwd `/`: `self` fails with `cannot find the path_finder checkout … set PATH_FINDER_REPO …` and exit 1; with `PATH_FINDER_REPO` set it works. From `fake_session/` the parent walk-up finds the checkout.
- `path-finder serve --port 4797 --no-log` from the checkout answers `/state` (4 sessions, 24 tasks), `/web` and `/` with 200; stopped afterwards, 4797 and 4780 untouched (4780 is the manager's watcher).
- `window`: `app_mode_browser()` finds `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` on this machine; with a recorded fake browser binary `open_app_window` spawns exactly `--app=<url> --window-size=380,720` and prints `opened … in an app-mode window`; with no browser it opens the URL through `webbrowser` and prints the fallback note; `open_window` on an answering port prints `watcher already answering on port N` without starting anything, and on a silent port starts `watcher.py serve --port N --root <cwd>` detached, waits for `/state` (real run on a free port: `/state` with `[]` for a temp root, `/web` 200), prints `started watcher pid … log …`, and a watcher that exits raises the timeout error. The real app window itself was not opened by the validator (it would leave a window on the user's desktop); the builder's `handoff/discovery/p1-window.png` shows it at 380 × 720 with the four sessions.
- `pyproject.toml`: setuptools backend, `requires-python >= 3.9`, no dependencies, console script `path-finder = path_finder.cli:main`. `.gitignore` gains `build/`, `dist/`, `*.egg-info/`. `discovery/discover.py` and `viz/watcher.py` are unchanged by P1 and the existing module paths still work (the discovery tests pass).

## Tests

- `tests/unit/test_path_finder_cli.py`: `find_repo` env var, package checkout, parent walk-up and the clear error; `with_default_root` for every command; help and unknown-command exit codes; `state`, `map`, blank-role and missing-argument runs in place; exit 1 on a missing checkout; `page_url`; `app_mode_browser` with no browser, a PATH browser and a Mac application; `open_app_window` flags and fallback; `start_server_in_background` real run and timeout; `open_window` reuse and start.
- `tests/integration/test_path_finder_entry.py`: `python3 -m path_finder.cli` exit codes, the package copied outside the checkout (exit 1 from `/`, works with the env var and from `fake_session/`), `serve` on 4797 with the working directory as root.
- `python3 -m pytest tests` → 396 passed (25 of them the new P1 tests; the three `test_web_render.py` failures seen mid-review were the viz-builder's V17 pins, now re-pinned under V17).

## Notes

- A watcher started by `window` writes the default `viz/events.jsonl` log in the checkout (no `--no-log`), as `serve` normally does; gitignored.
- `pip install .` (pipx) copies only the package, so a pipx-installed `path-finder` run outside the checkout needs `PATH_FINDER_REPO` or a cwd inside it; the error message says so.
- `path_finder/__pycache__/` appeared in the working tree while testing; `__pycache__/` is gitignored.
- CLAUDE.md "What exists" could name `path_finder/` and the `path-finder` script (user item, from ready.md).
