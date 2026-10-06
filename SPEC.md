# SPEC: live Claude Code sessions dashboard

Status: v1 complete (every task through V5 PASS, plugin installed, 350 tests green). v2 in progress: circuit visual and session removal editor, tasks W9, F10, F11, V7. Last updated 2026-10-06.

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
| `Notification` | `permission_prompt` | session is waiting | Emits state `waiting`. The next `UserPromptSubmit` or `Stop` clears it. |
| `SessionEnd` | | session closed | May not fire if the process dies. |

Event schema:

```json
{"ts":"2026-10-05T21:40:00Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"started","role":null}
{"ts":"2026-10-05T21:40:05Z","type":"message","from":"listings-bc","to":"tag-analyzer-63","text":"L16 is ready, look at it","notify_on_idle":true}
```

`message.from` is a string or null; null means the sender's hook could not resolve its own name, and the page must keep the message and draw it from the ring center. `state` is one of `started`, `busy`, `waiting`, `idle`, `ended`, `removed`. `removed` is written only by the server on a manual removal (§4.1). `waiting` means the session is blocked on a permission prompt, emitted from the `Notification` hook when `notification_type` is `permission_prompt`. `role` is `null` unless declared.

Liveness fallback: the server periodically checks whether each known PID is alive and marks dead sessions `ended`. On the same interval it reads `status` from `~/.claude/sessions/<pid>.json` and, when it disagrees with hook state (missed `Stop` after an interrupt), emits a corrective `session` event. Decided 2026-10-05. The socket filename in `/tmp/cc-socks/` appears to be the PID. Treat it as an undocumented internal.

## 4. Visual direction: "Circuit" (v2, replaces Orbit)

User direction 2026-10-06: not a ring. An electrical circuit that passes messages from capsule to capsule.

- Each live session is a capsule, a rounded component on a circuit board. Capsules are grouped by start folder into rows (one row per folder), so a restarted session returns to its folder row. Position inside a row is stable per PID while live.
- Traces are orthogonal wires (horizontal and vertical runs with rounded corners) connecting capsules. A trace is drawn on demand when a message first travels between two capsules and stays faint afterward, so the board shows who talks to whom.
- A message is a pulse: a bright charge that travels along the trace from sender to recipient. Messages with `notify_on_idle` leave the trace charged (glowing) until the recipient's next `idle` event, then the charge drains back to the sender.
- Capsule states: busy lit with a soft electrical flicker, waiting amber and steady, idle dim, started dim with a brief power-on flash, ended fades out leaving a faint footprint briefly, removed disappears immediately with no footprint.
- Each capsule shows its name and, underneath, its role if declared. A capsule for an unknown recipient (name not on the board) is a dashed outline at the end of its folder row, as the placeholder body was.
- Timeline strip, side panel, keyboard access, reduced motion (pulses become instant markers, no flicker), responsive layout: all carried over from v1 unchanged in behavior.
- Empty state: an empty board with "No sessions running".
- Handles 1 to ~15 sessions without overlap. Rows wrap when a folder has many sessions.

### 4.1 Session removal editor

- An "Edit" toggle on the page. In edit mode each capsule shows a remove control. Removing asks for one confirmation, then calls the server.
- `POST /sessions/<pid>/remove` appends a `session` event with state `removed` for that PID (current name, folder, role) to `events.jsonl` and broadcasts it. Returns 204, or 404 when the PID is unknown.
- `removed` is a sixth session state. The reducer treats it as not live. The page drops the capsule immediately with no footprint. If the session later emits any event, it reappears, which is the intended way to recover a mistaken removal of a live session.
- Edit mode also offers "Remove all ended" as one action, which removes every session currently in state `ended`.

## 5. Current state

### 5.1 webhook (hooks, server, fake generator)

W1 to W8 all PASS. Hooks run from the installed plugin `cc-dashboard@path-finder`, writing to `~/.claude/dashboard/events.jsonl`. Server, fake generator, role declaration, and plugin bundle complete.

### 5.2 frontend (HTML visualization)

F1 to F9 all PASS. Frontend complete.

### 5.3 tests

`node:test`, suite in `tests/`: unit (V2, V3), integration (V4), and docs examples (V5) all complete. 350 tests, about 2 s. See `tests/README.md`.

### 5.4 docs

`docs/overview.md` written by the manager. `docs/webhook/` and `docs/frontend/` hold placeholder READMEs.

## 6. Known issues and unknowns

Unverified assumptions that block real hook code. webhook-builder resolves them in task W1 and records answers here.

- W-U1: exact tool name for `SendMessage` under `PostToolUse`, and its input field names (recipient, text, notify flag).
- W-U2: whether a hook can derive the session display name (e.g. `listings-bc`) from `session_id`, `cwd`, or PID. If not, key by PID and map later.
- W-U3: whether `UserPromptSubmit` fires when an inbox message starts a turn.
- W-U4: whether `Stop` fires often enough to be a reliable idle signal, given it skips user interrupts.

Findings:

- W-U1 (confirmed from the raw log): `PreToolUse` and `PostToolUse` both fire with `tool_name` `SendMessage`. `tool_input` carries `to`, `message`, `notify_when_idle`, and optionally `summary`. Evidence, redacted record from this session's test send: `{"hook_event_name":"PostToolUse","tool_name":"SendMessage","tool_input":{"to":"path-finder-e5","notify_when_idle":true}}` with shape `tool_input: {to: string(13), message: string(145), notify_when_idle: boolean, summary: string(32)}`. The hook logs the message once, at `PostToolUse`, so a send that fails permission at `PreToolUse` is not counted. Mapping to §3: `to` -> `to`, `message` -> `text`, `notify_when_idle` -> `notify_on_idle` (false when absent). The sender's name is not in `tool_input`; the hook resolves it per W-U2.
- W-U2 (confirmed by reading the files on this machine): Claude Code writes `~/.claude/sessions/<pid>.json` with `{"pid":52134,"sessionId":"177234a7-...","cwd":"/Users/khangnguyen/Documents/path_finder","name":"path-finder-37","nameSource":"derived","status":"busy","messagingSocketPath":"/tmp/cc-socks/52134.sock",...}`. A hook matches its `session_id` to `sessionId` and gets both the PID and the display name. The name is not derivable from `session_id` alone (`path-finder-37` vs session id ending `...fd49`). Fallback when the file is missing: walk `ps -o ppid=,comm=` from the hook's parent to the `claude` process, observed in every raw record as `hook -> /bin/zsh -> claude`. Both are undocumented internals; names may be renamed later (`formerNames` field exists), so the hook re-reads the file on every event.
- W-U3 (confirmed, yes): `UserPromptSubmit` fires when an inbox message is delivered, not only when the user types. Evidence: this session sent `SendMessage` to `path-finder-e5` at 06:03:57Z; the raw log shows `path-finder-e5` (PID 40707) `UserPromptSubmit` at 06:04:10Z with no human input in between. Same pattern for `path-finder-e5` sending to `path-finder-18` at 06:04:48Z, followed by `path-finder-18` `UserPromptSubmit` at 06:04:53Z. Caveat: delivery to a session that is already mid-turn also fires `UserPromptSubmit` (this session received two while running tools, at 06:03:21Z and 06:03:32Z). So a `busy` event can arrive for a session that is already busy; the reducer treats it as a no-op state change.
- W-U4 (confirmed, reliable for normal turn ends): `Stop` fires at the end of every completed turn with `stop_hook_active: false`. Evidence: `path-finder-0d` (PID 29248) `Stop` at 06:04:33Z then `UserPromptSubmit` at 06:04:49Z on its next turn; `path-finder-e5` `Stop` at 06:04:57Z after processing the test message. Gaps: user interrupt (Escape) skips `Stop`, and a session waiting on a permission prompt is still "busy" by hook state. The `Notification` hook fires in that case (observed for PID 29248 at 06:04:09Z with `notification_type` of length 17, consistent with `permission_prompt`). Mitigation available to the server: `~/.claude/sessions/<pid>.json` has a `status` field (`busy`, `idle`) that ListAgents also uses; polling it on the liveness interval would correct a missed `Stop`. Manager decides whether to add a `waiting` state or a poll.
- Extra fields observed per event, all values redacted: every event has `session_id`, `transcript_path`, `cwd`, `scratchpad_dir`, `prompt_id`, `hook_event_name`; `UserPromptSubmit` adds `permission_mode`, `prompt`; `Stop` adds `permission_mode`, `effort.level`, `stop_hook_active`, `last_assistant_message`, `background_tasks`, `session_crons`; `Notification` adds `message`, `notification_type`; `PostToolUse` adds `tool_name`, `tool_input`, `tool_response`. No `SessionStart` or `SessionEnd` was observed because no session started or ended during the window; their `source` and `reason` fields are kept by the catch-all for the next restart.
- Hooks installed into `~/.claude/settings.json` took effect in already-running sessions within seconds, no restart needed.
- Rename observed 2026-10-05: Claude Code renamed the manager session mid-run from `path-finder-0d` to `manager-drives-feature-work` (registry `nameSource` changed, PID unchanged). The hook re-reads the registry per event, so later events carry the new name and the reducer keeps the body under the same PID. Messages sent before the rename still say `from: path-finder-0d`, and ListAgents now shows only the new name. Consequence: the page must not resolve message endpoints by name alone. Task F9.

Design decisions, 2026-10-05:

- Role declaration: a session runs `node webhook/declare-role.js <role>`. The script resolves its own session the same way the hook does (registry by PID walk) and appends a `session` event with the current state and `role` set. The reducer already keeps the last non-null role. The optional skill teaches sessions to run it. Task W7.
- Timeline depth: the server replays all of `events.jsonl` on start and keeps the last 500 messages in memory (`state.js` limit). The page timeline covers what the snapshot holds. No further persistence.
- Rotation: none in v1. `events.jsonl` is append-only; the user truncates it by hand. The server tolerates a truncated file on restart.

## 7. Contract between webhook and frontend

Defined in `docs/overview.md`. Summary:

- `message.from` may be null when the sender's name lookup fails. The page keeps such messages and draws them from the ring center.
- `GET /` serves `frontend/index.html`. All other non-`/events` paths are static files from `frontend/` (ES modules, css, json fixtures), no path traversal.
- `GET /snapshot` returns the same snapshot object as JSON, for tests and curl.
- `POST /sessions/<pid>/remove` appends a `removed` session event and broadcasts it. 204 on success, 404 for an unknown PID. Snapshot excludes removed sessions.
- `GET /events` is an SSE stream. First event is `snapshot` with the full state. Later events are `session` and `message` with the §3 schema, plus `liveness` when the PID check marks a session ended.
- Snapshot shape: `{ "sessions": [session objects with current state], "messages": [recent message events] }`.

Changes to this contract go through the manager. Either builder requests a change under Requests in `ready.md`.

## 8. Tasks

Status key: `[ ]` not started, `[~]` in progress (write the session name), `[x]` done and reviewed PASS. The manager assigns tasks by ID. Builders do not start unassigned tasks. Update before messaging anyone.

### 8.1 webhook-builder

- [x] **W1: verify hook behavior.** Write a catch-all hook script in `webhook/hooks/` that appends raw hook input for every event to a temp log. Provide the `settings.json` snippet under Requests. After the manager installs it, send one test message between two sessions, then fill in §6 findings and request removal of the catch-all.
  Acceptance: all four W-U findings filled in with evidence quoted from the raw log. Docs: `docs/webhook/hooks.md` describes the raw hook input shape.
- [x] **W2: choose runtime.** Runtime is Node 24 (only runtime installed, decided by manager 2026-10-05). Add `webhook/package.json` and write run commands under Requests so the manager updates `CLAUDE.md`.
  Acceptance: a fresh clone can install and run `webhook/` with the documented commands.
- [x] **W3: real hooks.** PASS 2026-10-05; started/ended verified live with a throwaway headless session (started, busy, idle, ended in 2 s, correct name and PID). Hook script that appends `session` events for `started`, `busy`, `idle`, `ended` and `message` events for `SendMessage`, following §3. Creates `~/.claude/dashboard/` if missing. Never blocks or fails a turn. Snippet under Requests.
  Acceptance: two live sessions produce correct events for start, busy, idle, one message, end. Hook exits 0 and logs nothing to the terminal even when the log dir is unwritable. Docs: `docs/webhook/hooks.md` covers each exported function.
- [x] **W4: fake event generator.** Script that writes a realistic stream to a chosen path. Covers zero sessions, ~15 sessions, same-folder siblings, a restarted session with a new ID, a session dying without `ended`, and `notify_on_idle` followed by the recipient going idle. Configurable speed.
  Acceptance: output validates against §3 schema. frontend-builder can run it against the page with one command. Docs: `docs/webhook/fake-generator.md`.
- [x] **W5: server.** Tails `events.jsonl` (path configurable), replays the file on startup, keeps in-memory state, runs the PID liveness check on an interval, serves `GET /`, static files from `frontend/`, and `GET /events` per §7.
  Acceptance: browser connecting mid-run receives a correct snapshot. Killing a session process marks it ended within one interval. Server survives malformed lines. Docs: `docs/webhook/server.md`, one entry per public function and endpoint.
- [x] **W6: documentation standard.** Every public function has a one-line docstring. Every module has a file in `docs/webhook/` with what, inputs, output, errors, example.
  Acceptance: validator confirms every documented example produces the documented output.

- [x] **W7: role declaration.** `webhook/declare-role.js <role>` appends a `session` event for the calling session with `role` set, resolving PID and name like the hook. Prints nothing on success, exits 0, exits 1 with one line on stderr if the session cannot be resolved.
  Acceptance: run from a live session, the ring shows the role under that body within one tail interval. Docs: `docs/webhook/declare-role.md`.
- [x] **W8: plugin bundle.** Package hooks, server, the `declare-role` skill, and a `/dashboard` command as a Claude Code plugin so another machine can install it without editing `settings.json` by hand. Hook commands must not hard-code this repo's path or the nvm node path. Research the current plugin manifest format first and put the proposed layout under Requests before building. The bundled skill re-declares the role on SessionStart so roles survive log truncation. Approved 2026-10-05: repo root is the plugin root; webhook-builder owns `.claude-plugin/`, `hooks/`, `commands/`, `skills/`; roles persist in `~/.claude/dashboard/roles.json` keyed by cwd (two sessions in one folder share a role, accepted); the W3 settings snippet stays until the validator verifies the plugin, then the manager removes it.
  Acceptance: documented install steps on a clean checkout produce working hooks and a running dashboard. Docs: `docs/webhook/plugin.md`.

- [~] path-finder-37 **W9: session removal endpoint.** Add state `removed` to `schema.js`. `POST /sessions/<pid>/remove` appends a `session` event with state `removed` (current name, folder, role) and broadcasts it; 404 for unknown PID. Snapshot and `liveSessions` exclude removed sessions. Removed sessions reappear on any later event for that PID. Add a `removed` scenario to `fake.js`.
  Acceptance: curl the endpoint against the demo server, the capsule disappears from the snapshot, restart the server and it stays gone, a new event for the PID brings it back. Docs updated.

### 8.2 frontend-builder

- [x] **F1: static page skeleton.** `frontend/index.html` with no build step. Connects to `/events`, applies the snapshot, applies incremental events. Falls back to loading a local JSON fixture when the SSE endpoint is absent so it can be developed before W5 exists.
  Acceptance: page loads with zero sessions and shows the empty ring with "No sessions running".
- [x] **F2: ring layout.** Decision 2026-10-05: folder-group stability is sufficient, slot order inside a folder follows name order. Sessions placed on a ring keyed by start folder. Same-folder sessions adjacent. Stable position across restart. Handles 1 to ~15 without label overlap.
  Acceptance: checked against W4 output at 1, 5, and 15 sessions.
- [x] **F3: state visuals.** Busy glow and pulse, idle dim, fade in on start, fade out with brief faint mark on end. Name label, role underneath only when declared.
- [x] **F4: message particles.** Curved path from sender to recipient. `notify_on_idle` thread that snaps back to the sender when the recipient's next state is idle. Decision 2026-10-05: a message to a name not yet on the ring creates a faint placeholder body at the folder slot derived from the name prefix (strip the trailing `-<id>`), labeled with the name; it merges when a real session event arrives and fades after 60 s without one.
- [x] **F5: timeline strip.** Scrub through history. Scrubbing replays state at that moment without losing the live stream.
- [x] **F6: side panel.** Click a particle to show from, to, time, and full text.
- [x] **F7: accessibility and responsiveness.** `prefers-reduced-motion` disables pulse, particles become instant markers. Works at phone width. Decision 2026-10-05: message ticks on the timeline open the same side panel, so past messages are reachable while scrubbing.
- [x] **F8: documentation standard.** One-line docstring on each public function. `docs/frontend/` has one file per module with what, inputs, output, errors, example.
  Acceptance for F3 to F8: validator confirms against W4 output and the docs examples.

- [x] **F9: session renames.** A session can be renamed mid-run (see §6). Resolve message endpoints to bodies by PID when the name matches no live body but matches a former name of one; keep a per-PID list of former names from session events; never create a placeholder body for a former name of a live session. Label updates in place with a brief highlight.
  Acceptance: W4 rename scenario shows one body throughout with the label changing, messages before and after the rename attach to it, no placeholder appears. Docs updated.

- [~] path-finder-18 **F10: circuit visual.** Replace the ring with the board layout in §4: folder rows, capsules, orthogonal traces drawn on first message and kept faint, pulses along traces, charged traces for notify threads, capsule states per §4. Timeline, panel, keyboard, reduced motion, and responsiveness keep working. Pure layout functions in `layout.js` so V3 tests can be updated.
  Acceptance: W4 output at 1, 5, and 15 sessions shows readable rows with no overlap; every message produces a visible pulse; a notify thread drains on idle; reduced motion shows no animation. Docs updated, including `docs/frontend/README.md` naming.
- [ ] **F11: removal editor.** Edit toggle, per-capsule remove control with one confirmation, "Remove all ended", calls `POST /sessions/<pid>/remove`, drops the capsule on the resulting `removed` event with no footprint. Disabled with a hint in fixture mode where no server exists.
  Acceptance: remove a live and an ended session on the demo server, both vanish, page reload shows them still gone, a new event for the live one brings it back. Docs updated.

### 8.3 validator

- [x] **V1: test structure.** `node:test`, `tests/` with `unit/`, `integration/`, `docs-examples/`, `helpers/`. Run with `node --test "tests/**/*.test.js"`. Done 2026-10-05.
- [x] **V2: unit tests for webhook.** Hook event formatting, state reduction from events, PID liveness with a mocked process check, malformed line handling. Mock the filesystem and process calls.
- [x] **V3: unit tests for frontend.** Ring position function, state reducer, reduced-motion branch. Use a DOM test environment, no real browser needed.
- [x] **V4: integration tests.** W4 output through the server into a connected SSE client, using a temp `events.jsonl`. Never the real file. Include the rename scenario (§6) and a role declaration via `declare-role.js` against the temp file.
- [x] **V5: docs examples.** Every example in `docs/` runs and produces the documented output. Use the runtime's markdown example runner if one exists, otherwise a small script.
- [x] **V6: review each ready.md** (ongoing duty, exercised on every task) against this file's acceptance criteria. Write `review.md` as PASS or numbered failures with file, line, input, expected, actual. Missing or outdated docs count as failures.

- [ ] **V7: v2 verification.** Update V3 layout tests for the board layout, add unit tests for the `removed` state in both reducers, an integration test for the removal endpoint including persistence across restart, and re-run all docs examples.

### 8.4 manager

- [x] M1: hooks now come from the installed plugin `cc-dashboard@path-finder` (user scope, installed 2026-10-06). Hand-written snippet removed from `~/.claude/settings.json`. Verified with a throwaway headless session: four events, each logged once.
- [x] M2: update `CLAUDE.md` setup commands after W2.
- [x] M3: design questions in §6 decided 2026-10-05: waiting state plus status poll, role declaration via W7, timeline depth equals snapshot, no rotation in v1.
- [x] M4: packaging done as W7 and W8. Plugin installed on this machine from the local checkout.
