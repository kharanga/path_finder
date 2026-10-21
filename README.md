# path_finder

Shows the Claude Code sessions running on one machine, the roles their humans gave them, and the messages they send each other. Two pieces: discovery (`discovery/discover.py`), where each session registers its role on disk, and the watcher (`viz/watcher.py`), which tails the sessions' transcripts and serves a live page.

## Install for use

The `path-finder` command bundles copies of both scripts and the pages, so it runs anywhere. With pipx, from the repository or from a built wheel:

```
pipx install git+https://github.com/kharanga/path_finder.git
pipx install path_finder-0.2.0-py3-none-any.whl
```

Then, in each Claude Code session:

```
path-finder identify --role manager      # once, when the session starts
path-finder list                          # every live session under the current folder, with roles
path-finder window                        # starts the watcher if needed and opens a small app-mode window
```

The Claude Code plugin gives the same two steps as slash commands, `/path-finder:identify <role>` and `/path-finder:mesh`. Install it from GitHub:

```
claude plugin marketplace add kharanga/path_finder
claude plugin install path-finder@path_finder
```

Or try it for one session from a checkout: `claude --plugin-dir plugin`.

## Where the data lives

Discovery writes `identity/<pid>.json` per session and `sessions.json` into one data directory: `$PATH_FINDER_HOME` when that variable is set, otherwise the checkout's `discovery/` when the scripts run inside a checkout (a folder holding `discovery/`, `viz/`, and `pyproject.toml`), otherwise `~/.path_finder`. The watcher reads the same directory. `path-finder --help` prints the directory in use. Set `PATH_FINDER_HOME` to the same path in every session that should see each other.

## Install for development

```
git clone https://github.com/kharanga/path_finder.git
cd path_finder
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m pytest tests
```

An editable install runs the checkout's scripts in place, so edits to `discovery/discover.py`, `viz/watcher.py`, or the pages take effect at once. The scripts also run directly: `python3 discovery/discover.py list` and `python3 viz/watcher.py serve`. To build a wheel: `pip wheel . --no-deps -w dist`.

`CLAUDE.md`, `SPEC.md`, and `.claude/roles/` describe how the agent team that builds this project works.
