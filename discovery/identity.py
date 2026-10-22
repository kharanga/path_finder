import fcntl
import json
import os

from paths import DIRECTORY_PATH, IDENTITY_DIR, now_iso
from registry import live_sessions


def identity_path(pid):
    return IDENTITY_DIR / f"{pid}.json"


def read_identity(pid):
    try:
        with open(identity_path(pid)) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_identity(session, role):
    identity = {**session, "role": role, "label": role, "identified_at": now_iso()}
    IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    with open(identity_path(session["pid"]), "w") as handle:
        json.dump(identity, handle, indent=2)
        handle.write("\n")
    return identity


def drop_identities_of_dead_sessions(live_pids):
    IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    for path in IDENTITY_DIR.glob("*.json"):
        if not path.stem.isdigit() or int(path.stem) not in live_pids:
            path.unlink(missing_ok=True)


def with_identity(session):
    identity = read_identity(session["pid"]) or {}
    return {
        **session,
        "role": identity.get("role"),
        "label": identity.get("label"),
        "identified_at": identity.get("identified_at") or identity.get("set_at"),
    }


def is_identified(entry):
    return entry.get("role") is not None


def directory_entries():
    sessions = live_sessions()
    drop_identities_of_dead_sessions({s["pid"] for s in sessions})
    return [with_identity(s) for s in sessions]


def lock_directory():
    DIRECTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = open(DIRECTORY_PATH.with_suffix(".json.lock"), "w")
    fcntl.flock(lock_handle, fcntl.LOCK_EX)
    return lock_handle


def write_directory(entries):
    data = {"updated_at": now_iso(), "sessions": entries}
    tmp_path = DIRECTORY_PATH.with_suffix(".json.tmp")
    with open(tmp_path, "w") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(tmp_path, DIRECTORY_PATH)


def rebuild_directory():
    lock = lock_directory()
    try:
        entries = directory_entries()
        write_directory(entries)
    finally:
        lock.close()
    return entries
