# declare-role.js

Lets a session label itself with a role (`manager`, `validator`, `webhook-builder`, anything matching the pattern below). Run from inside a Claude Code session:

```
node webhook/declare-role.js webhook-builder
```

It finds the calling session by walking up the process tree to the `claude` process, reads that PID's entry in `~/.claude/sessions/`, appends one `session` event with the session's current state and `role` set to `$CC_DASHBOARD_EVENTS` (default `~/.claude/dashboard/events.jsonl`), and saves the role for the session's start folder in `$CC_DASHBOARD_ROLES` (default `~/.claude/dashboard/roles.json`). The hook reads that file on every event, so later events carry the role and a session restarted in the same folder shows it from its first `started` event. Declaring again replaces the role.

Exit codes: 0 and no output on success; 1 and exactly one line on stderr when the argument is missing or invalid, no `claude` ancestor exists, the PID has no registry entry, or the events file or roles file cannot be written.

Role pattern: 1 to 40 characters, starting with a letter or digit, then letters, digits, spaces, `_` or `-`.

## parseRole(argv)

What it does: validates and trims the role argument.

Inputs: `argv` (string[]) without the node and script entries.

Output: the trimmed role string.

Errors: throws `Error("usage: declare-role.js <role>   (1-40 letters, digits, spaces, _ or -)")`.

Example: `parseRole(["  manager "])` is `"manager"`; `parseRole([])` and `parseRole(["bad/role!"])` throw the usage error.

## resolveCallingSession(options = {})

What it does: finds the `claude` ancestor PID, looks it up in the registry, and derives the current state from the registry `status` (`busy` when the status is not a known non-ended state, since a session running this command is busy by definition).

Inputs: `options.findPid` (function → integer or null) and `options.lookup` (function(pid) → registry entry or null), both injectable for tests; defaults are `findClaudeAncestorPid` and `lookupSessionRegistryByPid` from `hooks/dashboard-hook.js`.

Output: `{pid, name, cwd, folder, state}` with `cwd` the registry start folder (string or null) and `folder` its basename.

Errors: throws `Error("declare-role: no claude process found above this one")` or `Error("declare-role: no registry entry for claude pid <pid>")`.

Example:

```js
import { resolveCallingSession } from "./webhook/declare-role.js";
resolveCallingSession({ findPid: () => 1, lookup: () => ({ pid: 1, name: "x-1", cwd: "/a/b/listings", status: "idle" }) })
// {"pid":1,"name":"x-1","cwd":"/a/b/listings","folder":"listings","state":"idle"}
resolveCallingSession({ findPid: () => 1, lookup: () => ({ pid: 1, name: null, cwd: null, status: "weird" }) })
// {"pid":1,"name":null,"cwd":null,"folder":"","state":"busy"}
resolveCallingSession({ findPid: () => null })                        // throws: declare-role: no claude process found above this one
resolveCallingSession({ findPid: () => 999999, lookup: () => null })  // throws: declare-role: no registry entry for claude pid 999999
```

## saveRole(rolesPath, cwd, role)

What it does: merges `{cwd: role}` into the JSON object at `rolesPath`, creating the file and its directory, replacing a non-object file.

Inputs: `rolesPath` (string); `cwd` (string, the start folder); `role` (string).

Output: `true` on success, `false` when `cwd` is empty or the write fails.

Errors: none thrown.

Example:

```js
import { saveRole } from "./webhook/declare-role.js";
saveRole("/tmp/roles-example.json", "/a/b", "manager")   // true
saveRole("/tmp/roles-example.json", "/c", "validator")   // true, file is {"/a/b":"manager","/c":"validator"}
saveRole("/nonexistent-root/r.json", "/a", "x")          // false
saveRole("/tmp/roles-example.json", "", "x")             // false
```

## buildRoleEvent(session, role, now = new Date())

What it does: builds the §3 session event carrying the role.

Inputs: `session` from `resolveCallingSession`; `role` (string); `now` (Date).

Output: `{ts, type: "session", session, folder, pid, state, role}`.

Errors: none.

Example:

```js
buildRoleEvent({ pid: 29904, name: "listings-bc", folder: "listings", state: "idle" }, "validator", new Date("2026-10-05T21:40:00Z"))
// {"ts":"2026-10-05T21:40:00.000Z","type":"session","session":"listings-bc","folder":"listings","pid":29904,"state":"idle","role":"validator"}
```

## main(argv = process.argv.slice(2))

What it does: runs the whole flow and returns the exit code; the CLI entry calls `process.exit(main())`.

Inputs: `argv[0]` the role; `CC_DASHBOARD_EVENTS` and `CC_DASHBOARD_ROLES` optionally override the events and roles files.

Output: `0` on success, `1` after writing one stderr line.

Errors: none thrown; every failure becomes the exit code.

Example, from inside a Claude Code session:

```
export CC_DASHBOARD_EVENTS=/tmp/role-example/events.jsonl CC_DASHBOARD_ROLES=/tmp/role-example/roles.json
node webhook/declare-role.js webhook-builder; echo "exit=$?"
cat /tmp/role-example/events.jsonl /tmp/role-example/roles.json
node webhook/declare-role.js; echo "exit=$?"
CC_DASHBOARD_EVENTS=/nonexistent-root/e.jsonl node webhook/declare-role.js manager; echo "exit=$?"
```

Expected:

```
exit=0
{"ts":"...","type":"session","session":"<this session's name>","folder":"path_finder","pid":<this session's claude PID>,"state":"busy","role":"webhook-builder"}
{
  "/Users/khangnguyen/Documents/path_finder": "webhook-builder"
}
usage: declare-role.js <role>   (1-40 letters, digits, spaces, _ or -)
exit=1
declare-role: cannot write /nonexistent-root/e.jsonl
exit=1
```

Run without the overrides to declare for real; the dashboard shows the role under the body within a second. The plugin's `declare-role` skill runs exactly this command, see `plugin.md`.
