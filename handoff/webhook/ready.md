# Ready: W3 real hooks

## Done

- `webhook/hooks/dashboard-hook.js`: the real hook. Maps `SessionStart` to `started`, `UserPromptSubmit` to `busy`, `Notification` with `notification_type` `permission_prompt` to `waiting`, `Stop` to `idle`, `SessionEnd` to `ended`, and `PostToolUse` for `SendMessage` to a `message` event with `to`, `text` (from `message`), `notify_on_idle` (from `notify_when_idle`, false when absent). Everything else is ignored. Sender name and PID come from `~/.claude/sessions/<pid>.json` matched on `session_id`, re-read on every event, with the `ps` walk to the `claude` parent as fallback (then `session` is `null`). Creates `~/.claude/dashboard/` if missing. Output path overridable with `CC_DASHBOARD_EVENTS` for tests. Exit 0 always, zero bytes on stdout and stderr, about 25 ms per run. Entry point guarded with `realpathSync`.
- `webhook/schema.js`: `SESSION_STATES` now includes `waiting`. `validateEvent` and `parseEventLine` are the validators the server and generator will use.
- `docs/webhook/hooks.md`: hook to event table and every exported function of `dashboard-hook.js`.
- `docs/webhook/schema.md`: new, every export of `schema.js`.
- Unchanged from W1: `capture-raw.js` stays until the manager swaps the snippet.

## How to test

Unit level, from the repo root, inside any Claude Code session so the registry lookup finds a real session:

```
export CC_DASHBOARD_EVENTS=/tmp/w3-test/events.jsonl; rm -rf /tmp/w3-test
SID=$(python3 -c "import json,glob,os; print([json.load(open(f))['sessionId'] for f in glob.glob(os.path.expanduser('~/.claude/sessions/*.json')) if json.load(open(f))['pid']==$(ps -o ppid= -p $$ | tr -d ' ')][0])" 2>/dev/null || echo unknown)
H=webhook/hooks/dashboard-hook.js
for payload in \
  "{\"session_id\":\"$SID\",\"hook_event_name\":\"SessionStart\",\"cwd\":\"$PWD\",\"source\":\"startup\"}" \
  "{\"session_id\":\"$SID\",\"hook_event_name\":\"UserPromptSubmit\",\"cwd\":\"$PWD\",\"prompt\":\"x\"}" \
  "{\"session_id\":\"$SID\",\"hook_event_name\":\"Notification\",\"cwd\":\"$PWD\",\"message\":\"x\",\"notification_type\":\"permission_prompt\"}" \
  "{\"session_id\":\"$SID\",\"hook_event_name\":\"Notification\",\"cwd\":\"$PWD\",\"message\":\"x\",\"notification_type\":\"idle_prompt\"}" \
  "{\"session_id\":\"$SID\",\"hook_event_name\":\"PostToolUse\",\"cwd\":\"$PWD\",\"tool_name\":\"SendMessage\",\"tool_input\":{\"to\":\"listings-bc\",\"message\":\"L16 is ready\",\"notify_when_idle\":true},\"tool_response\":{}}" \
  "{\"session_id\":\"$SID\",\"hook_event_name\":\"PostToolUse\",\"cwd\":\"$PWD\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"ls\"}}" \
  "{\"session_id\":\"$SID\",\"hook_event_name\":\"Stop\",\"cwd\":\"$PWD\",\"stop_hook_active\":false}" \
  "{\"session_id\":\"unknown-id\",\"hook_event_name\":\"Stop\",\"cwd\":\"/tmp/other\"}" \
  "{\"session_id\":\"$SID\",\"hook_event_name\":\"SessionEnd\",\"cwd\":\"$PWD\",\"reason\":\"exit\"}" \
  "garbage"; do echo "$payload" | node $H; echo -n "$? "; done; echo
CC_DASHBOARD_EVENTS=/nonexistent-root/e.jsonl node $H <<< "{\"session_id\":\"$SID\",\"hook_event_name\":\"Stop\",\"cwd\":\"$PWD\"}"; echo "unwritable exit=$?"
node $H < /dev/null; echo "empty stdin exit=$?"
cat $CC_DASHBOARD_EVENTS
node -e 'import("./webhook/schema.js").then(({parseEventLine}) => { const fs = require("fs"); console.log(fs.readFileSync(process.env.CC_DASHBOARD_EVENTS, "utf8").trim().split("\n").map(l => parseEventLine(l) ? "ok" : "INVALID").join(" ")) })'
```

Expected: ten `0` exit codes, `unwritable exit=0`, `empty stdin exit=0`, nothing else printed by the hook. The events file has exactly 7 lines in this order: `started`, `busy`, `waiting`, `message` to `listings-bc` with `notify_on_idle` true, `idle`, `idle` with `"session":null` and `"folder":"other"`, `ended`. The `idle_prompt` notification, the `Bash` tool, and `garbage` produce no line. The validator prints seven `ok`. If `$SID` resolved, `session` is the running session's display name and `pid` its PID.

Docs examples: every example in `docs/webhook/hooks.md` under `dashboard-hook.js` and in `docs/webhook/schema.md` runs by importing the module; outputs are what the docs show, except PIDs and names which are whatever session runs it.

Live acceptance, after the manager swaps the snippet: in two sessions, send one `SendMessage` from A to B, let B finish, then:

```
tail -n 20 ~/.claude/dashboard/events.jsonl
```

Expected: A has `busy` then a `message` with `"to"` equal to B's name, B has `busy` then `idle`, each with `session` equal to the ListAgents name and `pid` equal to the `/tmp/cc-socks/<pid>.sock` filename. A permission prompt in either session adds a `waiting` line before the next `busy` or `idle`. Starting a new session adds `started`; quitting adds `ended`.

## Requests

1. Manager: replace the W1 catch-all with this snippet, one edit, then delete `/tmp/cc-dashboard-raw.jsonl`. The `Notification` entry carries no matcher because matchers on that hook filter by `notification_type` on recent versions only; the script filters for `permission_prompt` itself, so an unmatched notification costs one 25 ms no-op.

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": "/Users/khangnguyen/.nvm/versions/node/v24.14.0/bin/node /Users/khangnguyen/Documents/path_finder/webhook/hooks/dashboard-hook.js", "timeout": 5 }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "/Users/khangnguyen/.nvm/versions/node/v24.14.0/bin/node /Users/khangnguyen/Documents/path_finder/webhook/hooks/dashboard-hook.js", "timeout": 5 }] }],
    "PostToolUse": [{ "matcher": "SendMessage", "hooks": [{ "type": "command", "command": "/Users/khangnguyen/.nvm/versions/node/v24.14.0/bin/node /Users/khangnguyen/Documents/path_finder/webhook/hooks/dashboard-hook.js", "timeout": 5 }] }],
    "Notification": [{ "hooks": [{ "type": "command", "command": "/Users/khangnguyen/.nvm/versions/node/v24.14.0/bin/node /Users/khangnguyen/Documents/path_finder/webhook/hooks/dashboard-hook.js", "timeout": 5 }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "/Users/khangnguyen/.nvm/versions/node/v24.14.0/bin/node /Users/khangnguyen/Documents/path_finder/webhook/hooks/dashboard-hook.js", "timeout": 5 }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command", "command": "/Users/khangnguyen/.nvm/versions/node/v24.14.0/bin/node /Users/khangnguyen/Documents/path_finder/webhook/hooks/dashboard-hook.js", "timeout": 5 }] }]
  }
}
```

2. Manager: `docs/overview.md` says the `from` field is a string. It is `null` when the registry lookup fails and only the process walk succeeds. Either allow `string or null` for `from` in the contract (schema.js already does), or accept that the page drops messages with a null sender. I recommend allowing null; the frontend can fall back to matching by PID later if we add one.

## Blocked

Empty.
