# Claude Code Transcript JSONL — Reference Spec for the Session Visualizer

> **Purpose:** Instructions for building a live visualizer that watches Claude Code session transcripts and displays cross-session communication (who messaged whom, delivery status, session state).
>
> **Source & confidence:** Claude Code does NOT officially document this format. Field definitions come from the community parser `claude-code-transcripts` (Rust crate v0.1.12, Aug 2026), cross-checked against a real transcript from Claude Code v2.1.292. Items marked **⚠️ VERIFY** must be confirmed against real logs before relying on them.

---

## 1. Where the data lives

- Path: `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`
  - `<encoded-cwd>` = the session's working directory with every non-alphanumeric character replaced by `-` (e.g. `/Users/me/path_finder` → `-Users-me-path-finder`). The encoding is lossy; don't try to reverse it — read `cwd` from the entries, or glob on the session id from the registry (message-format doc §6).
- One file per session, named by session UUID.
- Append-only: one JSON object per line, new lines added as the session runs.
- Hooks receive the file path as `transcript_path`.

---

## 2. Listener requirements (MUST)

1. Watch the whole `~/.claude/projects/` directory recursively; new sessions create new files.
2. Track a byte offset per file; on change, read only new bytes.
3. Only parse complete lines (ending in `\n`). Buffer partial lines until finished.
4. Wrap every `JSON.parse` in try/catch. Skip malformed lines; never crash.
5. Unknown `type` values: log once per type, then ignore. The format changes between Claude Code versions.
6. Skip entries with `isSidechain: true` from the main graph (subagent work), or show them nested under their session.
7. Skip entries with `isMeta: true`, except those whose `turnOrigin` is `peer` or `system`: they carry received messages and idle notices (message-format doc §0).
8. Optional fields may be missing at any time — always use safe access (`?.`) and defaults.

---

## 3. The envelope (common fields)

Present on conversational entries: `user`, `assistant`, `system`, `attachment`, `progress`.

```jsonc
{
  "type": "assistant",
  "uuid": "…",                 // unique id of this entry
  "parentUuid": "…",           // previous entry; null = first in session
  "logicalParentUuid": "…",    // optional; preserves chain across compaction
  "isSidechain": false,        // true = subagent
  "sessionId": "…",            // camelCase session id
  "session_id": "…",           // optional snake_case copy; can differ on resumed sessions
  "timestamp": "2026-10-08T04:03:07.164Z",  // ISO 8601 — use for ordering
  "cwd": "/Users/…/repo",
  "gitBranch": "main",
  "version": "2.1.292",        // Claude Code version
  "entrypoint": "cli",         // optional
  "agentName": "…",            // optional
  "agentColor": "…",           // optional
  "sessionKind": "bg",         // optional; "bg" = background session, absent = interactive
  "isMeta": true,              // optional; hidden in UI
  "forkedFrom": { "sessionId": "…", "messageUuid": "…" }  // optional
}
```

---

## 4. Entry types — INCLUDE

### 4.1 `agent-name` — session label (no envelope)
```json
{ "type": "agent-name", "agentName": "fake-session-builder", "sessionId": "…" }
```
- **Use:** primary node label; the name other sessions use to message this one. Latest value wins.

### 4.2 `custom-title` / `ai-title` — fallback labels (no envelope)
```json
{ "type": "custom-title", "customTitle": "fake-session-builder", "sessionId": "…" }
{ "type": "ai-title", "aiTitle": "Fake session builder", "sessionId": "…" }
```
- **Use:** label priority: `agentName` → `customTitle` → `aiTitle` → short session id.

### 4.3 `permission-mode` (no envelope)
```json
{ "type": "permission-mode", "permissionMode": "auto", "sessionId": "…" }
```
- Values seen/expected: `default`, `auto`, `acceptEdits`, `dontAsk`, `plan`, `bypassPermissions`.
- **Use:** badge on node. Derive permission group:
  - **bypassing** = `bypassPermissions` (and `plan` when bypass is available — treat as uncertain)
  - **prompting** = everything else
- With default inbound settings, messages between sessions in DIFFERENT groups are held for approval → color predicted edges amber.

### 4.4 `mode` (no envelope)
```json
{ "type": "mode", "mode": "normal", "sessionId": "…" }
```
- Values: `normal`, `coordinator`. **Use:** small badge.

### 4.5 `last-prompt` (no envelope)
```json
{ "type": "last-prompt", "lastPrompt": "…", "leafUuid": "…", "sessionId": "…" }
```
- **Use:** tooltip "currently working on…". Truncate long text.

### 4.6 `summary` (no envelope)
```json
{ "type": "summary", "summary": "…", "leafUuid": "…", "sessionId": "…" }
```
- **Use:** one-line status under the node.

### 4.7 `assistant` — Claude's turn (contains outgoing messages)
```jsonc
{
  "type": "assistant",
  "message": {
    "id": "msg_…",
    "model": "claude-fable-5-1",
    "role": "assistant",
    "stop_reason": "end_turn",     // "end_turn" | "tool_use" | "max_tokens" | "stop_sequence" | null
    "content": [
      { "type": "text", "text": "…" },
      { "type": "thinking", "thinking": "", "signature": "…" },   // always redacted; ignore
      { "type": "redacted_thinking", "data": "…" },               // ignore
      { "type": "tool_use", "id": "toolu_…", "name": "SendMessage", "input": { } }
    ],
    "usage": {
      "input_tokens": 32,
      "output_tokens": 54,
      "cache_read_input_tokens": 74125,
      "cache_creation_input_tokens": 301
    }
  },
  "requestId": "req_…",
  "error": "…",              // only on failed turns
  "apiErrorStatus": 429,     // only on failed turns
  "isApiErrorMessage": true  // only on failed turns
}
```
- **Detect outgoing message:** `message.content[]` block with `type == "tool_use"` and `name == "SendMessage"`.
  - Store `id` (tool_use id) → pending send.
  - ⚠️ VERIFY: field names inside `input` (target name, message text, `notify_when_idle`) are undocumented. Print a real one first.
- **Detect discovery:** `tool_use` with `name == "ListAgents"`.
- **Tokens:** sum `usage` fields per session for cost; attribute turns triggered by incoming messages to "coordination cost".
- **Display:** SendMessage → animated edge/pulse from sender to target node, labeled with first line of the message.

### 4.8 `user` — prompts, tool results, likely incoming messages
```jsonc
{
  "type": "user",
  "message": {
    "role": "user",
    "content": "plain prompt text"          // EITHER a string
    // OR an array of blocks:
    // [ { "type": "text", "text": "…" },
    //   { "type": "tool_result", "tool_use_id": "toolu_…", "content": "…" | [blocks], "is_error": false },
    //   { "type": "image", "source": { } },
    //   { "type": "document", "source": { }, "title": "…" } ]
  },
  "toolUseResult": { },            // optional structured result (set by Claude Code)
  "sourceToolUseID": "toolu_…",    // optional; which tool_use this answers
  "sourceToolAssistantUUID": "…",  // optional; which assistant entry requested it
  "permissionMode": "auto",        // optional
  "promptSource": "typed",         // optional: "typed" | "system" | "queued" | "suggestion_accepted"
  "origin": { "kind": "human" },   // optional; where the prompt came from
  "isCompactSummary": true         // optional; compaction summary → skip
}
```
- **Send result:** match `tool_result.tool_use_id` to a pending SendMessage `tool_use.id`.
  - `is_error: true` or content starting with `Not sent` → mark edge FAILED (red, dashed), show reason.
  - Otherwise → mark edge SENT.
- **Incoming peer message:** confirmed 2026-10-20. A `user` entry when the receiver is idle, or a `queued_command` attachment (see 4.10) when it is busy, whose `origin.kind` is `"peer"`; both carry `origin.msg_id`. Only `"human"` has been observed so far. Confirm by sending a test message and inspecting the receiver's file.
- **Display:** incoming message → edge arrival animation at receiver; show full text in a side panel on click.

### 4.9 `system` — status events
```jsonc
{ "type": "system", "subtype": "turn_duration", "durationMs": 6549, "messageCount": 296 }
{ "type": "system", "subtype": "stop_hook_summary", "hookCount": 1,
  "hookInfos": [ { "command": "…", "durationMs": 12 } ],
  "hookErrors": [ "…" ], "preventedContinuation": false, "stopReason": "" }
{ "type": "system", "subtype": "api_error", "retryInMs": 2000, "retryAttempt": 1, "maxRetries": 10 }
```
- Known subtypes: `turn_duration`, `stop_hook_summary`, `api_error`, `compact_boundary`, `microcompact_boundary`, `away_summary`, `bridge_status`, `informational`, `local_command`, `scheduled_task_fire`, `permission_retry`, `agents_killed`.
- **Display:**
  - `turn_duration` → turn ended → node state IDLE (unless more input queued).
  - `api_error` → warning icon + retry count.
  - `stop_hook_summary` with non-empty `hookErrors` → warning icon with error text.
  - `compact_boundary` / `microcompact_boundary` → small "context compacted" marker on timeline.
  - `away_summary` → optional status text.

### 4.10 `attachment` — hooks and queued input
```jsonc
{ "type": "attachment", "attachment": {
    "type": "hook_non_blocking_error",    // hook_success | hook_non_blocking_error | hook_blocking_error | hook_cancelled
    "hookName": "Stop", "hookEvent": "Stop", "toolUseID": "…",
    "exitCode": 127, "stdout": "", "stderr": "…", "command": "…", "durationMs": 12 } }

{ "type": "attachment", "attachment": {
    "type": "queued_command",             // input that arrived while the session was busy
    "prompt": "go",                       // string OR array of content blocks
    "commandMode": "prompt",
    "timestamp": "…",
    "origin": { "kind": "human" },
    "source_uuid": "…",                   // snake_case here
    "isMeta": true } }
```
- **Keep:** `hook_*` (errors → warning icon) and `queued_command` (queue counter; with `attachment.origin.kind == "peer"` it is a peer message delivered mid-turn and counts as the read, confirmed 2026-10-20, V12).
- **Skip** all other attachment types (~35 total: file, directory, skill_listing, plan_mode, todo_reminder, diagnostics, nested_memory, etc.).

### 4.11 `progress` — live activity (seen in the 2026-10-08 fixtures; skipped by the watcher in v1)
```jsonc
{ "type": "progress", "toolUseID": "toolu_…", "parentToolUseID": "…",
  "data": { "type": "…", "toolName": "…", "status": "…", "elapsedTimeMs": 1200,
            "taskDescription": "…", "agentId": "…", "hookEvent": "…", "serverName": "…" } }
```
- `data.type` = kind of progress (bash, MCP tool, subagent, hook, search). All `data` fields optional.
- **Display:** node state WORKING + subtle pulse; optionally show `toolName` / `taskDescription`. High frequency — throttle UI updates.

### 4.12 `queue-operation` — the session's input queue (no envelope)
```json
{ "type": "queue-operation", "operation": "…", "content": "…", "timestamp": "…", "sessionId": "…" }
```
- ⚠️ VERIFY: possible `operation` values are unknown (likely enqueue/dequeue-style). Log them.
- **Display:** queue counter badge on node. Directly relevant to conflict detection.

---

## 5. Entry types — SKIP (internal bookkeeping)

`file-history-snapshot`, `file-history-delta`, `attribution-snapshot`, `content-replacement`, `marble-origami-commit`, `marble-origami-snapshot` (context-collapse internals), `speculation-accept`, `atis-latch`, `artifact-autoreact-ledger`, `artifact-comment-monitor`, `agent-setting`.

## 6. Entry types — OPTIONAL (later)

| Type | Possible use |
| :- | :- |
| `agent-color` | Node color matching the terminal |
| `task-summary` | Status text |
| `worktree-state` | Group nodes by git worktree |
| `pr-link`, `tag` | Chips on node |
| `bridge-session` | Remote Control / cross-machine indicator |
| `fork-context-ref`, `frame-link` | "Related session" edges |

---

## 7. Derived state the app must compute

**Per session (node):**
- `label`: agentName → customTitle → aiTitle → short id
- `permissionMode`, `permissionGroup` (prompting | bypassing), `mode`
- `state`: WORKING (recent `progress` / `assistant` with `stop_reason: "tool_use"`), IDLE (after `turn_duration`), ERROR (api_error / hook error)
- `queueCount` (from `queue-operation` / `queued_command`)
- `lastPrompt`, `summary`
- `tokens`: running totals from `assistant.message.usage`
- `cwd`, `gitBranch`, `sessionKind`

**Per message (edge):**
- `id` = SendMessage `tool_use.id`
- `from` = sender session, `to` = target (from `input`, ⚠️ VERIFY field name)
- `text`, `timestamp`
- `status`: PENDING (tool_use seen) → SENT / FAILED (tool_result) → RECEIVED (seen in receiver's file, ⚠️ VERIFY) → optionally HELD / DROPPED
- `kind`: peer message | idle notice | script post | own-hook post

**Filtering:** only show sessions in the same git repo as the manager (match on repo, not path prefix — worktrees can live outside the folder).

---

## 8. Display mapping (summary)

| Data | Visual |
| :- | :- |
| Session | Node; label from §7; color from `agentColor` if present |
| Permission group | Node badge; mismatch between sender/receiver → amber "may be held" edge |
| WORKING / IDLE / ERROR | Pulse / calm / warning icon |
| SendMessage | Animated edge sender → receiver |
| Send failed (`Not sent`, `is_error`) | Red dashed edge + reason tooltip |
| Message received | Arrival animation at receiver; click → full text panel |
| Tokens | Edge thickness or per-node cost; "% spent on coordination" metric |
| Queue | Counter badge on node |
| Hook / API errors | Warning icon with details |

---

## 9. Cross-session messaging facts (context)

- Sessions exchange plain text via `ListAgents` (discover) and `SendMessage` (send). Requires Claude Code v2.1.224+.
- Each local session has an inbox socket (`/status` → Peer address; `$CLAUDE_CODE_MESSAGING_SOCKET`). Messages are delivered to Claude and NOT stored in the socket — the transcript is the record.
- Receiver reads messages between tool calls if busy, or starts a new turn if idle.
- Each message is Delivered, Held, or Refused per the receiver's `crossSessionInbound` setting (`accept` | `hold` | `refuse`) or the permission-group default.
- Held messages expire after `dialogExpiry` (default 5 min); max 100 held; max 50 queued accepted messages per receiver; identical rapid repeats are dropped.
- `notify_when_idle` (v2.1.236+) = one-shot "B went idle" notice. It is an event, not a status — it can be stale by the time it's read.

---

## 10. Verification checklist (do before building parsers)

Run against real transcripts after sending a cross-session message:

```bash
F=~/.claude/projects/*/*.jsonl
# All entry types and counts
jq -r '.type' $F | sort | uniq -c | sort -rn
# System subtypes / attachment types
jq -r 'select(.type=="system") | .subtype' $F | sort | uniq -c
jq -r 'select(.type=="attachment") | .attachment.type' $F | sort | uniq -c
# Origin kinds (find how peer messages are marked)
jq -c 'select(.origin or .attachment.origin) | (.origin // .attachment.origin)' $F | sort | uniq -c
# Queue operation values
jq -r 'select(.type=="queue-operation") | .operation' $F | sort | uniq -c
# SendMessage input shape
jq -c 'select(.type=="assistant") | .message.content[] | select(.type=="tool_use" and .name=="SendMessage") | .input' $F
```

Update §4.7, §4.8, §4.10, §4.12, and §7 with the confirmed field names.
