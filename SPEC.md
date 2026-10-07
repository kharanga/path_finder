# SPEC: path_finder

Status: reset 2026-10-07. The architecture and the feature list are to be written by the user.

## Existing building block

`discovery/discover.py`, see `CLAUDE.md`. Verified on 2026-10-07 with a six-session mesh round: every session asked every other for its path and all answers landed in one shared `discovery/sessions.json`.

## Decisions so far

- The discovery directory should be persistent: a session is added when it starts and removed when it leaves, for as long as the application runs.
- Each session's human enters that session's role in its own CLI when discovery starts.
- Directory entries are keyed by PID, not display name, because names change.
- No hooks for now.

## Tasks

To be written.
