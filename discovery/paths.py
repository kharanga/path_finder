import os
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "sessions"
SCRIPT_PATH = Path(__file__).resolve()
HOME_ENV_VAR = "PATH_FINDER_HOME"


def checkout_holding(path):
    for folder in path.parents:
        if (folder / "discovery").is_dir() and (folder / "viz").is_dir() and (folder / "pyproject.toml").is_file():
            return folder
    return None


def data_dir():
    override = os.environ.get(HOME_ENV_VAR)
    if override:
        return Path(override).expanduser()
    checkout = checkout_holding(SCRIPT_PATH)
    if checkout is not None:
        return checkout / "discovery"
    return Path.home() / ".path_finder"


DISCOVERY_DIR = data_dir()
DIRECTORY_PATH = DISCOVERY_DIR / "sessions.json"
IDENTITY_DIR = DISCOVERY_DIR / "identity"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
