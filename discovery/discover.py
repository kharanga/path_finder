import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "sessions"
DEFAULT_OUT = Path(__file__).resolve().parent / "sessions.json"


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


def read_registry_entry(path):
    try:
        with open(path) as handle:
            entry = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(entry.get("pid"), int):
        return None
    return {"name": entry.get("name"), "pid": entry["pid"], "cwd": entry.get("cwd")}


def live_sessions():
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("*.json")):
        entry = read_registry_entry(path)
        if entry and pid_is_alive(entry["pid"]):
            sessions.append(entry)
    return sessions


def under_root(cwd, root):
    if root is None or cwd is None:
        return root is None
    return Path(cwd).resolve().is_relative_to(Path(root).resolve())


def own_session():
    pid = find_claude_ancestor_pid()
    if pid is None:
        return None
    return read_registry_entry(SESSIONS_DIR / f"{pid}.json")


def load_output(out_path):
    try:
        with open(out_path) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {"discovered_by": own_session(), "updated_at": None, "sessions": []}


def save_output(out_path, data):
    data["updated_at"] = now_iso()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def command_self(_args):
    me = own_session()
    if me is None:
        print("not running inside a Claude Code session", file=sys.stderr)
        return 1
    print(json.dumps(me))
    return 0


def command_list(args):
    me = own_session()
    my_pid = me["pid"] if me else None
    for session in live_sessions():
        if not under_root(session["cwd"], args.root):
            continue
        row = dict(session)
        if session["pid"] == my_pid:
            row["self"] = True
        print(json.dumps(row))
    return 0


def command_record(args):
    data = load_output(args.out)
    if data.get("discovered_by") is None:
        data["discovered_by"] = own_session()
    entry = {"name": args.name, "pid": args.pid, "cwd": args.path, "role": args.role, "replied_at": now_iso()}
    data["sessions"] = [s for s in data["sessions"] if s["pid"] != args.pid] + [entry]
    save_output(args.out, data)
    print(json.dumps(entry))
    return 0


def command_done(args):
    data = load_output(args.out)
    me = own_session()
    my_pid = me["pid"] if me else None
    recorded = {s["pid"] for s in data["sessions"]}
    missing = [
        s for s in live_sessions()
        if s["pid"] != my_pid and under_root(s["cwd"], args.root) and s["pid"] not in recorded
    ]
    print(json.dumps(data, indent=2))
    if missing:
        names = ", ".join(f"{s['name']} (pid {s['pid']})" for s in missing)
        print(f"missing replies from: {names}", file=sys.stderr)
        return 1
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Discovery helper: who is running, and what did they reply")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("self").set_defaults(func=command_self)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--root", help="keep only sessions whose cwd is under this path")
    list_parser.set_defaults(func=command_list)

    record_parser = sub.add_parser("record")
    record_parser.add_argument("--name", required=True)
    record_parser.add_argument("--pid", required=True, type=int)
    record_parser.add_argument("--path", required=True)
    record_parser.add_argument("--role")
    record_parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    record_parser.set_defaults(func=command_record)

    done_parser = sub.add_parser("done")
    done_parser.add_argument("--root", help="only require replies from sessions under this path")
    done_parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    done_parser.set_defaults(func=command_done)

    return parser


def main():
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
