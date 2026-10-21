# Plan: Session Message Visualization (v1)

Status: draft 2026-10-08. For the user to review, then paste into `SPEC.md` as the next task block.
Companion docs: `docs/jsonl-transcript-spec.md`, `docs/cross-session-message-format.md`.

## 1. Goal

Extend the existing capsule page (`discover.py ui`, D2) so it shows **messages traveling between sessions, live**, read from each session's transcript JSONL. v1 targets the two fake sessions (manager and builder); the design must generalize to N capsules without rework.

## 2. Scope

**In v1**
- Capsules for every discovered session (already in D2), extended with: status pill (Working / Idle), inbox badge (messages waiting), last message line, "watching" indicator.
- Connectors between capsules for each message, with three stages: Pending → In inbox → Read.
- Idle notices shown as a muted one-shot connector.
- Live updates while sessions run. Page refresh must not lose state.

**Out of v1**
- Routing, holding, or blocking messages (the manager/broker). Visualize only.
- Held and refused messages (format not yet observed; see §8).
- Token cost and latency metrics (data is available; add in v2).
- Replay of past runs (v2; keep the event log so it is possible).
- Hooks and socket posting (parked; see the parked doc).

## 3. Data sources (all read-only)

| Source | Path | Gives |
| :- | :- | :- |
| Session registry | `~/.claude/sessions/<pid>.json` | PID, display name, start path (undocumented; already used by `discover.py`) |
| Identity | `discovery/identity/<pid>.json` | role, label (entered by each session's human) |
| Transcripts | `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` | every send, receive, result, idle notice, turn end |

**Gap to close first (task V0):** the registry is keyed by PID, transcripts are keyed by session UUID, and no entry on either side carries both. Options to test, in order:
1. The registry file may contain the session id. Open one and check.
2. Match on `cwd`: a transcript's entries carry `cwd`; the registry carries the start path. Ambiguous when two sessions share a folder (the fake sessions do).
3. Received messages carry `origin.verifiedPeerPid`, so once any message flows, each transcript can be tied to the PID of its *sender*; combined with option 2 this resolves most cases.
Record the chosen method in `cross-session-message-format.md` §6.

## 4. Architecture

Keep the current stack: Python for the backend (same file family as `discover.py`), a static `index.html` for the page, no framework.

```
~/.claude/sessions/*.json ─┐
discovery/identity/*.json ─┼─► watcher.py ──► state (in memory) ──► GET /events (SSE) ──► index.html
~/.claude/projects/**/*.jsonl ┘        └──► discovery/events.jsonl (append-only log for v2 replay)
```

- **watcher.py**: polls or inotify-watches the three sources. Tails each transcript by byte offset, parses complete lines only, ignores unknown types (rules in `jsonl-transcript-spec.md` §2, with the `isMeta` exception from `cross-session-message-format.md` §0).
- **state**: `sessions{}` keyed by PID and `messages{}` keyed by `msg_id`, plus a socket→PID map. Each session also carries `activity` (latest tool description or last assistant text), `activity_at`, `idle_since`, and `last_assistant_text` (V8), which the compact window's activity rows read. `/state` also carries `tasks`, `task_counts`, and `spec_path`, parsed from the SPEC.md Tasks section on every mtime change, with a `tasks` change on `/events` (V9). Each task carries `area` (Discovery, Visualization, Packaging, or the series letter) for the panel's folders (V10). Each session also carries `waiting_on` (PIDs it holds an open idle-notice subscription for, or has a PENDING or IN_INBOX message to), recomputed after every entry (V11). A watch clears on the idle notice's enqueue or `user` entry, whichever comes first, matched by the quoted socket address or name resolved to a PID; a `queued_command` peer attachment counts as the read; a delivery notice marks the message FAILED (V12). Convention: the manager marks a task `[~]` on assignment and `[x]` on PASS, so SPEC.md is the task panel's source of truth.
- **server**: `watcher.py serve` owns port 4780 (`discover.py ui` is retired, D4). `GET /state` is the full snapshot and carries `sources` (latest entry per PID); `GET /events` streams one JSON line per change, each with `source` and `source_pid`, which the page caption reads.
- **index.html**: renders capsules from `/state`, applies `/events` deltas. Connectors drawn as SVG lines over the capsule layout.

## 5. State model

**Session (capsule)**
```
pid, session_id, name, role, label, cwd, socket ("uds:/tmp/cc-socks/<pid>.sock")
status: WORKING | IDLE          ← assistant/turn start → WORKING; system turn_duration → IDLE
inbox: int                      ← queue-operation enqueue +1, dequeue −1, remove −1
last_text: str                  ← origin.body of last received, or input.summary of last sent
watching: [pid]                 ← SendMessage with notify_when_idle: true, cleared when the notice is read
```

**Message (connector)**
```
msg_id, from_pid, to (name or socket → resolved pid), summary, body
stage: PENDING | IN_INBOX | READ | FAILED
sent_at, accepted_at, enqueued_at, read_at
kind: message | idle_notice
```

Stage transitions (sender file unless noted):
- `assistant` tool_use `SendMessage` → create PENDING (`id` = tool_use id)
- `user` tool_result with matching `tool_use_id` → `success` true: IN_INBOX, store `toolUseResult.msg_id`; false: FAILED
- receiver `queue-operation` enqueue → `enqueued_at`, receiver inbox +1, and PENDING → IN_INBOX if the sender's tool_result has not been read yet
- receiver `queue-operation` dequeue or remove → inbox −1 (the peer `user` entry does not decrement again)
- receiver `user` with `origin.kind == "peer"` and `origin.msg_id` == msg_id → READ
- idle notice: receiver `user` with `turnOrigin == "system"` and content starting `[Cross-session idle notice]` → one-shot connector from the named session, then clear `watching`

## 6. UI spec (from the flow frames)

| Element | Shows | Driven by |
| :- | :- | :- |
| Capsule title | `label` (role), fallback display name | identity file, registry |
| Status pill | Working / Idle | turn start, `turn_duration` |
| Inbox badge | count when > 0 | enqueue/dequeue |
| Last line | latest `origin.body` or `input.summary`, truncated | peer entry, tool_use |
| Watching line | eye icon + target label | `notify_when_idle` |
| Connector label | `input.summary` | tool_use |
| Connector stage | Pending (muted) → In inbox (check) → Read (double check); Failed (red) | tool_result, enqueue, peer entry |
| Idle notice | muted dashed connector, disappears after read | idle notice entry |
| Legend | the four states above | static |

Layout: capsules grouped by folder as in D2; connectors as straight lines between capsule centers, label at midpoint. With many messages, keep only the latest connector per (from, to) pair visible and list the rest in a side panel on click.

Look (V4+V5 rework, 2026-10-08): reference frames in `docs/ui-frames.png`. Dark cards with a coloured dot and bold label, status pill, orange inbox pill, eye watching line, quoted last line; the connector sits in the gap between cards as summary, bold arrow, stage; a monospace caption under each row names the latest transcript entry. No legend, no SVG wires; thin arcs for non-neighbour pairs. Where the mock frames and the transcript timing differ, the page follows the data.

Compact web window (V7, 2026-10-20): a second page at `/web`, about 380 px wide, for a small browser window. Top to bottom: a ring of session nodes (the frame-style card; the pod for two sessions; compact dot-and-name nodes past eight), the caption, a strip of one chip per session (ring while working, orange count while mail waits, click highlights that session's arrows), and toasts newest first with the message's first line. Arrows exist only while a message is in flight: Pending grey, In inbox green, Failed red until resolved, plus, since V14, a read arrow that stays 30 s (full for 3 s, then muted with its label) and leaves early when a reply on the reversed pair appears; task cards wrap a truncated title in full on hover (V17; click pins the full SPEC text). Since V15 nodes can be dragged (mouse or touch) and pinned where dropped; pins live in localStorage under `viz-web-pin:<label|role|pid>` so a reload or a later session with the same role lands in the same spot, and a Reset layout button in the caption bar clears them. Since V16 a session waiting on another (`waiting_on`) draws a dashed yellow tether (V18, grey in V16) to it under the arrows, hollow circle at the target, eye glyph at the midpoint with "waiting" on hover, beside any message arrow on the same pair, for as long as the wait lasts. Idle notices are never arrows; they pulse the eye glyph on the watching node and add a muted toast. One arrow per (from, to) pair with a +N count. Since V13 every live session under the root is a node from the first poll until the watcher drops it (the ten-minute ring rule is gone), the activity line is the tool call's description alone with no tool-name prefix, and once the V11 vertical growth reaches its cap any cards still too close are relaxed apart vertically. Mocks: `handoff/viz/v7-animation.html`, `handoff/viz/v7-styles.html`. The task panel (V9) groups tasks into per-series folders (V10); a closed folder is remembered in localStorage under `viz-web-folder-closed:<area>`. Since V11 an idle node and its activity row are blank unless the session is waiting, then both read "waiting on <label>"; a working node shows its activity line in full, wrapping without truncation, and the ring grows so cards never overlap.

## 7. Tasks

| ID | Task | Acceptance |
| :- | :- | :- |
| V0 | Map PID ↔ session_id ↔ transcript path (§3) | For both fake sessions, `watcher.py map` prints pid, session_id, transcript path |
| V1 | Transcript tailer | Appending lines to a fixture file produces parsed events; partial lines are buffered; unknown types are skipped without error |
| V2 | Message state machine | Feeding the captured manager + builder fixtures produces 2 messages READ, 1 idle notice, with timestamps matching the logs |
| V3 | `/state` and `/events` endpoints | `curl /state` returns both sessions; `/events` streams a change within 1s of a line being appended |
| V4 | Capsule extensions (pill, badge, last line, watching) | Matches frames 1–4 of the UI flow on a live round trip |
| V5 | Connectors with stages | Matches frames 2–9 on a live round trip |
| V6 | Event log + fixtures | `discovery/events.jsonl` written; fixtures committed under `tests/fixtures/` (sanitized captures) |

Suggested order: V0 → V1 → V2 (all testable offline with fixtures) → V3 → V4 → V5 → V6.

## 8. Test plan

- Fixtures: the manager and builder captures from 2026-10-08 (remove home-directory paths before committing).
- Unit: tailer (partial lines, rotation, unknown types), state machine (each transition, out-of-order arrival: receiver file read before sender file).
- Integration: temp `~/.claude`-like tree with fixture transcripts appended line by line; assert `/events` output.
- Live check: run the two fake sessions, send one message with `notify_when_idle`, compare the page against the nine frames.
- Not covered yet: held/refused messages. When ready, test by setting one session to `crossSessionInbound: hold`, capture the sender's `[Cross-session delivery notice]`, then add FAILED/HELD handling.

## 9. Decisions (closed 2026-10-08)

1. Discovery: self-registration, no messages (SPEC task D3). The watcher reads the same registry and `identity/` files.
2. Hooks: the leftover `dashboard-hook.js` plugin is removed by the user. No hooks in v1.
3. Watcher: poll every 250 ms.
4. Ownership: `viz-builder` owns all of `viz/` (option A). Role file at `.claude/roles/viz-builder.md`.
5. `discover.py ui` retired; the watcher owns port 4780 (D4, 2026-10-20).
6. Compact web window (V7, 2026-10-20): a second page at `/web` with a ring of session nodes, arrows only for messages in flight, a strip, and toasts. Mocks in `handoff/viz/v7-animation.html` and `handoff/viz/v7-styles.html`.