# Ready: D4 2026-10-20

## Done
`ui` is retired from `discovery/discover.py`. The commands are now `identify`, `self`, `list`, `done`.

- `ui` and `ui --stop` removed, with `ui_is_up`, `start_ui`, `stop_ui`, `command_ui`, the `UI_PORT`, `UI_LOG`, `UI_PID` constants, and the `time` and `urllib.request` imports.
- `discovery/index.html` deleted (shows as `D` in git status). `discovery/ui.log` removed; `discovery/ui.pid` did not exist. Copies of both files sit in this session's scratchpad until the commit, in case the manager wants them back.
- `.gitignore`: dropped `discovery/ui.log` and `discovery/ui.pid`. This file is outside `discovery/`; the edit is listed in the D4 task text in `SPEC.md`, so I made it rather than requesting it.
- `identify --role "<blank>"`: the role is stripped; when nothing is left, `identify` prints `role is blank: pass the role your human entered, for example --role manager` on stderr, exits 2, and writes nothing. A non-blank role is stored stripped.

Verified on 2026-10-20 against the live machine:

- `discover.py ui` exits 2 with argparse `invalid choice: 'ui' (choose from identify, self, list, done)`.
- `identify --role ""` and `identify --role "   "` both exit 2; `discovery/identity/74018.json` is byte-for-byte unchanged afterwards.
- `self` exits 0 and `list --root /Users/khangnguyen/Documents/path_finder` prints six sessions, as before.
- Port 4780 is held by `viz/watcher.py serve` (pid 25176, not started by this session, untouched), so the port handover dependency is met.

## How to test

```
python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py ui
python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py identify --role ""
python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py identify --role "  "
```

Expect exit 2 from each, the first with the argparse invalid-choice error, the other two with the blank-role message and no change to `discovery/identity/`. Then `ls discovery` shows only `discover.py`, `identity/`, `sessions.json`, `sessions.json.lock`, and `git status` shows `discovery/index.html` deleted and `.gitignore` modified.

Tests: `python3 -m pytest tests -q` currently reports 195 passed, 42 errors. Every error is the same fixture failure: `tests/conftest.py` lines 50 and 51 monkeypatch `UI_LOG` and `UI_PID`, which no longer exist on the module. With those two lines removed the full suite passes (237 passed, verified in a scratchpad copy of `tests/`, `discovery/`, and `viz/`). No test in `tests/unit/test_discover.py` or `tests/integration/test_discovery_cli.py` exercises `ui`, so nothing else needs removing.

## Requests
- Validator (owner of `tests/`): delete the two `UI_LOG` and `UI_PID` monkeypatch lines from the `discover` fixture in `tests/conftest.py`. Optionally add `ui` to the `test_removed_mesh_commands_are_rejected` parametrize list and a test that `identify --role "  "` exits 2 and writes no identity file.
- Manager: mark D4 done in `SPEC.md`; D3 is still unchecked there too. The CLAUDE.md "What exists" sentence already describes `ui` as retired.

## Blocked
None.
