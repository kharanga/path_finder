# path-finder plugin

Two skills for Claude Code sessions working in a path_finder checkout. Name each session after its role first, with `/rename <folder>_<role>` (or just `/rename <role>`), where `<folder>` is the project folder's name; discovery takes the role from that name. `path-finder identify --role <role>` remains as an explicit override.

- `/path-finder:init <builder names>`: asks for the builder names when none are given, runs `path-finder init --root <cwd> --builder <name> ...`, which creates the empty placeholders the `setup-agent-workspace` skill fills in (`CLAUDE.md`, `SPEC.md`, `.claude/roles/manager.md`, `.claude/roles/validator.md`, one role file and one `handoff/<name>/.gitkeep` per builder; existing files are left alone), prints the created list, and tells the user to run that skill next.
- `/path-finder:mesh`: runs `path-finder list --root <cwd>`, then `path-finder window --root <cwd>`, which reuses this project's watcher or starts one on the first free port from 4780 upward, and prints the page URL `window` chose. A session listed without a role has an auto-generated name; the skill tells the user to `/rename` it.

## Install

Trial, for one session, from the checkout root:

```
claude --plugin-dir plugin
```

For keeps, add the checkout as a local marketplace (its manifest is `.claude-plugin/marketplace.json` at the checkout root, which lists this plugin with source `./plugin`) and install from it:

```
claude plugin marketplace add /Users/khangnguyen/Documents/path_finder
claude plugin install path-finder@path_finder
```

The CLI itself comes from `pip install -e .` or `pipx install .` in the checkout root (P1). Without it the skills use the scripts in the checkout directly.

## Where the data lives

`mesh` writes and reads the discovery data directory: `identity/<pid>.json` per session and `sessions.json`. It is `$PATH_FINDER_HOME` when that variable is set, otherwise the checkout's `discovery/` when the scripts run inside a checkout (a folder holding `discovery/`, `viz/`, and `pyproject.toml`), otherwise `~/.path_finder`. `path-finder --help` prints the directory in use.

## No hooks

Hooks are deliberately absent. Every received message already costs a session a full turn, and discovery is self-registration from files on disk, so there is nothing a hook would need to do.
