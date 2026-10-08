import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "sessions"
SCRIPT_PATH = Path(__file__).resolve()
DISCOVERY_DIR = SCRIPT_PATH.parent
DIRECTORY_PATH = DISCOVERY_DIR / "sessions.json"
IDENTITY_DIR = DISCOVERY_DIR / "identity"
UI_PORT = 4780
UI_LOG = DISCOVERY_DIR / "ui.log"
UI_PID = DISCOVERY_DIR / "ui.pid"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pid_is_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def parent_and_command(pid):
    try:
        line = subprocess.run(
            ["ps", "-o", "ppid=,comm=", "-p", str(pid)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None, None
    parts = line.split(None, 1)
    if len(parts) != 2:
        return None, None
    return int(parts[0]), parts[1].strip()


def find_claude_ancestor_pid(start_pid=None, max_depth=8):
    pid = start_pid if start_pid is not None else os.getppid()
    for _ in range(max_depth):
        if pid <= 1:
            return None
        ppid, command = parent_and_command(pid)
        if ppid is None:
            return None
        if os.path.basename(command) == "claude":
            return pid
        pid = ppid
    return None


def socket_address(pid):
    return f"uds:/tmp/cc-socks/{pid}.sock"


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


def command_identify(args):
    me = own_session()
    if me is None:
        print("not running inside a Claude Code session", file=sys.stderr)
        return 1
    identity = write_identity(me, args.role)
    rebuild_directory()
    print(json.dumps(identity))
    return 0


def command_self(_args):
    me = own_session()
    if me is None:
        print("not running inside a Claude Code session", file=sys.stderr)
        return 1
    identity = read_identity(me["pid"])
    if identity is None:
        print("identity not set: ask your human for the role, then run identify", file=sys.stderr)
        return 2
    print(json.dumps({**me, "role": identity.get("role"), "label": identity.get("label")}))
    return 0


def command_list(args):
    me = own_session()
    my_pid = me["pid"] if me else None
    for entry in rebuild_directory():
        if not under_root(entry["cwd"], args.root):
            continue
        row = {**entry, "identified": is_identified(entry)}
        if entry["pid"] == my_pid:
            row["self"] = True
        print(json.dumps(row))
    return 0


def command_done(args):
    unidentified = [
        entry for entry in rebuild_directory()
        if under_root(entry["cwd"], args.root) and not is_identified(entry)
    ]
    if unidentified:
        names = ", ".join(f"{e['name']} (pid {e['pid']})" for e in unidentified)
        print(f"unidentified sessions: {names}", file=sys.stderr)
        return 1
    print("every live session under the root has an identity")
    return 0


def ui_is_up(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/sessions.json", timeout=1)
        return True
    except Exception:
        return False


def stop_ui():
    try:
        pid = int(UI_PID.read_text().strip())
        os.kill(pid, 15)
        UI_PID.unlink()
        print(f"stopped ui server pid {pid}")
    except (OSError, ValueError):
        print("no ui server pid file", file=sys.stderr)
        return 1
    return 0


def start_ui(port):
    with open(UI_LOG, "a") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(DISCOVERY_DIR)],
            stdout=log, stderr=log, start_new_session=True,
        )
    UI_PID.write_text(f"{server.pid}\n")
    for _ in range(20):
        if ui_is_up(port):
            break
        time.sleep(0.1)


def command_ui(args):
    if args.stop:
        return stop_ui()
    rebuild_directory()
    if not ui_is_up(args.port):
        start_ui(args.port)
    url = f"http://127.0.0.1:{args.port}/"
    subprocess.run(["open", url], check=False)
    print(url)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Discovery helper: which sessions are live and what role each one has")
    sub = parser.add_subparsers(dest="command", required=True)

    identify_parser = sub.add_parser("identify", help="store this session's role; run first, when the session starts")
    identify_parser.add_argument("--role", required=True)
    identify_parser.set_defaults(func=command_identify)

    sub.add_parser("self", help="print this session's name, pid, path, role, and label").set_defaults(func=command_self)

    list_parser = sub.add_parser("list", help="rebuild sessions.json and print live sessions with roles")
    list_parser.add_argument("--root", help="print only sessions whose cwd is under this path")
    list_parser.set_defaults(func=command_list)

    done_parser = sub.add_parser("done", help="exit 0 when every live session under the root has an identity")
    done_parser.add_argument("--root", help="only require identities from sessions under this path")
    done_parser.set_defaults(func=command_done)

    ui_parser = sub.add_parser("ui", help="serve the capsule page")
    ui_parser.add_argument("--port", type=int, default=UI_PORT)
    ui_parser.add_argument("--stop", action="store_true")
    ui_parser.set_defaults(func=command_ui)

    return parser


def main():
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
