# Ready: W1 verify hook behavior, W2 runtime manifest

## Done

- `webhook/hooks/capture-raw.js`: catch-all hook. Reads the hook JSON from stdin, appends one redacted record per invocation to a temp log, exits 0 always. Values are replaced by type and length; only `session_id`, `hook_event_name`, `cwd`, `tool_name`, `source`, `reason`, `stop_hook_active`, `permission_mode`, and the `SendMessage` inputs `to` and `notify_when_idle` are kept verbatim. Prompt text and message text are never logged.
- `webhook/package.json`: Node 24 manifest, `"type": "module"`, zero dependencies, scripts `start`, `demo`, `fake` (the last two land with W4 and W5).
- `webhook/schema.js`, `webhook/state.js`, `webhook/liveness.js`: early drafts for W3 and W5, not yet part of any task handoff. Ignore for this review.
- `docs/webhook/hooks.md`: raw hook input shape, how a hook maps to its session, every exported function of `capture-raw.js`.
- `SPEC.md` §6: preliminary W-U1 and W-U2 findings with evidence. W-U3 and W-U4 wait for the raw log.

## How to test

Smoke test without installing anything:

```
cd /Users/khangnguyen/Documents/path_finder
echo '{"session_id":"test-123","hook_event_name":"PostToolUse","cwd":"/tmp/x","tool_name":"SendMessage","tool_input":{"to":"listings-bc","message":"hello there","notify_when_idle":true},"tool_response":{"ok":true}}' | node webhook/hooks/capture-raw.js /tmp/raw-test.jsonl; echo "exit=$?"
echo 'not json' | node webhook/hooks/capture-raw.js /tmp/raw-test.jsonl; echo "exit=$?"
echo '{"a":1}' | node webhook/hooks/capture-raw.js /nonexistent-root/raw.jsonl; echo "exit=$?"
wc -l /tmp/raw-test.jsonl
```

Expected: three lines `exit=0`, `wc -l` reports 2. The first record's `input.kept.tool_input` is `{"to":"listings-bc","notify_when_idle":true}` and `input.shape.tool_input.message` is `string(11)`. No prompt or message text appears anywhere in the file.

After the manager installs the snippet below: in one session run `SendMessage` to another session, let the recipient finish its turn, then check `/tmp/cc-dashboard-raw.jsonl` has records with `hook_event_name` of `UserPromptSubmit`, `PostToolUse` with `tool_name` `SendMessage`, and `Stop`.

Runtime check for W2: `node --version` prints v24.x. `cd webhook && npm install` succeeds with no dependencies to fetch.

## Requests

1. Manager: install this catch-all into `~/.claude/settings.json` for the W1 test window. It covers every event, not just the five the dashboard needs, so the raw log also shows which events fire on inbox-driven turns.

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": "node /Users/khangnguyen/Documents/path_finder/webhook/hooks/capture-raw.js /tmp/cc-dashboard-raw.jsonl", "timeout": 5 }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "node /Users/khangnguyen/Documents/path_finder/webhook/hooks/capture-raw.js /tmp/cc-dashboard-raw.jsonl", "timeout": 5 }] }],
    "PreToolUse": [{ "matcher": "SendMessage", "hooks": [{ "type": "command", "command": "node /Users/khangnguyen/Documents/path_finder/webhook/hooks/capture-raw.js /tmp/cc-dashboard-raw.jsonl", "timeout": 5 }] }],
    "PostToolUse": [{ "hooks": [{ "type": "command", "command": "node /Users/khangnguyen/Documents/path_finder/webhook/hooks/capture-raw.js /tmp/cc-dashboard-raw.jsonl", "timeout": 5 }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "node /Users/khangnguyen/Documents/path_finder/webhook/hooks/capture-raw.js /tmp/cc-dashboard-raw.jsonl", "timeout": 5 }] }],
    "SubagentStop": [{ "hooks": [{ "type": "command", "command": "node /Users/khangnguyen/Documents/path_finder/webhook/hooks/capture-raw.js /tmp/cc-dashboard-raw.jsonl", "timeout": 5 }] }],
    "Notification": [{ "hooks": [{ "type": "command", "command": "node /Users/khangnguyen/Documents/path_finder/webhook/hooks/capture-raw.js /tmp/cc-dashboard-raw.jsonl", "timeout": 5 }] }],
    "PreCompact": [{ "hooks": [{ "type": "command", "command": "node /Users/khangnguyen/Documents/path_finder/webhook/hooks/capture-raw.js /tmp/cc-dashboard-raw.jsonl", "timeout": 5 }] }],
    "SessionEnd": [{ "hooks": [{ "type": "command", "command": "node /Users/khangnguyen/Documents/path_finder/webhook/hooks/capture-raw.js /tmp/cc-dashboard-raw.jsonl", "timeout": 5 }] }]
  }
}
```

   `node` resolves through the shell PATH of the session. If a session's PATH lacks nvm, replace `node` with `/Users/khangnguyen/.nvm/versions/node/v24.14.0/bin/node`. Hooks pick up settings changes on the next session start, so one new session (or restart) is needed to see `SessionStart`, while already-running sessions may or may not reload.

2. Manager: tell me once installed. I will send one test message to the validator, wait for its turn to end, then fill in §6 W-U3 and W-U4 and ask for the catch-all to be removed.

3. Manager, `CLAUDE.md` setup commands for W2:

```
# install (no dependencies, this only checks the manifest)
cd webhook && npm install

# run server (after W5)
node webhook/server.js            # prints the dashboard URL, default http://127.0.0.1:4747

# demo with fake data (after W4 and W5)
node webhook/server.js --demo
```

4. Validator: `node:test` with `node --test tests/` fits this runtime with no dependencies. Every module in `webhook/` is ESM and exports its functions, so unit tests can import them directly.

## Blocked

Empty.
