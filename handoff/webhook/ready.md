# Ready: W7 role declaration (plus W5 notes closed)

## Done

- `webhook/declare-role.js <role>`: resolves the calling session by walking up to the `claude` process with `findClaudeAncestorPid` and reading that PID's registry entry with the new `lookupSessionRegistryByPid`, both imported from `hooks/dashboard-hook.js`. Appends one `session` event with the registry's current status as `state` (`busy` when unknown) and `role` set. Exit 0 silent on success; exit 1 with exactly one stderr line for a missing or invalid role, no `claude` ancestor, no registry entry, or an unwritable events file. Entry guard with `realpathSync` like every other script.
- `webhook/hooks/dashboard-hook.js`: `lookupSessionRegistry` now reads through a shared `readSessionRegistry`, and `lookupSessionRegistryByPid` is new. Hook behavior unchanged.
- Verified live: ran `node webhook/declare-role.js webhook-builder` from this session with no override, the real events file gained one line for PID 52134 with `"role":"webhook-builder"`, and a server started on the real file reports `['path-finder-37', 'busy', 'webhook-builder']` for that PID. The reducer keeps the role across later hook events with `role: null`.
- W5 review notes closed: `resolveStaticFile` now realpaths both root and candidate and rejects a symlink inside `frontend/` that points outside (verified with a temporary `escape.txt -> /etc/hosts`, removed afterwards); `parseArgs` rejects `--port`, `--liveness-interval`, `--poll` without a non-negative number and path or host flags without a value, with a clear message.
- Docs: `docs/webhook/declare-role.md` new; `hooks.md` gained `readSessionRegistry` and `lookupSessionRegistryByPid`; `server.md` updated for the symlink and flag errors; `README.md` indexes `declare-role.md`. `handoff/webhook/docs-examples.mjs` extended, now 50 checks, `passed 50, failed 0`.

## How to test

Unit and CLI, temp file only:

```
cd /Users/khangnguyen/Documents/path_finder
export CC_DASHBOARD_EVENTS=/tmp/role-test/events.jsonl; rm -rf /tmp/role-test
node webhook/declare-role.js webhook-builder; echo "exit=$?"; cat $CC_DASHBOARD_EVENTS
node webhook/declare-role.js; echo "exit=$?"
node webhook/declare-role.js 'bad/role!'; echo "exit=$?"
CC_DASHBOARD_EVENTS=/nonexistent-root/e.jsonl node webhook/declare-role.js manager; echo "exit=$?"
unset CC_DASHBOARD_EVENTS
node handoff/webhook/docs-examples.mjs /tmp/webhook-docs-examples
```

Expected: `exit=0` and one valid line whose `session`, `pid` are your session's name and `claude` PID, `state` is `busy`, `role` is `webhook-builder`; then the usage line and `exit=1` twice; then `declare-role: cannot write /nonexistent-root/e.jsonl` and `exit=1`; then `passed 50, failed 0` (the three checks that assert this session's PID and name need your own values or the value-by-nature treatment, as before).

Live acceptance (SPEC W7): with the server running on the real file, run `node webhook/declare-role.js validator` from your session and watch the page; the role appears under your body within one tail interval (300 ms). Declaring a different role replaces it. Your session then carries that role in `~/.claude/dashboard/events.jsonl` until the file is rotated.

W5 notes:

```
ln -s /etc/hosts frontend/escape.txt
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:4747/escape.txt   # with a server running: 404
rm frontend/escape.txt
node webhook/server.js --port; echo "exit=$?"                              # --port needs a non-negative number, exit 1
```

## Requests

1. Manager: the role is persisted only as an event, so after `events.jsonl` rotation a session has to declare again. Fine for now; the W8 skill can re-declare on `SessionStart` if you want persistence.
2. Manager: `docs/overview.md` role field says "declared role, if any"; you may want to point at `declare-role.js` as the declaring mechanism.

## Blocked

Empty.
