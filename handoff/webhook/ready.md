# Ready: W8 research phase (proposal, no code yet) plus fake.js rename scenario

## Done

- `webhook/fake.js`: rename scenario added as scenario step 7. One session (`population[1]`) sends a message under its original name, is renamed mid-stream to `RENAMED_NAME` (`manager-drives-feature-work`) with the same PID via the new `renameSession`, then receives a `notify_on_idle` message and sends another under the new name. Present in raw and fixture modes. `docs/webhook/fake-generator.md` renumbered and updated, documented counts refreshed (129 fixture events, 127 raw lines, 18 distinct names, 7 notify messages). `handoff/webhook/docs-examples.mjs` has a `fake rename` check and the refreshed counts: `passed 51, failed 0`.
- W8 research done, no plugin files written. Sources: the official plugin docs at `code.claude.com/docs/en/plugins/manifest-reference.md`, `plugins/components.md`, `plugins/install.md`, `plugins/marketplace-reference.md`, `hooks.md`, and the locally installed official marketplace at `~/.claude/plugins/marketplaces/claude-plugins-official/` (read-only), which is the ground truth for Claude Code 2.1.291 on this machine.

## How to test

Rename scenario:

```
cd /Users/khangnguyen/Documents/path_finder
node webhook/fake.js --fixture /tmp/rn.json --start-time 2026-10-05T21:40:00Z
python3 -c "
import json; ev=json.load(open('/tmp/rn.json'))['events']; by={}
for e in ev:
    d=e['data']
    if d['type']=='session' and d['session']: by.setdefault(d['pid'],set()).add(d['session'])
print(len(ev), [(p,sorted(n)) for p,n in by.items() if len(n)>1])"
node webhook/fake.js --out /tmp/rn.jsonl --instant && grep -c manager-drives-feature-work /tmp/rn.jsonl
node handoff/webhook/docs-examples.mjs /tmp/webhook-docs-examples
```

Expected: `129 [(70052, ['listings-2c', 'manager-drives-feature-work'])]`, then `8` (the rename line, two messages under the new name, and later random-phase events), then `passed 51, failed 0` with the usual three value-by-nature checks.

Reducer behavior on rename, already covered by `state.md`: a later event with a new non-null name replaces the name and keeps the role.

## Requests

### W8 proposal for the manager, waiting for go

**Format facts that drive the layout** (from the docs and the installed marketplace):

- Plugin root holds `.claude-plugin/plugin.json` (only `name` required; `version`, `description`, `author` conventional). Hooks go in `hooks/hooks.json` at the plugin root with the same shape as settings, wrapped in a top-level `"hooks"` key. Commands are `commands/<name>.md` with frontmatter `description` and optional `argument-hint`. Skills are `skills/<name>/SKILL.md` with frontmatter `name`, `description`.
- `${CLAUDE_PLUGIN_ROOT}` expands in hook commands to the installed plugin directory, so no repo path is hard-coded. `${CLAUDE_PLUGIN_DATA}` is a per-plugin persistent directory. Every official plugin with hooks uses `"command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/x.sh\""`.
- Hook commands run through `sh` from the user's home directory, not a login shell, so nvm's `node` is not on PATH. That is why the manager had to hard-code the nvm path in W1 and W3.
- A single-repo marketplace is `.claude-plugin/marketplace.json` at the marketplace root with `plugins: [{name, source, description, version}]`; relative `source` resolves from the marketplace root. The official marketplace uses `./plugins/<name>`. Install paths: `claude --plugin-dir <dir>` for one session without installing, `/plugin marketplace add <owner/repo | ./path>` then `/plugin install <name>@<marketplace>` for a permanent user-scope install.
- `Notification` hooks accept a matcher on `notification_type`, and `SessionStart` matchers are `startup`, `resume`, `clear`, `compact`, `fork`.

**Proposed layout.** The repo root becomes the plugin root, because the hook scripts, server, and page must all sit under `${CLAUDE_PLUGIN_ROOT}` for a marketplace install to copy them. This adds four top-level folders outside `webhook/`; I propose webhook-builder owns them and the manager records that in `CLAUDE.md`.

```
path_finder/
  .claude-plugin/
    plugin.json          name "cc-dashboard", version 0.1.0, description, author
    marketplace.json     name "path-finder", plugins: [{ name: "cc-dashboard", source: "./" }]
  hooks/
    hooks.json           six entries, each: sh "${CLAUDE_PLUGIN_ROOT}/hooks/run-node.sh" "${CLAUDE_PLUGIN_ROOT}/webhook/hooks/dashboard-hook.js"
    run-node.sh          POSIX sh: picks node from $CC_DASHBOARD_NODE, then `command -v node`, then newest ~/.nvm/versions/node/*/bin/node, then /opt/homebrew/bin/node, /usr/local/bin/node; exec's it with stdin passed through; exits 0 silently if none found so a turn is never blocked
  commands/
    dashboard.md         /dashboard [demo|stop]: starts `node ${CLAUDE_PLUGIN_ROOT}/webhook/server.js` in the background if port 4747 is free, prints the URL; `demo` adds --demo; `stop` kills the server it started
  skills/
    declare-role/SKILL.md   tells Claude to run `node ${CLAUDE_PLUGIN_ROOT}/webhook/declare-role.js <role>` when the user says what role this session has; lists the exit codes
  webhook/   frontend/   docs/   (unchanged)
```

**SessionStart re-declare.** `declare-role.js` also writes the role into `~/.claude/dashboard/roles.json` as `{ "<cwd>": "<role>" }`. `dashboard-hook.js` on `SessionStart` reads that file and emits `started` with the role set when its `cwd` has an entry. Roles then survive restarts and `events.jsonl` rotation. Limitation to accept or reject: two sessions in the same folder share a role. If that matters, key by `session_id` instead, which survives `--resume` but not a fresh start.

**No hard-coded paths.** `hooks.json` and the command and skill markdown use `${CLAUDE_PLUGIN_ROOT}` only. Node comes from `run-node.sh`. The W3 settings snippet is removed by the manager once the plugin is installed, or every event is logged twice.

**Install steps to document in `docs/webhook/plugin.md`:**

```
# try for one session without installing
claude --plugin-dir /path/to/path_finder

# install for every session, from a local checkout
claude plugin marketplace add /path/to/path_finder
claude plugin install cc-dashboard@path-finder

# install from GitHub once pushed
claude plugin marketplace add <owner>/path_finder
claude plugin install cc-dashboard@path-finder

# then, in any session
/dashboard            # prints http://127.0.0.1:4747/
/dashboard demo
```

**Open points I will verify during the build, with fallbacks:**

1. Whether `"source": "./"` is accepted for a plugin that is also the marketplace root. The official marketplace only shows `./plugins/<name>`. Fallback: keep the plugin at the root and document `--plugin-dir` plus `claude plugin install` from a GitHub URL, or move to `plugins/cc-dashboard/` with symlinks, which I would rather avoid.
2. Whether `${CLAUDE_PLUGIN_ROOT}` is substituted inside command and skill markdown bodies, not only in hooks. Fallback: the command body asks Claude to resolve the plugin root with `claude plugin list` output or `CLAUDE_PLUGIN_ROOT` in the environment.
3. Whether `run-node.sh` is needed at all under the plugin runner, by testing a hook with a bare `node` on a PATH without nvm. If `node` resolves, the wrapper stays as a safety net anyway.

**Estimated size:** about 120 lines across `hooks.json`, `run-node.sh`, two markdown files, two manifests, plus the `roles.json` additions to `declare-role.js` and `dashboard-hook.js`, and `docs/webhook/plugin.md`. Acceptance test: `claude --plugin-dir` on a clean checkout with the W3 snippet removed from settings, start one session, confirm `started`/`busy`/`idle` lines appear, run `/dashboard`, open the URL.

### Other

- Manager: please confirm ownership of the four new top-level folders and whether the W3 snippet comes out of `~/.claude/settings.json` at install time or only after the plugin is verified.

## Blocked

Empty. Waiting for the manager's go on the proposal above.
