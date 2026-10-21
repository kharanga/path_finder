# Ready: P1 2026-10-20

## Done
`pip install -e .` or `pipx install .` now gives a `path-finder` console script. Nothing in `discovery/discover.py` or `viz/watcher.py` changed; `python3 discovery/discover.py ...` and `python3 viz/watcher.py ...` keep working as before.

New files:

- `pyproject.toml`: setuptools build, package `path_finder`, console script `path-finder = path_finder.cli:main`, `requires-python >= 3.9`, no dependencies.
- `path_finder/repo.py`: finds the checkout. Order: `PATH_FINDER_REPO` env var, the package's own parent folder (editable install or running from the checkout), then the current directory and its parents, looking for `discovery/discover.py` and `viz/watcher.py`. A clear error and exit 1 when none matches.
- `path_finder/cli.py`: the dispatcher. `identify`, `self`, `list`, `done` run `discovery/discover.py` in place; `serve`, `state`, `replay`, `map`, `tail` run `viz/watcher.py` in place, both via `runpy.run_path` with the remaining arguments passed through untouched, so every flag of the two scripts is available. `--root` is appended as the current working directory for `list`, `done`, `map`, and `serve` when the caller did not pass one. Unknown command prints the usage and exits 2.
- `path_finder/window.py`: `window [--port 4780] [--page web] [--root DIR]`. Probes `/state` on the port; when nothing answers it starts `viz/watcher.py serve --port P --root DIR` detached in the background, logging to `<tempdir>/path-finder-serve-<port>.log`, and waits up to 8 s for `/state`. Then it looks for Google Chrome, Chromium, Brave Browser, or Microsoft Edge under `/Applications` and `~/Applications` (and on PATH on other systems), and opens `--app=URL --window-size=380,720` with the first one found. With none found it opens the URL in the default browser and prints a note saying so.
- `.gitignore`: `build/`, `dist/`, `*.egg-info/`.

Verified on 2026-10-20:

- Two scratch venvs: one `pip install -e .`, one plain `pip install .` (the pipx shape, package copied into site-packages). Both put `path-finder` in the venv's `bin/`.
- `path-finder identify --role x` from the editable venv wrote `discovery/identity/74018.json` with role `x`; I re-ran it with `--role discovery-builder` right after, so my identity is back to normal. `identify --role "  "` exits 2 through the CLI as well.
- From the plain install, `path-finder self` works from `fake_session/` (parent walk-up), fails with the checkout message from `/`, and works from `/` with `PATH_FINDER_REPO` set.
- `path-finder serve --port 4799 --no-log` answered `/state` (4 sessions) and `/web` (HTTP 200). Port 4780 is held by the viz-builder's watcher (pid 15153), untouched, which is why the check used 4799.
- `path-finder window --port 4799` printed `watcher already answering on port 4799` and opened the app window in the running Chrome. `path-finder window --port 4798` printed `started watcher pid ... on port 4798, log ...` and opened a second one. Both watchers I started were stopped afterwards; ports 4798 and 4799 are free.
- Screenshot: `handoff/discovery/p1-window.png`, captured over the DevTools protocol from a Chrome instance launched with the exact `--app --window-size` flags and a scratch profile. The window reported `outer 380x720`, `inner 380x692`, bounds `{left 22, top 59, width 380, height 720}`, title `Session Web`, and the page shows the four live sessions. The default-browser fallback was not exercised because Chrome is installed; the code path is `open_app_window` in `path_finder/window.py`.
- `python3 -m pytest tests`: 369 passed. Two `test_web_render.py` tether tests failed once while the viz-builder was editing `viz/web.html` and that test file (mtimes 19:12 and 19:13); they passed on rerun and in the final full run.

## How to test

```
python3 -m venv /tmp/pf-venv && /tmp/pf-venv/bin/pip install -e /Users/khangnguyen/Documents/path_finder
/tmp/pf-venv/bin/path-finder --help
/tmp/pf-venv/bin/path-finder identify --role x && cat discovery/identity/$(pgrep -n claude).json
/tmp/pf-venv/bin/path-finder identify --role <your real role>
/tmp/pf-venv/bin/path-finder serve --port 4799 --no-log &   # then curl http://127.0.0.1:4799/state
/tmp/pf-venv/bin/path-finder window --port 4799
```

Expect the console script on the venv's PATH, the identity file rewritten with role `x`, `/state` JSON on 4799, and a small chromeless Chrome window showing `/web`. Running `window` on an unused port (for example 4797) should print `started watcher pid N` and open the window; stop that watcher with `kill N` when done. `pipx install .` from the checkout root gives the same result, but installs into the user's pipx home, so prefer the venv on a shared machine.

## Requests
- Manager: mark P1 done in `SPEC.md`. CLAUDE.md "What exists" could gain one line for `path_finder/` and the `path-finder` script.
- Validator: tests for `path_finder/` would go under `tests/`; `path_finder.cli.main(argv)` takes an argument list and returns an exit code, `path_finder.repo.find_repo` honours `PATH_FINDER_REPO`, and `path_finder.window.app_mode_browser` returns `None` when no browser is found, which is the fallback branch.

## Blocked
None.
