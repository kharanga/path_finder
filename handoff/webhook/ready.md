# Ready: W8 plugin bundle

## Done

- Plugin at the repo root, layout as approved: `.claude-plugin/plugin.json` (name `cc-dashboard`, 0.1.0), `.claude-plugin/marketplace.json` (marketplace `path-finder`, one entry with `source: "./"`), `hooks/hooks.json` (six entries through `${CLAUDE_PLUGIN_ROOT}`), `hooks/run-node.sh` (POSIX node finder, exits 0 silently when no node), `commands/dashboard.md` (`/dashboard [demo|stop]`), `skills/declare-role/SKILL.md`. No repo path or nvm path anywhere in the plugin files.
- `claude plugin validate .` passes. Its one warning, `CLAUDE.md` at the plugin root is not plugin context, is intended and documented.
- Role persistence: `webhook/declare-role.js` now also writes `~/.claude/dashboard/roles.json` as `{ "<cwd>": "<role>" }` (`CC_DASHBOARD_ROLES` overrides; failure to write is an exit 1 line). `webhook/hooks/dashboard-hook.js` reads it on every event and sets `role` for a matching `cwd`, so a restarted session or a rotated events file shows the role from the first `started`. New exports: `saveRole` (declare-role), `readSavedRole` and `DEFAULT_ROLES_PATH` (hook). `resolveCallingSession` now returns `cwd` as well, see Requests item 1.
- Verified with headless sessions loading the plugin via `--plugin-dir`, with `CC_DASHBOARD_EVENTS` and `CC_DASHBOARD_ROLES` pointed at temp files so the real files were untouched. Run 1 (`claude -p "Reply with the single word ok." --plugin-dir "$PWD"`): `started`, `busy`, `idle`, `ended` for the new session `path-finder-ce`, PID 90848, each line exactly twice (settings hook plus plugin hook). Run 2 with the `declare-role` skill: a `busy` line with `"role":"plugin-test"`, then `idle` and `ended` carrying the role, and `roles.json` mapping this repo path to `plugin-test`. That proves `${CLAUDE_PLUGIN_ROOT}` expands in hooks and in skill bodies, and that `run-node.sh` found node under the plugin runner.
- Open points from the proposal, resolved and recorded in `docs/webhook/plugin.md`: `source: "./"` validates; the plugin root variable works in markdown; the node wrapper stays as a safety net. One observation recorded: `SessionEnd` can fire after the registry entry is deleted, giving `"session": null` on the `ended` line, which the reducer absorbs.
- Docs: `docs/webhook/plugin.md` new (layout, install, node resolution, roles, limitation, acceptance test). `declare-role.md`, `hooks.md`, `README.md` updated. `handoff/webhook/docs-examples.mjs` now 52 checks, `passed 52, failed 0`.
- Test suite run before handoff: `node --test "tests/**/*.test.js"` gives 82 tests, 78 pass, 2 fail. Both failures are the `cwd` shape change, see Requests item 1. Nothing else is red.

## How to test

Manifests and inventory:

```
cd /Users/khangnguyen/Documents/path_finder
claude plugin validate .
grep -c CLAUDE_PLUGIN_ROOT hooks/hooks.json commands/dashboard.md skills/declare-role/SKILL.md
grep -rn "khangnguyen\|\.nvm" .claude-plugin hooks commands skills; echo "hard-coded paths above: none expected"
```

Expected: `Validation passed with warnings` (the `CLAUDE.md` warning only), counts `12`, `3`, `1`, and no grep hits.

Node wrapper:

```
export CC_DASHBOARD_EVENTS=/tmp/w8-test/events.jsonl CC_DASHBOARD_ROLES=/tmp/w8-test/roles.json; rm -rf /tmp/w8-test
echo '{"session_id":"x","hook_event_name":"Stop","cwd":"/tmp/q"}' | PATH=/usr/bin:/bin /bin/sh hooks/run-node.sh webhook/hooks/dashboard-hook.js; echo "exit=$?"
echo '{}' | PATH=/nonexistent HOME=/nonexistent /bin/sh hooks/run-node.sh webhook/hooks/dashboard-hook.js; echo "exit=$?"
wc -l < /tmp/w8-test/events.jsonl
```

Expected: `exit=0` twice, no other output, and `1` line (the first command found the nvm node without PATH help and wrote an event; the second found no node and wrote nothing).

Plugin acceptance on a clean checkout, headless, real files untouched. Put the prompt before the flags; `--allowedTools` is variadic and swallows a trailing prompt. Each session costs a few API calls.

```
git clone /Users/khangnguyen/Documents/path_finder /tmp/path_finder-clean
claude plugin validate /tmp/path_finder-clean
export CC_DASHBOARD_EVENTS=/tmp/w8-test/events.jsonl CC_DASHBOARD_ROLES=/tmp/w8-test/roles.json; rm -rf /tmp/w8-test
claude -p "Reply with the single word ok." --plugin-dir /tmp/path_finder-clean
claude -p "Use the declare-role skill to declare this session's role as plugin-test, then reply with the single word done." --plugin-dir /tmp/path_finder-clean --allowedTools=Bash
python3 -c "
import json,collections
rows=[json.loads(l) for l in open('/tmp/w8-test/events.jsonl')]
print(collections.Counter((r['state'],r['role']) for r in rows)); print(sorted({r['pid'] for r in rows}))"
cat /tmp/w8-test/roles.json
```

Expected: `ok` then `done`; the counter shows two PIDs, with `('started', None)`, `('busy', None)`, `('idle', None)`, `('ended', None)` from the first session and `('busy', 'plugin-test')`, `('idle', 'plugin-test')`, `('ended', 'plugin-test')` from the second; every count is even while the W3 snippet is still in settings, because each event is logged by both hook sources. `roles.json` is `{"/tmp/path_finder-clean": "plugin-test"}`. Note the clone must be a git clone or copy, not a symlink, because `--plugin-dir` resolves the real path.

Install for every session (optional for review, the manager decides when): `claude plugin marketplace add /tmp/path_finder-clean` then `claude plugin install cc-dashboard@path-finder`, start a normal session, run `/dashboard`, open the URL. After that the manager removes the W3 snippet from `~/.claude/settings.json` so events stop doubling.

Docs examples: `node handoff/webhook/docs-examples.mjs /tmp/webhook-docs-examples` gives `passed 52, failed 0` with the three session-literal checks treated as value-by-nature as before.

Test suite: `node --test "tests/**/*.test.js"` gives 2 failures until Requests item 1 is applied, then 0.

## Requests

1. Validator: `resolveCallingSession` in `webhook/declare-role.js` now returns `{pid, name, cwd, folder, state}`; `cwd` is the registry start folder string, or `null` when the registry has none. The two `deepStrictEqual` assertions at `tests/unit/webhook/declare-role.test.js:18` and `:25` expect the old shape without `cwd`. Add `cwd: "/a/b/listings"` to the first expected object and `cwd: null` to the second (the values follow the mocks already in those tests). Everything else in the suite is green.
2. Manager: `CLAUDE.md` areas table and `.claude/roles/webhook-builder.md` should list `.claude-plugin/`, `hooks/`, `commands/`, `skills/` under webhook-builder, as you decided. `CLAUDE.md` setup can gain the two-line plugin install from `docs/webhook/plugin.md`.
3. Manager: after the validator's clean-checkout test passes and you install the plugin for real, remove the W3 snippet from `~/.claude/settings.json`.

## Blocked

Empty.
