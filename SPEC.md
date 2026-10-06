# SPEC: live Claude Code sessions dashboard

Status: scaffolding only, no code written. Last updated 2026-10-05.

Read `CLAUDE.md` first for architecture, ownership, and team rules. This file holds the current state of each area, known issues, open questions, and the tasks each builder works on next. Every feature to implement is tracked here.

## 1. Goal

A simple, artistic dashboard showing every Claude Code session currently running on this machine and the messages they send each other. Sessions follow no required workflow. Roles such as manager, builder, or validator are optional labels a session may declare.

## 2. How sessions communicate (confirmed in this environment)

- `ListAgents` lists live sessions by name (start folder plus short ID, e.g. `listings-bc`, `tag-analyzer-63`) and whether each is busy or idle.
- `SendMessage` sends plain text to a session by name. It lands in the recipient's inbox and is read at its next turn. Replies come back marked as cross-session messages with the sender's name.
- The channel is a local socket per session (e.g. `/tmp/cc-socks/29904.sock`). Nothing goes over the internet.
- Messages are text only. Permissions are per session. A message cannot approve another session's edits or commands.
- Names change on restart. Never hard-code session names.
- A "notify me when idle" flag on `SendMessage` gives the sender a one-time note when the recipient goes quiet.

## 3. Data capture

Each session reports on itself through user-level hooks in `~/.claude/settings.json`. All hooks append to `~/.claude/dashboard/events.jsonl`, one JSON object per line.

| Hook | Matcher | Meaning | Notes |
|---|---|---|---|
| `SessionStart` | | session appeared | |
| `UserPromptSubmit` | | session is busy | Should also fire when an inbox message starts a turn. Verify. |
| `Stop` | | session is idle | Does not fire on user interrupt. |
| `PostToolUse` | `SendMessage` | outgoing message | Log once, at the sender. |
| `SessionEnd` | | session closed | May not fire if the process dies. |

Event schema:

```json
{"ts":"2026-10-05T21:40:00Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"started","role":null}
{"ts":"2026-10-05T21:40:05Z","type":"message","from":"listings-bc","to":"tag-analyzer-63","text":"L16 is ready, look at it","notify_on_idle":true}
```

`state` is one of `started`, `busy`, `idle`, `ended`. `role` is `null` unless declared.

Liveness fallback: the server periodically checks whether each known PID is alive and marks dead sessions `ended`. The socket filename in `/tmp/cc-socks/` appears to be the PID. Treat it as an undocumented internal.

## 4. Visual direction: "Orbit"

- Each live session is a body on a ring. Position is keyed by start folder, so a restarted session returns to the same spot. Same-folder sessions sit next to each other.
- Busy sessions glow and pulse gently. Idle sessions dim. New sessions fade in. Ended sessions fade out, leaving a faint mark briefly.
- Messages are particles on curved paths between sessions. Messages with `notify_on_idle` trail a thin thread that snaps back to the sender when the recipient goes idle.
- Each body is labeled with its name. Role appears underneath only if declared.
- Timeline strip for scrubbing history. Side panel shows full message text when a particle is clicked.
- Handles 1 to ~15 sessions, including zero (empty ring with "No sessions running").
- Respects `prefers-reduced-motion`. Responsive.

## 5. Current state

### 5.1 webhook (hooks, server, fake generator)

Folder `webhook/` is empty. No runtime chosen. No hooks installed. `~/.claude/settings.json` has an empty `hooks` object. `~/.claude/dashboard/` does not exist.

### 5.2 frontend (HTML visualization)

Folder `frontend/` is empty.

### 5.3 tests

No test framework, no `tests/` folder.

### 5.4 docs

`docs/overview.md` written by the manager. `docs/webhook/` and `docs/frontend/` hold placeholder READMEs.

## 6. Known issues and unknowns

Unverified assumptions that block real hook code. webhook-builder resolves them in task W1 and records answers here.

- W-U1: exact tool name for `SendMessage` under `PostToolUse`, and its input field names (recipient, text, notify flag).
- W-U2: whether a hook can derive the session display name (e.g. `listings-bc`) from `session_id`, `cwd`, or PID. If not, key by PID and map later.
- W-U3: whether `UserPromptSubmit` fires when an inbox message starts a turn.
- W-U4: whether `Stop` fires often enough to be a reliable idle signal, given it skips user interrupts.

Findings:

- W-U1:
- W-U2:
- W-U3:
- W-U4:

Open design questions, manager decides:

- How does a session declare a role? Candidate: an extra event type written by an optional skill.
- How far back does the timeline go? Does the server need to persist beyond replaying `events.jsonl`?
- Who rotates `events.jsonl`?

## 7. Contract between webhook and frontend

Defined in `docs/overview.md`. Summary:

- `GET /` serves `frontend/index.html`.
- `GET /events` is an SSE stream. First event is `snapshot` with the full state. Later events are `session` and `message` with the §3 schema, plus `liveness` when the PID check marks a session ended.
- Snapshot shape: `{ "sessions": [session objects with current state], "messages": [recent message events] }`.

Changes to this contract go through the manager. Either builder requests a change under Requests in `ready.md`.

## 8. Tasks

Status key: `[ ]` not started, `[~]` in progress (write the session name), `[x]` done and reviewed PASS. Update before messaging anyone.

### 8.1 webhook-builder

- [ ] **W1: verify hook behavior.** Write a catch-all hook script in `webhook/hooks/` that appends raw hook input for every event to a temp log. Provide the `settings.json` snippet under Requests. After the manager installs it, send one test message between two sessions, then fill in §6 findings and request removal of the catch-all.
  Acceptance: all four W-U findings filled in with evidence quoted from the raw log. Docs: `docs/webhook/hooks.md` describes the raw hook input shape.
- [ ] **W2: choose runtime.** Pick Node or Bun, add the manifest, and write install and run commands under Requests so the manager updates `CLAUDE.md`.
  Acceptance: a fresh clone can install and run `webhook/` with the documented commands.
- [ ] **W3: real hooks.** Hook script that appends `session` events for `started`, `busy`, `idle`, `ended` and `message` events for `SendMessage`, following §3. Creates `~/.claude/dashboard/` if missing. Never blocks or fails a turn. Snippet under Requests.
  Acceptance: two live sessions produce correct events for start, busy, idle, one message, end. Hook exits 0 and logs nothing to the terminal even when the log dir is unwritable. Docs: `docs/webhook/hooks.md` covers each exported function.
- [ ] **W4: fake event generator.** Script that writes a realistic stream to a chosen path. Covers zero sessions, ~15 sessions, same-folder siblings, a restarted session with a new ID, a session dying without `ended`, and `notify_on_idle` followed by the recipient going idle. Configurable speed.
  Acceptance: output validates against §3 schema. frontend-builder can run it against the page with one command. Docs: `docs/webhook/fake-generator.md`.
- [ ] **W5: server.** Tails `events.jsonl` (path configurable), replays the file on startup, keeps in-memory state, runs the PID liveness check on an interval, serves `GET /` and `GET /events` per §7.
  Acceptance: browser connecting mid-run receives a correct snapshot. Killing a session process marks it ended within one interval. Server survives malformed lines. Docs: `docs/webhook/server.md`, one entry per public function and endpoint.
- [ ] **W6: documentation standard.** Every public function has a one-line docstring. Every module has a file in `docs/webhook/` with what, inputs, output, errors, example.
  Acceptance: validator confirms every documented example produces the documented output.

### 8.2 frontend-builder

- [ ] **F1: static page skeleton.** `frontend/index.html` with no build step. Connects to `/events`, applies the snapshot, applies incremental events. Falls back to loading a local JSON fixture when the SSE endpoint is absent so it can be developed before W5 exists.
  Acceptance: page loads with zero sessions and shows the empty ring with "No sessions running".
- [ ] **F2: ring layout.** Sessions placed on a ring keyed by start folder. Same-folder sessions adjacent. Stable position across restart. Handles 1 to ~15 without label overlap.
  Acceptance: checked against W4 output at 1, 5, and 15 sessions.
- [ ] **F3: state visuals.** Busy glow and pulse, idle dim, fade in on start, fade out with brief faint mark on end. Name label, role underneath only when declared.
- [ ] **F4: message particles.** Curved path from sender to recipient. `notify_on_idle` thread that snaps back to the sender when the recipient's next state is idle.
- [ ] **F5: timeline strip.** Scrub through history. Scrubbing replays state at that moment without losing the live stream.
- [ ] **F6: side panel.** Click a particle to show from, to, time, and full text.
- [ ] **F7: accessibility and responsiveness.** `prefers-reduced-motion` disables pulse, particles become instant markers. Works at phone width.
- [ ] **F8: documentation standard.** One-line docstring on each public function. `docs/frontend/` has one file per module with what, inputs, output, errors, example.
  Acceptance for F3 to F8: validator confirms against W4 output and the docs examples.

### 8.3 validator

- [ ] **V1: propose test structure.** Pick a framework compatible with the runtime from W2. Propose folder layout. Ask the user before creating anything.
- [ ] **V2: unit tests for webhook.** Hook event formatting, state reduction from events, PID liveness with a mocked process check, malformed line handling. Mock the filesystem and process calls.
- [ ] **V3: unit tests for frontend.** Ring position function, state reducer, reduced-motion branch. Use a DOM test environment, no real browser needed.
- [ ] **V4: integration tests.** W4 output through the server into a connected SSE client, using a temp `events.jsonl`. Never the real file.
- [ ] **V5: docs examples.** Every example in `docs/` runs and produces the documented output. Use the runtime's markdown example runner if one exists, otherwise a small script.
- [ ] **V6: review each ready.md** against this file's acceptance criteria. Write `review.md` as PASS or numbered failures with file, line, input, expected, actual. Missing or outdated docs count as failures.

### 8.4 manager

- [ ] M1: install hook snippets from Requests into `~/.claude/settings.json`.
- [ ] M2: update `CLAUDE.md` setup commands after W2.
- [ ] M3: decide the open design questions in §6.
- [ ] M4: packaging, later. Plugin bundle with hooks, optional role-declaring skill, and a `/dashboard` command. Reference model: Graphify.
