# cc-dashboard plugin

The repo root is a Claude Code plugin. Installing it gives every session on the machine the dashboard hooks, a `/dashboard` command, and a `declare-role` skill, with no edits to `~/.claude/settings.json`.

## Layout

| Path | Purpose |
|---|---|
| `.claude-plugin/plugin.json` | manifest: name `cc-dashboard`, version, description, author |
| `.claude-plugin/marketplace.json` | single-plugin marketplace named `path-finder` whose only entry has `source: "./"` |
| `hooks/hooks.json` | six hook entries (`SessionStart`, `UserPromptSubmit`, `PostToolUse` matcher `SendMessage`, `Notification` matcher `permission_prompt`, `Stop`, `SessionEnd`), each running `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run-node.sh" "${CLAUDE_PLUGIN_ROOT}/webhook/hooks/dashboard-hook.js"` |
| `hooks/run-node.sh` | POSIX wrapper that finds `node` and execs the script |
| `commands/dashboard.md` | `/dashboard [demo|stop]` |
| `skills/declare-role/SKILL.md` | the role declaration skill |
| `webhook/`, `frontend/` | the server, hooks, generator, and page, unchanged |

No file hard-codes this repo's path or a Node install path. Hook commands use `${CLAUDE_PLUGIN_ROOT}`, which Claude Code expands to the installed plugin directory; the skill and command bodies use the same variable, which Claude Code substitutes in their content (verified: a headless session ran the skill and the script executed from the plugin root).

## Install

Try it for one session without installing:

```
claude --plugin-dir /path/to/path_finder
```

Install for every session from a local checkout:

```
claude plugin marketplace add /path/to/path_finder
claude plugin install cc-dashboard@path-finder
```

Install from GitHub once the repo is pushed:

```
claude plugin marketplace add <owner>/path_finder
claude plugin install cc-dashboard@path-finder
```

Then in any session:

```
/dashboard          # starts the server if port 4747 is free and prints http://127.0.0.1:4747/
/dashboard demo     # same, on fake data
/dashboard stop
```

Validate the manifests at any time with `claude plugin validate /path/to/path_finder`. It passes with one warning that `CLAUDE.md` at the plugin root is not loaded as plugin context, which is intended: that file is for people working on the repo.

If the W3 hook snippet is still in `~/.claude/settings.json` when the plugin is installed, every event is logged twice. Remove the snippet after the plugin is verified.

## Node resolution

Plugin hooks run through `sh` from the home directory, not a login shell, so a Node installed by nvm is not on `PATH`. `hooks/run-node.sh` picks the first of: `$CC_DASHBOARD_NODE` if set and executable, `node` on `PATH`, the newest `~/.nvm/versions/node/*/bin/node`, `/opt/homebrew/bin/node`, `/usr/local/bin/node`, `/usr/bin/node`. If none exists it exits 0 silently so a hook never fails a turn, and the dashboard simply records nothing until Node is installed. Set `CC_DASHBOARD_NODE=/path/to/node` in the environment Claude Code starts from to pin a specific binary.

Verified on this machine: with `PATH=/usr/bin:/bin` the wrapper found the nvm Node and the hook wrote its event; with `PATH=/nonexistent HOME=/nonexistent` it exited 0 with no output.

## Roles that survive restarts

`webhook/declare-role.js` appends the role event and also saves `{ "<start folder>": "<role>" }` to `~/.claude/dashboard/roles.json` (`CC_DASHBOARD_ROLES` overrides the path). `dashboard-hook.js` reads that file on every event and sets `role` when the session's `cwd` has an entry, so a restarted session, or one whose `events.jsonl` was rotated, shows its role again from its first `started` event.

Limitation, accepted by the manager: roles are keyed by start folder, so two sessions started in the same folder share one role, and declaring in one changes the other at its next event. Key by `session_id` instead if that ever matters; that survives `--resume` but not a fresh start.

## Open points from the proposal, and what was chosen

1. Plugin as its own marketplace root with `source: "./"`: accepted by `claude plugin validate`, so the layout stays at the repo root. The install from a local checkout and from GitHub still needs a run by the validator on a clean clone, see `handoff/webhook/ready.md`.
2. `${CLAUDE_PLUGIN_ROOT}` in skill and command bodies: works. A headless `claude -p --plugin-dir` session invoked the `declare-role` skill and the script ran from the plugin directory.
3. `run-node.sh`: kept. In the headless test the plugin hook ran under `sh` with the session's environment and found `node`, but the wrapper costs nothing and covers machines where it would not.

## Observed detail worth knowing

On `SessionEnd` the registry entry `~/.claude/sessions/<pid>.json` can already be gone, so the `ended` event may carry `"session": null`. The reducer keeps the name from earlier events, so the page is unaffected.

## Acceptance test on a clean checkout

```
git clone <repo> /tmp/path_finder-clean
claude plugin validate /tmp/path_finder-clean
export CC_DASHBOARD_EVENTS=/tmp/plugin-test/events.jsonl CC_DASHBOARD_ROLES=/tmp/plugin-test/roles.json
claude -p "Reply with the single word ok." --plugin-dir /tmp/path_finder-clean
claude -p "Use the declare-role skill to declare this session's role as plugin-test, then reply with the single word done." --plugin-dir /tmp/path_finder-clean --allowedTools=Bash
cat /tmp/plugin-test/events.jsonl; cat /tmp/plugin-test/roles.json
```

Expected: `started`, `busy`, `idle`, `ended` for the first session with its name and PID; for the second a `busy` line with `"role":"plugin-test"` followed by `idle` and `ended` carrying the role, and `roles.json` mapping the folder the `claude` command was launched from (not the plugin directory) to `plugin-test`. While the W3 snippet is still installed, every hook line appears twice, once per hook source; the `busy` line with the role appears once because `declare-role.js` writes it directly. Put the prompt before the flags; `--allowedTools` is variadic and swallows a trailing prompt.
