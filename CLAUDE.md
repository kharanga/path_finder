# path_finder: live Claude Code sessions dashboard

Every agent reads this file first, then `SPEC.md`.

## What the app does

A local-only dashboard that shows every Claude Code session running on this machine and the messages they send each other. Sessions appear as bodies on a ring. Busy sessions glow, idle sessions dim, and messages travel as particles between them. Nothing leaves the machine.

## Architecture and data flow

1. User-level Claude Code hooks (configured in `~/.claude/settings.json`) run on `SessionStart`, `UserPromptSubmit`, `Stop`, `PostToolUse` for `SendMessage`, and `SessionEnd`. Each appends one JSON line to `~/.claude/dashboard/events.jsonl`.
2. A small server in `webhook/` tails that file, rebuilds state on startup, checks whether each session's PID is still alive, and streams updates to the browser over Server-Sent Events. It sends a full state snapshot when a browser connects.
3. A single HTML page in `frontend/` renders the "Orbit" visualization from the snapshot plus incremental events.

Event schema and the contract between server and page live in `docs/overview.md`. The full spec is `SPEC.md`.

## Areas and ownership

| Area | Folder | Owner | Docs |
|---|---|---|---|
| Hooks, SSE server, fake event generator | `webhook/` | webhook-builder | `docs/webhook/` |
| Plugin packaging: manifests, hook config, command, skill | `.claude-plugin/`, `hooks/`, `commands/`, `skills/` | webhook-builder | `docs/webhook/plugin.md` |
| HTML visualization | `frontend/` | frontend-builder | `docs/frontend/` |
| Tests | `tests/` (unit, integration, docs-examples, helpers) | validator | `tests/README.md`, review files |
| This file, `SPEC.md`, `docs/overview.md`, git | repo root | manager | `docs/overview.md` |

## Setup, run, test

Runtime is Node 24, the only runtime installed on this machine. The manifest is `webhook/package.json`. The page has no build step.

```
# install (no dependencies, checks the manifest only)
cd webhook && npm install

# run server (after W5), prints the dashboard URL, default http://127.0.0.1:4747
node webhook/server.js

# demo with fake data (after W4 and W5)
node webhook/server.js --demo

# run tests
node --test "tests/**/*.test.js"
```

## Coding conventions

- Every public function, class, or endpoint gets a one-line summary comment or docstring, nothing more. This project rule replaces the global "no comments" rule. No other comments. Put meaning in names.
- Hooks must be fast, append-only, and never block or fail a turn. Swallow errors.
- Log each cross-session message once, at the sender.
- Key sessions by PID when a display name is not available, then map to the display name later.
- Never hard-code session names. They change on restart.
- Treat `/tmp/cc-socks/` as an undocumented internal. Use it only as a liveness fallback.
- The page must handle 0 to ~15 sessions, respect `prefers-reduced-motion`, and stay responsive.
- Builders update `docs/<area>/` in the same task as the code change. A task is not done until the docs match the code.

## Protected files

Never read out their contents or write to them from tests.

- `~/.claude/settings.json`: shared config. Only the manager edits it. Builders put the needed snippet under Requests in `ready.md`.
- `~/.claude/dashboard/events.jsonl`: real session data. Tests use a temp copy.
- `/tmp/cc-socks/`: Claude Code internal. Read-only fallback.
- Any `.env` file.

## Where documentation lives

- `CLAUDE.md`: this guide.
- `SPEC.md`: current state, known issues, tasks per builder with acceptance criteria.
- `docs/overview.md`: architecture, event schema, server-to-page contract. Manager owns it.
- `docs/webhook/`, `docs/frontend/`: one markdown file per module, documenting each public function with what it does, inputs, output, errors, and a realistic example. The builder owns its folder.

## How the team works

- Roles are in `.claude/roles/`. Each agent reads its own role file after this file and `SPEC.md`.
- The manager assigns every task. A builder starts a task only when the manager sends it by ID (for example `W3`). Builders never pick the next task from `SPEC.md` on their own. After a PASS, the builder reports to the manager and waits for the next assignment.
- Builders work only inside their own folder and docs folder. A change needed elsewhere goes under Requests in their `ready.md`.
- When a builder finishes a task it writes `handoff/<area>/ready.md` with sections Done, How to test, Requests, Blocked. The validator tests it and writes `handoff/<area>/review.md` with PASS or numbered failures.
- After 3 failed rounds on the same issue, the agent stops and writes under Blocked. The manager resolves it.
- Only the manager runs `git commit` or `git push`.
- Sessions can find each other with `ListAgents` and message with `SendMessage`. Messages are short pointers to files, not content.
