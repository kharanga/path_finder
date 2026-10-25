import json
import os
from pathlib import Path

from paths import SESSIONS_DIR
from processes import find_claude_ancestor_pid, pid_is_alive


USER_NAME_SOURCE = "user"


def socket_address(pid):
    return f"uds:/tmp/cc-socks/{pid}.sock"


def comparable_name(text):
    return text.replace("-", "_").lower()


def role_from_name(name, cwd, name_source):
    if name_source != USER_NAME_SOURCE or not name:
        return None
    folder = Path(cwd).name if cwd else ""
    folder_prefix = f"{comparable_name(folder)}_" if folder else None
    bare = name[len(folder_prefix):] if folder_prefix and comparable_name(name).startswith(folder_prefix) else name
    return bare.replace("_", "-").lower() or None


def read_registry_entry(path):
    try:
        with open(path) as handle:
            entry = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(entry.get("pid"), int):
        return None
    return {
        "pid": entry["pid"],
        "name": entry.get("name"),
        "name_source": entry.get("nameSource"),
        "cwd": entry.get("cwd"),
        "socket": socket_address(entry["pid"]),
        "session_id": entry.get("sessionId"),
    }


def live_sessions():
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("*.json")):
        entry = read_registry_entry(path)
        if entry and pid_is_alive(entry["pid"]):
            sessions.append(entry)
    return sessions


def under_root(cwd, root):
    if root is None:
        return True
    if cwd is None:
        return False
    return Path(cwd).resolve().is_relative_to(Path(root).resolve())


def own_session():
    pid = find_claude_ancestor_pid()
    if pid is None:
        return None
    return read_registry_entry(SESSIONS_DIR / f"{pid}.json")
