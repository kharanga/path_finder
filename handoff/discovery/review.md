# Review: D3 2026-10-08

PASS

## Checked against SPEC.md D3

- `list --root /Users/khangnguyen/Documents/path_finder/fake_session` printed fake-session-manager (pid 32813) and fake-session-builder (pid 33993), both `"identified": true` with roles. No message sent: both fake transcripts kept their 00:23 mtime across the run.
- `done --root .../fake_session` exits 0 with every session identified.
- `record` and `protocol` exit 2 with argparse "invalid choice". `--as-pid` and `--out` are gone.
- `sessions.json` is rebuilt on every `list` and `done` from the registry plus `identity/`, under `sessions.json.lock`, written atomically via `.tmp` + `os.replace`. Dead PIDs are dropped and their identity files deleted.
- Session exit removes it on the next `list`: verified with a real child process (`sleep`) terminated between two `list` runs in a temp sandbox, not by closing a fake session.
- `identify` sets label equal to role; `self` exits 2 before `identify`, 1 outside a session.
- `with_identity` reads both `identified_at` and the D1 `set_at` field, so the two fake sessions' 2026-10-07 identity files still resolve.
- `index.html`: capsule dashed when `role` is null, header counts identified sessions, no `heard_by` or `participants` left.
- Role file `.claude/roles/discovery-builder.md` matches the code: directory shape, commands, `identified_at`.

## Tests

`python3 -m pytest tests` runs 48 tests, all passing, in about 2 s. Layout:

- `tests/conftest.py`: loads `discovery/discover.py` by path and points `SESSIONS_DIR`, `DISCOVERY_DIR`, `DIRECTORY_PATH`, `IDENTITY_DIR` at a temp tree. Nothing under `~/.claude` or `discovery/` is read or written.
- `tests/unit/test_discover.py`: one function at a time; registry parsing (missing, corrupt, non-integer pid), root filtering, liveness, identity merge, pruning, every command's exit code and output, removed commands and flags.
- `tests/integration/test_discovery_cli.py`: the CLI as a subprocess with `HOME` set to a temp dir and a copy of the script, real child processes as live and exited sessions.
- `tests/fixtures/discovery/`: sanitized registry entry and a D1 `set_at` identity file (home paths replaced).

## Notes, not failures

1. `identify --role ""` writes an empty-string role, which `is_identified` counts as identified and `done` accepts. Suggest rejecting a blank role in a later D task.
2. The two fake sessions' identity files predate D2 and carry a label that differs from the role (`fake manager` vs `fake session manager`). The code reads them as-is; they will be replaced when those sessions re-identify.
3. For the manager: `.gitignore` should list `__pycache__/`, `.hypothesis/`, and `.pytest_cache/`. The tests set `sys.dont_write_bytecode` and I removed the directories my run created, but a plain `pytest` run with the installed hypothesis plugin recreates `.hypothesis/`.
4. For the manager: CLAUDE.md line 11 still says `record` and `done` maintain `sessions.json` and that `protocol` and `record` "are removed in D3". The builder's ready.md already requests this update.
