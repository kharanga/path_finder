# path_finder

Shows the Claude Code sessions running on one machine, the roles their humans gave them, and the messages they send each other. Two pieces: discovery (`discovery/discover.py`), where each session registers its role on disk, and the watcher (`viz/watcher.py`), which tails the sessions' transcripts and serves a live page.

## Install for use

The `path-finder` command bundles copies of both scripts and the pages, so it runs anywhere. Install it with pipx in one of two ways; run only one.

Either straight from GitHub, which needs no checkout:

```
pipx install git+https://github.com/kharanga/path_finder.git
```

Or from a wheel you built yourself inside the checkout (`pip wheel . --no-deps -w dist`):

```
pipx install dist/path_finder-0.2.0-py3-none-any.whl
```

Name each Claude Code session after its role with `/rename <folder>_<role>` (or just `/rename <role>`), where `<folder>` is the project folder's name, for example `/rename path_finder_manager`. Discovery reads that name from the session registry and reports the role with `role_source` `name`; an auto-generated name gives no role. `path-finder identify --role <role>` stores an explicit role that wins over the name. Then, in each session:

```
path-finder list                          # every live session under the current folder, with roles
path-finder window                        # opens a small app-mode window on this project's watcher, starting one if needed
```

To lay out a new agent workspace, `path-finder init --builder api --builder web` (in the project root, or with `--root DIR`) creates the empty placeholders that the `setup-agent-workspace` skill fills in but never creates: `CLAUDE.md`, `SPEC.md`, `.claude/roles/manager.md`, `.claude/roles/validator.md`, one `.claude/roles/<builder>.md` and one `handoff/<builder>/.gitkeep` per builder. Files that already exist are left untouched; every path is reported as created or exists.

Each project root gets its own watcher and port. `window` walks up from port 4780 (or `--port`), reuses the watcher whose `/state` root matches the current folder, and otherwise starts one on the first silent port. The next `window` from the same project finds that watcher again; the printed line names the port and root used.

The Claude Code plugin gives the same steps as slash commands, `/path-finder:mesh` and `/path-finder:init <builder names>`. Install it from GitHub:

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
