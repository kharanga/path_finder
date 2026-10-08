# Review: V0 2026-10-08

PASS

## Checked against SPEC.md V0

- `python3 viz/watcher.py map --root fake_session` prints pid, session id, and transcript path for both fake sessions (32813, 33993), method `registry sessionId`, exit 0. Same with the absolute root.
- Each mapped id equals the single `sessionId` value inside that transcript (`grep -o '"sessionId":"[^"]*"' | sort -u`).
- `map` with no root lists all ten live sessions on the machine, exit 0. `--json` carries `pid`, `name`, `cwd`, `socket`, `session_id`, `started_at_ms`, `role`, `label`, `transcript`, `method`.
- Method order matches plan §3: registry `sessionId` first (every live registry file has it), `cwd` folder plus `startedAt` as fallback, `origin.verifiedPeerPid` not needed.
- Fallback on the shared fake_session folder reports `cwd folder, ambiguous (2 candidates)` with no path, as the ready.md states.
- Folder encoding: every non-alphanumeric character becomes `-`. Verified against the six real folders under `~/.claude/projects/`, including `path_finder` to `path-finder` and `claude-501/-Users` to `claude-501--Users`.
- Nothing under `~/.claude` or `discovery/` is written. Only `viz/watcher.py` is new.

## Tests

`python3 -m pytest tests` now runs 81 tests (33 new for V0), all passing, in about 3 s.

- `tests/conftest.py`: `watcher` fixture loads `viz/watcher.py` by path and points `SESSIONS_DIR`, `PROJECTS_DIR`, `IDENTITY_DIR` at a temp tree.
- `tests/unit/test_watcher.py`: encoding cases, registry parsing with and without `sessionId` and `startedAt`, every `resolve_transcript` branch (single, not written yet, duplicate id resolved by own folder, duplicate id ambiguous, fallback single, fallback ambiguous, fallback empty folder, no cwd, no start), `session_map` merge and root filter, `command_map` text and JSON output and exit codes.
- `tests/integration/test_watcher_cli.py`: the CLI as a subprocess with `HOME` set to a temp dir and the script copied beside a temp `discovery/identity/`, real child processes as live sessions.

## Notes, not failures

1. User item (docs/, no team role may edit it): SPEC V0 asks for the method in `docs/cross-session-message-format.md` §6. Not recorded. §6 still keys nodes by `sessionId` and recommends a `SessionStart` hook, both contradicting SPEC (keyed by PID, no hooks). The builder's suggested replacement text under Requests in ready.md is accurate against the code and the real registry files.
2. User item (docs/): `docs/jsonl-transcript-spec.md` §1 says only `/` becomes `-` in the folder name. Wrong: `path_finder` is `path-finder` on this machine. The builder's correction is right.
3. Exit code inconsistency: `map --json` exits 0 when no session matches the root, text mode exits 1. Covered by a test that pins the current behaviour; worth aligning in V1 or later.
4. For the manager: `viz/__pycache__/` exists from the builder's run; same `.gitignore` request as the D3 review.
