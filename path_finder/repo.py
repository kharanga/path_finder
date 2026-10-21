import os
from pathlib import Path

REPO_ENV_VAR = "PATH_FINDER_REPO"
REQUIRED_FILES = ("discovery/discover.py", "viz/watcher.py")


class RepoNotFound(Exception):
    pass


def is_repo(folder):
    return all((folder / relative).is_file() for relative in REQUIRED_FILES)


def candidate_folders():
    override = os.environ.get(REPO_ENV_VAR)
    if override:
        yield Path(override).expanduser().resolve()
    yield Path(__file__).resolve().parents[1]
    cwd = Path.cwd().resolve()
    yield cwd
    yield from cwd.parents


def find_repo():
    for folder in candidate_folders():
        if is_repo(folder):
            return folder
    raise RepoNotFound(
        "cannot find the path_finder checkout: run from inside it or set "
        f"{REPO_ENV_VAR} to the folder that holds discovery/discover.py and viz/watcher.py"
    )


def discover_script(repo):
    return repo / "discovery" / "discover.py"


def watcher_script(repo):
    return repo / "viz" / "watcher.py"
