import os
from pathlib import Path

REPO_ENV_VAR = "PATH_FINDER_REPO"
HOME_ENV_VAR = "PATH_FINDER_HOME"
REQUIRED_FILES = ("discovery/discover.py", "viz/watcher.py")
VENDOR_DIR = Path(__file__).resolve().parent / "_vendor"


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


def discover_script(folder):
    return folder / "discovery" / "discover.py"


def watcher_script(folder):
    return folder / "viz" / "watcher.py"


def vendored_copies_present():
    return is_repo(VENDOR_DIR)


def data_dir(code_folder):
    override = os.environ.get(HOME_ENV_VAR)
    if override:
        return Path(override).expanduser()
    if code_folder != VENDOR_DIR and (code_folder / "pyproject.toml").is_file():
        return code_folder / "discovery"
    return Path.home() / ".path_finder"


def data_dir_description():
    try:
        folder = find_repo()
    except RepoNotFound:
        if vendored_copies_present():
            folder = VENDOR_DIR
        else:
            return f"data directory: {HOME_ENV_VAR} when set, else ~/.path_finder (no checkout found)"
    where = "vendored copies inside the package" if folder == VENDOR_DIR else f"checkout {folder}"
    return f"code: {where}\ndata directory: {data_dir(folder)}  ({HOME_ENV_VAR} when set, else the checkout's discovery/, else ~/.path_finder)"
