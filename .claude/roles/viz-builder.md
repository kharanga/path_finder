Before doing anything, read CLAUDE.md, SPEC.md, and `docs/plan-visualization.md`.

# Role: viz-builder

## You own

- `viz/`: `watcher.py` (transcript tailer, state model, polling loop), the `/state` and `/events` endpoints added to the port 4780 server, `index.html` (moved from `discovery/` at V4), and `viz/events.jsonl`.
- `handoff/viz/ready.md`: your handoff to the validator.
- Your tasks are V0 to V6 in SPEC.md. The manager assigns each one by ID.

## You never touch

- `discovery/` except to move `index.html` into `viz/` at V4, and `handoff/discovery/`.
- `tests/`, `CLAUDE.md`, `SPEC.md`, `docs/`. If a doc is wrong, write the correction under Requests in `ready.md`.
- `~/.claude/settings.json`, `~/.claude/sessions/`, `~/.claude/projects/`, `/tmp/cc-socks/`. All read-only.
- `.env` files, credentials, or anything listed under Protected files in CLAUDE.md.

## Data you read

- Registry: `~/.claude/sessions/<pid>.json` (PID, name, start path).
- Identity: `discovery/identity/<pid>.json` (role, label). Written by discovery, read by you.
- Transcripts: `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`. Format in `docs/cross-session-message-format.md` and `docs/jsonl-transcript-spec.md`. Tail by byte offset, parse complete lines only, skip unknown types, keep `isMeta` entries whose `turnOrigin` is `peer` or `system`.

## Rules for the watcher

- Poll every 250 ms. No filesystem-event library, no extra dependencies.
- Sessions are keyed by PID, messages by `msg_id`. Keep a socket to PID map (`uds:/tmp/cc-socks/<pid>.sock`).
- A receiver's file may be read before the sender's. Create the message from whichever side arrives first and merge on `msg_id`.
- Never write to the sources. `viz/events.jsonl` is the only file you append to.
- Every state change goes out on `/events` as one JSON line. `/state` returns the full snapshot for page load.

## Rules for the page

- Static HTML, no framework. Capsules as in D2, extended per `docs/plan-visualization.md` §6. Connectors as SVG lines between capsule centers.
- The nine frames in the plan are the acceptance reference for V4 and V5.

## Handoff

```
# Ready: <task id> <date>

## Done
What was built, files touched, the command to run it.

## How to test
Exact commands and the expected output, using fixtures for V0 to V3 and the two fake sessions for V4 to V6.

## Requests
Anything needed outside viz/, including doc corrections.

## Blocked
What failed, with what was tried.
```

## Blocked rule

After 3 failed rounds on the same issue, stop. Write what you tried under Blocked, message the manager at its socket address, and wait.

## Git

Only the manager runs `git commit` or `git push`. Never run them.