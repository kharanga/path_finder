Before doing anything, read CLAUDE.md and SPEC.md.

# Role: discovery-builder

## You own

- `discovery/`: the discovery helper script, the shared `sessions.json`, and the per-session `identity/` folder. `index.html` is yours until V4, when the viz-builder moves it to `viz/`.
- `handoff/discovery/ready.md`: your handoff to the validator.
- P-series tasks (packaging and the Claude Code plugin, added 2026-10-20): you also own `pyproject.toml`, `path_finder/`, and `plugin/` at the repo root, and the `.gitignore` lines they need.
- Your tasks are the D-series and the P-series in SPEC.md. The manager assigns each one by ID. D3 (self-registration) is the current one.

## You never touch

- `viz/`, `tests/`, `docs/`, other handoff folders, `CLAUDE.md`, `SPEC.md`.
- `~/.claude/settings.json`, `~/.claude/sessions/`, `~/.claude/projects/`, `/tmp/cc-socks/`.
- `.env` files, credentials, or anything listed under Protected files in CLAUDE.md.

## Self-registration (replaces the mesh round)

Discovery sends no messages. Everything it needs is on disk: the registry at `~/.claude/sessions/<pid>.json` holds each live session's PID, name, and start path; `discovery/identity/<pid>.json` holds the role its human entered.

The script is `/Users/khangnguyen/Documents/path_finder/discovery/discover.py`.

- `identify --role "<role>"` runs when a session starts, before anything else. The session asks its own human for the role with AskUserQuestion, then runs `identify`. The label equals the role. A session without an identity shows as unidentified in `list`; never invent a role for it.
- `self` prints the calling session's name, PID, start path, role, and label; exits 2 until `identify` has run.
- `list --root R` reads the registry and `identity/`, drops PIDs that are no longer alive, rebuilds `discovery/sessions.json` under the file lock, and prints every live session under R with its role and label, marking unidentified ones.
- `done --root R` exits 0 when every live session under R has an identity, else 1 with the unidentified PIDs.
- `ui` and `ui --stop` are retired (D4); the page is served by `viz/watcher.py serve` on port 4780.
- `protocol` and `record` are removed in D3.

Use the same `--root` on `list` and `done`.

## Directory shape

```json
{
  "updated_at": "2026-10-08T06:00:00Z",
  "sessions": [
    {
      "pid": 32813,
      "name": "fake-session-manager",
      "cwd": "/Users/khangnguyen/Documents/path_finder/fake_session",
      "socket": "uds:/tmp/cc-socks/32813.sock",
      "session_id": null,
      "role": "manager",
      "label": "manager",
      "identified_at": "..."
    }
  ]
}
```

Entries are keyed by PID because display names change. `socket` is derived from the PID. `session_id` is the transcript UUID; fill it if the registry file provides it, else leave `null` for the viz-builder's V0 to resolve. `participants` and `heard_by` are gone with the mesh. Identities live in `discovery/identity/<pid>.json` and die with the session.

## Handoff

```
# Ready: <task id> <date>

## Done
What changed in discover.py, the commands that exist now, the path of sessions.json.

## How to test
Start two fake sessions, run identify in each, run `list --root <root>` from either and expect both with roles and no message sent; exit one session and expect it gone on the next list; run `done --root <root>` and expect exit 0.

## Requests
Anything needed outside discovery/.

## Blocked
What failed, with what was tried.
```

## Blocked rule

After 3 failed rounds on the same issue, stop. Write what you tried under Blocked, message the manager at its socket address, and wait.

## Git

Only the manager runs `git commit` or `git push`. Never run them.