# Ready: P2 round 2 2026-10-20

## Done
A Claude Code plugin at `plugin/`, written by hand (`claude plugin init` scaffolds into `~/.claude/skills/`, not into the checkout).

- `plugin/.claude-plugin/plugin.json`: name `path-finder`, version 0.1.0, description, author, keywords. No hooks, agents, MCP servers, or commands.
- `plugin/skills/identify/SKILL.md` (`/path-finder:identify <role>`): if `$ARGUMENTS` is blank, asks "What is this session's role?" with AskUserQuestion; then runs `identify --role <role>` followed by `self` and prints the `self` line. `allowed-tools: [Bash, AskUserQuestion]`, `argument-hint: <role>`.
- `plugin/skills/mesh/SKILL.md` (`/path-finder:mesh`): runs `list --root "$PWD"`, probes `http://127.0.0.1:4780/state` with curl and runs `window --root "$PWD"` only when nothing answers, then prints `http://127.0.0.1:4780/web`. `allowed-tools: [Bash]`.
- Both skills define a tiny shell function `pf` that calls `path-finder` when it is on PATH and otherwise `python3 "${CLAUDE_PLUGIN_ROOT}/../discovery/discover.py"` (identify) or `python3 -m path_finder.cli` from the checkout root (mesh, so `window` also works without the CLI). A first draft used a two-word variable for the fallback, which zsh does not word-split; the first headless test session reported the failure, and the function form replaced it. The snippets were then run under `zsh -c` through both branches.
- `plugin/README.md`: both skills, the trial install line `claude --plugin-dir plugin`, the keep-it install via a local marketplace (`claude plugin marketplace add <checkout>` then `claude plugin install path-finder@path_finder`), and a paragraph saying hooks are deliberately absent and why.

Verified on 2026-10-20 (Claude Code 2.1.305):

- `claude plugin validate plugin`: "Validation passed". It also prints two plugin-directory submission notes, a missing LICENSE and a missing icon; those only matter for submitting to the public directory and the license choice is the user's, so nothing was added.
- `claude --plugin-dir plugin -p "List every skill ... whose name contains path-finder"` printed exactly `path-finder:identify` and `path-finder:mesh`.
- `claude --plugin-dir plugin -p "/path-finder:identify builder" --allowedTools Bash` wrote `discovery/identity/94872.json` with role and label `builder` for that headless session (pid 94872) and printed its `self` line. The CLI was not on that session's PATH, so this exercised the `discover.py` fallback. That session has exited, so the next `list` drops the file.
- `claude --plugin-dir plugin -p "/path-finder:mesh" --allowedTools Bash` printed the five live sessions under the checkout (manager, discovery-builder, viz-builder, validator, and itself unidentified) and `http://127.0.0.1:4780/web`. The watcher was already answering on 4780, so no window was opened; the `window` branch itself was verified in P1.
- `python3 -m pytest tests`: 396 passed.

## Round 2 (validator item 1: no marketplace manifest)

Per the manager's decision, `.claude-plugin/marketplace.json` now sits at the checkout root (that folder is the discovery-builder's for the P-series). It names the marketplace `path_finder`, lists one plugin, `path-finder`, with source `./plugin`. The README's keep-install section now says where the manifest is; its two command lines are unchanged.

Verified: `claude plugin validate .` reports "Validating marketplace manifest ... Validation passed"; `claude plugin validate plugin` still passes. `claude plugin marketplace add /Users/khangnguyen/Documents/path_finder` printed "Successfully added marketplace: path_finder", and `claude plugin marketplace remove path_finder` cleaned it up again, leaving `known_marketplaces.json` as it was and no `path_finder` reference in `~/.claude/settings.json`. `claude plugin install path-finder@path_finder` was not run, because installing enables the plugin in the user's settings; the validator or the user can run it when wanted.

## How to test

```
claude plugin validate plugin
claude --plugin-dir plugin
```

In that session: `/path-finder:identify builder` should print the session's `self` JSON line with role `builder`, and `discovery/identity/<its pid>.json` should exist. `/path-finder:mesh` should print one JSON line per live session under the checkout and then `http://127.0.0.1:4780/web`; if port 4780 is silent it should also start the watcher and open the app window. `/path-finder:identify` with no argument should ask for the role first. Non-interactively the same two commands work with `claude --plugin-dir plugin -p "/path-finder:identify builder" --allowedTools Bash`.

## Requests
- Manager: mark P2 done in `SPEC.md`; add `plugin/` to the CLAUDE.md "What exists" list if wanted. If the plugin is ever submitted to the public directory, the repo needs a LICENSE file and the plugin an icon; both are the user's choice.
- Validator: `handoff/discovery/review.md` from P1 can stay; no tests were added for `plugin/` since the skills are prose plus one shell snippet each, and `claude plugin validate plugin/skills` covers the frontmatter.

## Blocked
None.
