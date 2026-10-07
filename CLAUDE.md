# path_finder

Every agent reads this file first, then `SPEC.md`.

## Status

The workspace was reset on 2026-10-07. The architecture and the spec are being defined by the user. Do not build anything that `SPEC.md` does not ask for.

## What exists

- `discovery/discover.py`: helper for session discovery. `identify --role` stores the role the session's human entered in `discovery/identity/<pid>.json` (label equals role). `ui` serves `discovery/index.html`, a capsule per discovered session, with the built-in http server on port 4780; `ui --stop` ends it. `self` prints the calling session's name, PID, start path, role, and label, and exits 2 until `identify` has run. `list` prints live sessions, filtered by `--root`. `record` and `done` maintain a shared `discovery/sessions.json` under a file lock. `protocol` prints the exact message texts for a mesh round. Owned by discovery-builder.
- `.claude/roles/`: one file per role. Each agent reads its own role file after this file and `SPEC.md`.
- `handoff/<area>/ready.md` and `review.md`: builder to validator handoff.

## How sessions find and talk to each other

- `ListAgents` lists live sessions on this machine by display name. Names are derived from the start folder plus a suffix, change on restart, and can change mid-run. Never hard-code a name. PIDs are stable for a session's life.
- `SendMessage` sends plain text to a session by name over a local socket. It is read at the recipient's next turn. Only a Claude session can send; scripts cannot.
- Each session's registry entry at `~/.claude/sessions/<pid>.json` holds its PID, name, and full start path. This is undocumented but is what the discovery helper reads.

## Team rules

- The manager assigns every task by ID. Builders do not start unassigned work.
- Builders work only inside their own folder and write requests for anything else under Requests in their `ready.md`.
- After 3 failed rounds on the same issue, stop and write under Blocked.
- Only the manager runs `git commit` or `git push`.
- Never kill a process you did not start in your own session.

## Protected files

- `~/.claude/settings.json`, `~/.claude/sessions/`, `/tmp/cc-socks/`: read-only, never edited by agents.
- Any `.env` file.
