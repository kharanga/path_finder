# path-finder plugin

Two skills for Claude Code sessions working in a path_finder checkout.

- `/path-finder:identify <role>`: asks for the role when none is given, runs `path-finder identify --role <role>`, and prints `self`. Falls back to `python3 discovery/discover.py` from the checkout when the `path-finder` CLI is not installed.
- `/path-finder:mesh`: runs `path-finder list --root <cwd>`, starts the watcher with `path-finder window` when nothing answers on port 4780, and prints the page URL.

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

## No hooks

Hooks are deliberately absent. Every received message already costs a session a full turn, and discovery is self-registration from files on disk, so there is nothing a hook would need to do.
