# Overview

Owner: manager. Builders request changes to this file under Requests in their `ready.md`.

## Architecture

```
Claude Code sessions (any folder on this machine)
        |  user-level hooks, one JSON line per event
        v
~/.claude/dashboard/events.jsonl
        |  tail + replay on startup
        v
webhook/  server: state, PID liveness, SSE
        |  GET /  and  GET /events
        v
frontend/ index.html: Orbit ring visualization
```

## Areas

- **webhook** (webhook-builder): hook scripts that write events, the fake event generator, and the server. Everything that produces or serves data.
- **frontend** (frontend-builder): the single HTML page. Everything that renders data.
- **tests** (validator): unit and integration tests, docs example checks.

## Event schema

Written by hooks, read by the server, forwarded to the page unchanged.

Session state:

```json
{"ts":"2026-10-05T21:40:00Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"started","role":null}
```

| Field | Type | Meaning |
|---|---|---|
| `ts` | ISO 8601 string | when the hook ran |
| `type` | `"session"` | discriminator |
| `session` | string or null | display name, null until known |
| `folder` | string | basename of the session's start folder |
| `pid` | integer | process id, the stable key |
| `state` | `started`, `busy`, `waiting`, `idle`, `ended` | `waiting` is a permission prompt |
| `role` | string or null | declared role, if any |

Message:

```json
{"ts":"2026-10-05T21:40:05Z","type":"message","from":"listings-bc","to":"tag-analyzer-63","text":"L16 is ready, look at it","notify_on_idle":true}
```

| Field | Type | Meaning |
|---|---|---|
| `ts` | ISO 8601 string | when the sender's hook ran |
| `type` | `"message"` | discriminator |
| `from` | string or null | sender display name, null when the hook could not resolve its own session name |
| `to` | string | recipient display name |
| `text` | string | message text |
| `notify_on_idle` | boolean | sender asked to be told when the recipient goes idle |

Confirmed in W1: `SendMessage` exposes `to`, `message`, and `notify_when_idle`, mapped to `to`, `text`, and `notify_on_idle`.

## Server to page contract

- `GET /` serves `frontend/index.html`. Every other path that is not `/events` is served as a static file from `frontend/` with the correct content type for `.html`, `.js`, `.css`, `.json`, and `.svg`. Paths that escape `frontend/` return 404.
- `GET /events` is a Server-Sent Events stream.
  - First event: `event: snapshot`, data `{"sessions":[...],"messages":[...]}` where each session object is the latest `session` event for that PID and `messages` holds recent message events, oldest first.
  - Then `event: session` and `event: message` with the schema above, as they arrive.
  - `event: liveness` with a `session` object in state `ended` when the PID check finds a dead process.

## Data flow for one message

1. Session A calls `SendMessage` to session B.
2. A's `PostToolUse` hook appends a `message` event.
3. The server reads the new line, updates state, emits `event: message`.
4. The page draws a particle from A's position to B's position. If `notify_on_idle` is true, it also draws a thread.
5. B's next turn fires `UserPromptSubmit` (busy), then `Stop` (idle). The page sees B go idle and snaps the thread back to A.

## Liveness

Sessions can die without `SessionEnd`. The server checks each known PID on an interval. A missing process produces a synthetic `ended` event. The socket directory `/tmp/cc-socks/` may be consulted as a secondary signal but is an undocumented Claude Code internal.
