# path_finder

Every agent reads this file first, then `SPEC.md`, then its own role file.

## Status

The workspace was reset on 2026-10-07. The spec is defined by the user. Do not build anything that `SPEC.md` does not ask for. Discovery is the existing block; visualization is the current block.

## What exists

- `discovery/discover.py`: helper for session discovery. `identify --role` stores the role the session's human entered in `discovery/identity/<pid>.json` (label equals role). `self` prints the calling session's name, PID, start path, role, and label, and exits 2 until `identify` has run. `list` prints live sessions, filtered by `--root`. `list` and `done` rebuild `discovery/sessions.json` from the registry plus `identity/` under a file lock; a dead PID is dropped with its identity file. `protocol` and `record` are removed. `ui` is retired in D4; the page is served by `python3 viz/watcher.py serve` on port 4780. Owned by discovery-builder.
- `viz/`: the visualization. `watcher.py` has `map`, `tail`, `state`, `replay`, and `serve`; `serve` runs the poller on port 4780, serves `/state`, `/events`, and `index.html`, and writes `viz/events.jsonl`. Reference frames in `docs/ui-frames.png`. Owned by viz-builder.
- `path_finder/` and `pyproject.toml`: the installable CLI (P1). `pipx install .` gives `path-finder` with `identify`, `self`, `list`, `done` (run `discovery/discover.py` in place), `serve`, `state`, `replay`, `map`, `tail` (run `viz/watcher.py` in place), and `window`, which starts the watcher if nothing answers on the port and opens `/web` in a 380 by 720 px app-mode browser window. Owned by discovery-builder.
- `plugin/` and `.claude-plugin/marketplace.json`: the Claude Code plugin (P2), name `path-finder`, skills `identify` (asks the role, registers the session) and `mesh` (lists live sessions, opens the window), no hooks. Trial: `claude --plugin-dir plugin`; keep: add the checkout as a marketplace, then `claude plugin install`. Owned by discovery-builder.
- `docs/`: `plan-visualization.md`, `cross-session-message-format.md`, `jsonl-transcript-spec.md`, `ui-frames.png`. `SPEC.md` says which to read for which task.
- `.claude/roles/`: one file per role.
- `handoff/<area>/ready.md` and `review.md`: builder to validator handoff.

## How sessions find and talk to each other

- `ListAgents` lists live sessions on this machine by display name. Names are derived from the start folder plus a suffix, change on restart, and can change mid-run. Never hard-code a name. PIDs are stable for a session's life.
- `SendMessage` sends plain text to a session by display name or by socket address (`uds:/tmp/cc-socks/<pid>.sock`). A busy recipient reads it between tool calls; an idle one starts a new turn with it. A received message carries the sender's name and socket address; reply to that address, not to a name.
- `notify_when_idle` on `SendMessage` asks for one notice when the target next goes idle. The notice is an event ("was idle at time T"), not a status, and arrives as a `[Cross-session idle notice]` prompt with no `msg_id`.
- Only Claude sessions send messages in this project. Claude Code documents that scripts and hooks can post to a session's inbox socket, but that is untested here and parked; do not build on it.
- Each session's registry entry at `~/.claude/sessions/<pid>.json` holds its PID, name, and full start path. Undocumented; it is what the discovery helper reads.
- Each session's transcript at `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` records every send, result, received message, idle notice, and turn end. Undocumented; format in `docs/`. The visualization reads it.
- Every received message costs the receiver a full turn. Do not message a session for information that is already on disk. Discovery is self-registration for this reason: `identify` on start, then `list` reads the registry and `identity/`.

## Team rules

- The manager assigns every task by ID. Builders do not start unassigned work.
- Builders work only inside their own folder and write requests for anything else under Requests in their `ready.md`.
- After 3 failed rounds on the same issue, stop and write under Blocked.
- Only the manager runs `git commit` or `git push`.
- Never kill a process you did not start in your own session.
- No hooks for now. If a `hook_non_blocking_error` for `dashboard-hook.js` appears in a transcript, the leftover plugin is still installed; tell the user, do not fix it. As of 2026-10-08 it was still installed (82 such errors in the fake transcripts).

## Protected files

- `~/.claude/settings.json`, `~/.claude/sessions/`, `~/.claude/projects/`, `/tmp/cc-socks/`: read-only, never edited by agents.
- Any `.env` file.