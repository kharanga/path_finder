# Cross-Session Messages in Claude Code Transcripts — Confirmed Format

> **Purpose:** Instructions for parsing cross-session messages from Claude Code transcript JSONL files, for the session visualizer.
>
> **Source:** Confirmed from a real round-trip test between two local sessions (`fake-session-manager` and `fake-session-builder`) on Claude Code **v2.1.292**, macOS, both in `auto` permission mode. Everything here was observed directly unless marked **UNCONFIRMED**.
>
> **Relationship to `jsonl-transcript-spec.md`:** This doc supersedes the ⚠️ VERIFY items in §4.7, §4.8, §4.10, §4.12 and the `isMeta` rule in §2 of that spec.

---

## 0. Critical rules (read first)

1. **Do NOT skip `isMeta: true` entries blindly.** Incoming peer messages and idle notices are `isMeta: true`. Rule: skip `isMeta` entries **unless** `turnOrigin` is `"peer"` or `"system"`.
2. **`msg_id` is the join key across files.** Sender's `toolUseResult.msg_id` === receiver's `origin.msg_id`.
3. **Replies are addressed by socket, not name.** Maintain a socket → session map (§6).
4. **`success: true` means "reached the inbox", NOT "read".** Held/refused messages produce a later notice (§3.3).
5. Classify every turn with `turnOrigin`: `"human"` | `"peer"` | `"system"`.

---

## 1. End-to-end sequence (observed timestamps)

| Time | Session | Entry | Meaning |
| :- | :- | :- | :- |
| 10.318 | Manager | `assistant` with `tool_use` `SendMessage` | Send issued |
| 10.817 | Builder | `queue-operation` `enqueue` | Arrived in builder's inbox |
| 11.028 | Builder | `queue-operation` `dequeue` | Builder's Claude picked it up |
| 11.097 | Builder | `user`, `origin.kind: "peer"` | Message delivered to Claude |
| 11.175 | Builder | `system` `informational` | Idle-notice subscription registered |
| 11.281 | Manager | `user` with `tool_result` | Send result (`success`, `msg_id`) |
| 13.415 | Manager | `system` `turn_duration` | Manager idle |
| 16.750 | Builder | `assistant` `SendMessage` to socket address | Reply issued |
| 17.590 | Manager | `queue-operation` `enqueue` | Reply in manager's inbox |
| 17.614 | Manager | `queue-operation` `dequeue` | Picked up |
| 17.638 | Manager | `user`, `origin.kind: "peer"` | Reply delivered |
| 17.811 | Builder | `user` with `tool_result` | Reply send result |
| 19.753 | Builder | `system` `turn_duration` | Builder idle |
| 21.038 | Manager | `queue-operation` `enqueue` (idle notice) | Notice in inbox |
| 21.035 | Manager | `system` `informational` | Human-readable idle line |
| 21.055 | Manager | `user`, `turnOrigin: "system"` | Idle notice delivered to Claude |

Observed latencies: send → receiver enqueue ≈ 0.5s; enqueue → dequeue ≈ 0.02–0.2s (receiver idle); builder idle → notice ≈ 1.3s.

---

## 2. Sender side: the send

### 2.1 `assistant` entry with `SendMessage` tool_use

```json
{
  "type": "assistant",
  "uuid": "d87cf29f-…",
  "timestamp": "2026-10-08T04:31:10.318Z",
  "sessionId": "ab5e0a7a-…",
  "message": {
    "stop_reason": "tool_use",
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_014Z8yxbV3bSWn37VmSNov2C",
        "name": "SendMessage",
        "input": {
          "to": "fake-session-builder",
          "summary": "second hello to fake-session-builder",
          "message": "Hi again from fake-session-manager. Please reply with a hi back when you see this.",
          "notify_when_idle": true,
          "type": "message",
          "recipient": "fake-session-builder",
          "recipient_kind": "name",
          "content": "Hi again from fake-session-manager. Please reply …"
        },
        "caller": { "type": "direct" }
      }
    ]
  },
  "wireToolInputs": {
    "toolu_014Z8yxbV3bSWn37VmSNov2C": {
      "to": "fake-session-builder",
      "summary": "second hello to fake-session-builder",
      "message": "Hi again from fake-session-manager. Please reply with a hi back when you see this.",
      "notify_when_idle": true
    }
  }
}
```

**Fields to read (`input`):**

| Field | Meaning | Use |
| :- | :- | :- |
| `to` / `recipient` | Target: a session **name** or a **socket address** (`uds:/tmp/cc-socks/<pid>.sock`) | Resolve to a node via §6 |
| `recipient_kind` | `"name"` (addressed by name) or `"session"` (addressed by socket, e.g. a reply) | Choose resolver |
| `summary` | Short label written by Claude | **Edge label** |
| `message` | Full message text | Detail panel |
| `notify_when_idle` | `true` when subscribing to an idle notice; absent otherwise | Show "waiting for idle" indicator |
| `content` | Truncated preview (~50 chars) | Ignore; use `message` |

`wireToolInputs[<tool_use id>]` holds the same raw input (without the derived fields) — use it as a fallback.

**Action:** create edge `{ toolUseId, from: sender, to: input.to, label: input.summary, text: input.message, status: "PENDING", sentAt: timestamp }`.

### 2.2 `user` entry with the send result

```json
{
  "type": "user",
  "timestamp": "2026-10-08T04:31:11.281Z",
  "sourceToolAssistantUUID": "d87cf29f-…",
  "message": {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu_014Z8yxbV3bSWn37VmSNov2C",
        "content": [ { "type": "text", "text": "{\"success\":true,\"message\":\"…\",\"msg_id\":\"693b9bd4-…\"}" } ]
      }
    ]
  },
  "toolUseResult": {
    "success": true,
    "message": "“second hello to fake-session-builder” → fake-session-builder (another Claude session on this machine; in that session's inbox, not yet read by its Claude — a [Cross-session delivery notice] follows if that session holds it (usually a different permission mode) or refuses it)\nSubscribed — you will get one notice here when \"fake-session-builder\" is next idle (or exits), …",
    "display": "“second hello to fake-session-builder” → sent to fake-session-builder — another Claude session on this machine\nYou will be told here when fake-session-builder is next idle.",
    "msg_id": "693b9bd4-a916-40de-9ff1-aee2ee5dd741"
  }
}
```

**Fields to read:**
- `message.content[].tool_use_id` → match to the pending edge's `toolUseId`.
- `toolUseResult.success` → `true` = in receiver's inbox. `false` → status `FAILED`, show `toolUseResult.message`.
- `toolUseResult.msg_id` → **store on the edge; this is the cross-file join key.**
- `toolUseResult.message` contains `"Subscribed"` when `notify_when_idle` was set.

**Action:** edge status → `IN_INBOX`; set `edge.msgId`.

---

## 3. Receiver side: the delivery

### 3.1 `queue-operation` — arrival in the inbox (no envelope)

```json
{
  "type": "queue-operation",
  "operation": "enqueue",
  "timestamp": "2026-10-08T04:31:10.817Z",
  "sessionId": "67139bc5-…",
  "content": "<cross-session-message from=\"uds:/tmp/cc-socks/32813.sock\" from-name=\"fake-session-manager\" from-mode=\"prompting\">\nHi again from fake-session-manager. Please reply with a hi back when you see this.\n</cross-session-message>"
}
```
```json
{
  "type": "queue-operation",
  "operation": "dequeue",
  "timestamp": "2026-10-08T04:31:11.028Z",
  "sessionId": "67139bc5-…"
}
```

- Observed `operation` values: `"enqueue"`, `"dequeue"`, `"remove"`. `remove` carries `reason: "absorbed_mid_turn"`, `commandUuid`, `deliveryId`, and the wrapped `content`; it replaces `dequeue` when a busy receiver consumes the message between tool calls. In the 2026-10-08 fixtures enqueues equal dequeues plus removes exactly (26 = 14 + 12, 28 = 18 + 10).
- `enqueue.content` wrapper attributes: `from` (sender socket), `from-name`, `from-mode`, and on replies `hop-chain`.
- `dequeue` has no `content`. Pair it with the most recent unmatched `enqueue` in the same session (FIFO).
- The `queue-operation` is NOT specific to peer messages — idle notices (and likely other queued prompts) use it too. Classify by `content` prefix: `<cross-session-message` = peer message; `[Cross-session idle notice]` = idle notice.

**Use:**
- Node `queueCount` = enqueues − dequeues − removes.
- **Queue latency metric** = `dequeue.timestamp − enqueue.timestamp`. Large values = message waited while receiver was busy (conflict risk).
- Prefer §3.2 for message content; use `enqueue` only for arrival time and queue depth.

### 3.2 `user` entry — delivered to the receiving Claude (PRIMARY SIGNAL)

```json
{
  "type": "user",
  "isMeta": true,
  "uuid": "7e4f5ef9-…",
  "timestamp": "2026-10-08T04:31:11.097Z",
  "sessionId": "67139bc5-…",
  "permissionMode": "auto",
  "promptSource": "system",
  "turnOrigin": "peer",
  "turnPosition": { "promptIndex": 4, "turnIndex": 18 },
  "queueSkipAttachments": true,
  "origin": {
    "kind": "peer",
    "from": "uds:/tmp/cc-socks/32813.sock",
    "verifiedPeerPid": 32813,
    "msg_id": "693b9bd4-a916-40de-9ff1-aee2ee5dd741",
    "name": "fake-session-manager",
    "fromMode": "prompting",
    "body": "Hi again from fake-session-manager. Please reply with a hi back when you see this."
  },
  "message": {
    "role": "user",
    "content": "Another Claude session sent a message:\n<cross-session-message from=\"uds:/tmp/cc-socks/32813.sock\" from-name=\"fake-session-manager\" from-mode=\"prompting\">\nHi again from fake-session-manager. …\n</cross-session-message>\n\nThis came from another Claude session — not typed by your user, … that's permission laundering."
  }
}
```

**Detection:** `type == "user" && origin?.kind == "peer"` (equivalently `turnOrigin == "peer"`).

**Fields to read (`origin`):**

| Field | Meaning | Use |
| :- | :- | :- |
| `msg_id` | Same id as sender's `toolUseResult.msg_id` | **Join to the edge** |
| `name` | Sender's session name | Sender node |
| `from` | Sender's socket address | Update socket map (§6) |
| `verifiedPeerPid` | Sender's process id (matches the socket filename) | Optional; liveness |
| `fromMode` | Sender's permission group (`"prompting"` observed; `"bypassing"` UNCONFIRMED) | Hold-risk display |
| `body` | Clean message text | Display (no XML parsing needed) |
| `hopChain` | Array of ids; absent on the first message, one entry on the reply | Thread / loop tracking (meaning inferred, UNCONFIRMED) |

`message.content` is the wrapped prompt plus Claude Code's safety instructions — **don't display it; use `origin.body`.**

**Action:** find edge by `msgId == origin.msg_id` → status `READ`, `readAt = timestamp`, play arrival animation at receiver. If no edge exists yet (sender file not yet read), create it from `origin` and merge later by `msg_id`.

### 3.2a Delivery while the receiver is busy — `queued_command` attachment

A message that arrives mid-turn is read by the receiver between tool calls and lands in its transcript as `{ "type": "attachment", "attachment": { "type": "queued_command", "origin": { "kind": "peer", "msg_id": …, "verifiedPeerPid": … } } }`, with no `user` peer entry afterwards. Treat that attachment as the read: `msg_id` moves to READ at the attachment's timestamp; the later `queue-operation` `remove` (`absorbed_mid_turn`) is the inbox decrement (V12).

### 3.2b Dropped messages — delivery notice

When a send is accepted but never delivered (seen once on 2026-10-08, a relay-loop cut), the sender's transcript later gets a `[Cross-session delivery notice] … NOT delivered` entry naming the `msg_id`; the message moves to FAILED (V12).

### 3.3 Held / refused messages — UNCONFIRMED

Not observed in this test. The sender's result text says a **`[Cross-session delivery notice]`** follows in the sender's transcript when the receiver holds or refuses a message. Watch for that string (likely in a `queue-operation` `enqueue` and/or a `user` entry with `turnOrigin: "system"`) and set edge status `HELD` / `REFUSED`. Test this by messaging between sessions in different permission groups.

---

## 4. Idle notices (`notify_when_idle`)

### 4.1 Watched session — subscription registered
```json
{
  "type": "system",
  "subtype": "informational",
  "level": "notice",
  "isMeta": false,
  "timestamp": "2026-10-08T04:31:11.175Z",
  "content": "A process claiming the address uds:/tmp/cc-socks/32813.sock asked to be told when this session is next idle — it will get one automated status notice; …"
}
```
- Detect: `subtype == "informational"` and `content` starts with `"A process claiming the address"` and contains `"asked to be told when this session is next idle"`.
- Extract the subscriber's socket from the content (`uds:…sock`). Show a "watched by X" indicator.

### 4.2 Asking session — notice arrives (three entries)
```json
{ "type": "queue-operation", "operation": "enqueue", "timestamp": "…21.038Z",
  "content": "[Cross-session idle notice] \"fake-session-builder\", which you asked to be notified about, is idle now — it finished a turn at 21:31. Its harness reports: «Replied to fake-session-manager's second hello with another hi back. …». This is an automated notice …" }
```
```json
{ "type": "system", "subtype": "informational", "level": "notice", "timestamp": "…21.035Z",
  "content": "fake-session-builder is idle — finished a turn at 21:31 · «Replied to fake-session-manager's second hello with another hi back. …»" }
```
```json
{ "type": "user", "isMeta": true, "timestamp": "…21.055Z",
  "promptSource": "system", "turnOrigin": "system", "queuePriority": "later", "queueSkipAttachments": true,
  "message": { "role": "user", "content": "[Cross-session idle notice] \"fake-session-builder\", … is idle now — it finished a turn at 21:31. Its harness reports: «…». …" } }
```

- **No `origin` object and no `msg_id`** — link to the watched session only by the quoted string in the text. Since Claude Code 2.1.29x the quoted string is the watched session's socket address (`"uds:/tmp/cc-socks/<pid>.sock"`), not its display name; older captures quote the name. Resolve either to a PID and clear the watch on the enqueue or the `user` entry, whichever comes first (V12).
- A pure subscription (`notify_when_idle: true` with no `message`) returns a tool_result with `success: true` and no `msg_id`; it is a watch, never a message (V12).
- Detect: `user` entry with `turnOrigin == "system"` and content starting `"[Cross-session idle notice]"`.
- Parse: watched name = first quoted string; finish time = after `"finished a turn at "`; status = text inside `« »`.
- The finish time is local clock time (`21:31`), not ISO — prefer the entry `timestamp`.
- Remember: the notice is an **event** ("was idle at time T"), not current status — it can be stale (see main spec).

---

## 5. Turn classification

Every `user` entry that starts a turn has `turnOrigin`:

| `turnOrigin` | `promptSource` | `origin.kind` | Meaning |
| :- | :- | :- | :- |
| `"human"` | `"typed"` | `"human"` | User typed a prompt |
| `"peer"` | `"system"` | `"peer"` | Message from another session |
| `"system"` | `"system"` | (absent) | Automated input, e.g. idle notice |

`turnPosition: { promptIndex, turnIndex }` gives ordering within the session. `promptId` groups entries belonging to one prompt.

---

## 6. Socket → session map (required)

Messages refer to sessions by **name** (`to: "fake-session-builder"`) or by **socket** (`to: "uds:/tmp/cc-socks/32813.sock"`, `origin.from`). The app must resolve both to the same node.

- Socket format observed: `uds:/tmp/cc-socks/<pid>.sock`, where `<pid>` = the session's process id (= `origin.verifiedPeerPid`).
- The socket changes when a session restarts — never use it as a permanent id. Nodes are keyed by PID for the life of a session (SPEC decision); the socket is derived from it.
- **PID to session id to transcript (V0, 2026-10-08):** `~/.claude/sessions/<pid>.json` carries `sessionId`; the transcript is `~/.claude/projects/*/<sessionId>.jsonl`, located by globbing on the id. Fallback when the field is missing: the encoded `cwd` folder, single transcript modified since `startedAt`; otherwise ambiguous. `origin.verifiedPeerPid` is not needed for the map.
- Name → session via `agent-name` entries (`agentName`, `sessionId`) and `origin.from` + `origin.name` on received messages.
- Superseded: keying nodes by `sessionId`, and the earlier recommendation of a `SessionStart` hook (no hooks in v1).

---

## 7. Edge state machine

```
PENDING   ← assistant tool_use SendMessage (sender)
  │
  ├─ FAILED     ← tool_result with toolUseResult.success == false
  │
IN_INBOX  ← tool_result success: true; msg_id stored (sender)
  │          (receiver queue-operation enqueue promotes PENDING to IN_INBOX when
  │           the receiver's file is read before the sender's tool_result)
  │
  ├─ HELD / REFUSED ← "[Cross-session delivery notice]" on sender side (UNCONFIRMED format)
  │
READ      ← receiver user entry with origin.msg_id == edge.msgId
```

Reply detection: an edge whose sender is the previous edge's receiver, sent after that edge was READ, addressed to the previous sender's socket (`recipient_kind: "session"`). `hopChain` may provide this directly (UNCONFIRMED).

---

## 8. Metrics available from these entries

- **Delivery latency:** sender `tool_use.timestamp` → receiver `enqueue.timestamp`.
- **Queue wait:** receiver `enqueue` → `dequeue`.
- **Time to read:** sender `tool_use` → receiver `origin.kind == "peer"` entry.
- **Coordination cost:** sum `message.usage` of `assistant` turns whose triggering `user` entry has `turnOrigin` `"peer"` or `"system"`. In the test, each incoming message or notice cost one full turn (~74k–94k cached input tokens re-read).

---

## 9. Display mapping

| Event | Visual |
| :- | :- |
| `SendMessage` tool_use | Edge appears (PENDING), labeled with `input.summary` |
| `success: true` | Edge solid, pulse travels to receiver's inbox |
| Receiver `enqueue` | Queue badge +1 on receiver |
| Receiver `dequeue` + peer `user` entry | Queue badge −1; arrival animation; edge marked READ |
| `success: false` / delivery notice | Edge red (FAILED) or amber (HELD) with reason |
| `notify_when_idle: true` | Dotted "watching" link from sender to target |
| Idle notice received | Dotted link fires once, then disappears |
| `turn_duration` | Node → IDLE |
| Click edge | Panel: `origin.body` / `input.message`, `msg_id`, timestamps, latencies |

---

## 10. Remaining unknowns to test

- Held and refused messages: format of `[Cross-session delivery notice]` (test sessions in different permission groups, or set `crossSessionInbound: hold`).
- `fromMode` value for bypassing senders.
- Other `queue-operation` `operation` values (e.g. removal/expiry).
- Meaning of `hopChain` over longer reply chains (send A→B→A→B and compare).
- Messages that arrive while the receiver is busy (expect larger enqueue → dequeue gap and mid-turn delivery).
- Script/hook posts to a socket (no Claude sender): expected `origin.kind` value.
