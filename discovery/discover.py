import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "sessions"
SCRIPT_PATH = Path(__file__).resolve()
DISCOVERY_DIR = SCRIPT_PATH.parent
DEFAULT_OUT = DISCOVERY_DIR / "sessions.json"
IDENTITY_DIR = DISCOVERY_DIR / "identity"


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


def own_pid(args):
    override = getattr(args, "as_pid", None)
    if override is not None:
        return override
    me = own_session()
    return me["pid"] if me else None


def identity_path(pid):
    return IDENTITY_DIR / f"{pid}.json"


def read_identity(pid):
    try:
        with open(identity_path(pid)) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def empty_directory():
    return {"participants": [], "updated_at": None, "sessions": []}


def locked_directory(out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = out_path.with_suffix(out_path.suffix + ".lock")
    lock_handle = open(lock_path, "w")
    fcntl.flock(lock_handle, fcntl.LOCK_EX)
    return lock_handle


def read_directory(out_path):
    try:
        with open(out_path) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return empty_directory()


def write_directory(out_path, data):
    data["updated_at"] = now_iso()
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    with open(tmp_path, "w") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(tmp_path, out_path)


def command_identify(args):
    me = own_session()
    if me is None:
        print("not running inside a Claude Code session", file=sys.stderr)
        return 1
    identity = {**me, "role": args.role, "label": args.label, "set_at": now_iso()}
    IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    with open(identity_path(me["pid"]), "w") as handle:
        json.dump(identity, handle, indent=2)
        handle.write("\n")
    print(json.dumps(identity))
    return 0


def command_self(_args):
    me = own_session()
    if me is None:
        print("not running inside a Claude Code session", file=sys.stderr)
        return 1
    identity = read_identity(me["pid"])
    if identity is None:
        print("identity not set: ask your human for role and label, then run identify", file=sys.stderr)
        return 2
    print(json.dumps({**me, "role": identity.get("role"), "label": identity.get("label")}))
    return 0


def command_list(args):
    my_pid = own_pid(args)
    for session in live_sessions():
        if not under_root(session["cwd"], args.root):
            continue
        row = dict(session)
        if session["pid"] == my_pid:
            row["self"] = True
        print(json.dumps(row))
    return 0


def command_record(args):
    reporter = own_pid(args)
    if reporter is None:
        print("cannot determine own session pid, pass --as-pid PID", file=sys.stderr)
        return 1
    lock = locked_directory(args.out)
    try:
        data = read_directory(args.out)
        existing = next((s for s in data["sessions"] if s["pid"] == args.pid), None) or {}
        heard_by = sorted(set(existing.get("heard_by", [])) | {reporter})
        entry = {
            "name": args.name,
            "pid": args.pid,
            "cwd": args.path,
            "role": args.role if args.role is not None else existing.get("role"),
            "label": args.label if args.label is not None else existing.get("label"),
            "replied_at": now_iso(),
            "heard_by": heard_by,
        }
        data["sessions"] = [s for s in data["sessions"] if s["pid"] != args.pid] + [entry]
        data["participants"] = sorted(set(data["participants"]) | {reporter})
        write_directory(args.out, data)
    finally:
        lock.close()
    print(json.dumps(entry))
    return 0


def command_done(args):
    reporter = own_pid(args)
    data = read_directory(args.out)
    heard_by_me = {s["pid"] for s in data["sessions"] if reporter in s.get("heard_by", [])}
    missing = [
        s for s in live_sessions()
        if s["pid"] != reporter and under_root(s["cwd"], args.root) and s["pid"] not in heard_by_me
    ]
    print(json.dumps(data, indent=2))
    if missing:
        names = ", ".join(f"{s['name']} (pid {s['pid']})" for s in missing)
        print(f"pid {reporter} is still missing replies from: {names}", file=sys.stderr)
        return 1
    return 0


ASK_TEXT = f"discovery: reply with the one-line output of python3 {SCRIPT_PATH} self"

IDENTIFY_INSTRUCTION = "\n".join([
    "Ask your human with AskUserQuestion, one question with two fields:",
    "   \"What is this session's role?\" and \"What label should this session show?\"",
    f"   Then run: python3 {SCRIPT_PATH} identify --role \"<role>\" --label \"<label>\"",
])


def start_text(root, report_to):
    root_flag = f" --root {root}" if root else ""
    return "\n".join([
        f"discovery: start{root_flag}",
        "You are one node in a discovery mesh. Do exactly this, then stop.",
        f"0. {IDENTIFY_INSTRUCTION}",
        "   Do this first, before step 1 and before answering any ask.",
        f"1. Run: python3 {SCRIPT_PATH} list{root_flag}",
        "   One JSON line per live session; the line with \"self\": true is you.",
        "2. For every other line, send that session (by its name) this exact message with SendMessage:",
        f"   {ASK_TEXT}",
        "3. Each reply is one JSON line with name, pid, cwd, role, label. For each reply run:",
        f"   python3 {SCRIPT_PATH} record --name <name> --pid <pid> --path <cwd> --role \"<role>\" --label \"<label>\"",
        f"4. Run: python3 {SCRIPT_PATH} done{root_flag}",
        "   Exit 0 means you heard from everyone. Exit 1 names who is missing: ask each of them once more, record, run done again.",
        f"5. Message {report_to} with one line: discovery done, exit <code>, heard from <n> sessions.",
        "While doing this, if you receive a message starting with \"discovery: reply with\", run",
        f"   python3 {SCRIPT_PATH} self",
        "and send its one output line back to that sender. If self exits 2, do step 0 first, then run self again and reply.",
        "Answer every such request, even after your own round is done.",
        "Do not edit files other than what the script writes. Do not run git.",
    ])


def command_protocol(args):
    me = own_session()
    report_to = args.report_to or (me["name"] if me else "the manager")
    print("=== ask ===")
    print(ASK_TEXT)
    print("=== start ===")
    print(start_text(args.root, report_to))
    return 0


def add_as_pid(parser):
    parser.add_argument("--as-pid", dest="as_pid", type=int, help="override own session pid, for local tests")


def build_parser():
    parser = argparse.ArgumentParser(description="Discovery helper: who is running, who they are, and what they replied")
    sub = parser.add_subparsers(dest="command", required=True)

    identify_parser = sub.add_parser("identify")
    identify_parser.add_argument("--role", required=True)
    identify_parser.add_argument("--label", required=True)
    identify_parser.set_defaults(func=command_identify)

    sub.add_parser("self").set_defaults(func=command_self)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--root", help="keep only sessions whose cwd is under this path")
    add_as_pid(list_parser)
    list_parser.set_defaults(func=command_list)

    record_parser = sub.add_parser("record")
    record_parser.add_argument("--name", required=True)
    record_parser.add_argument("--pid", required=True, type=int)
    record_parser.add_argument("--path", required=True)
    record_parser.add_argument("--role")
    record_parser.add_argument("--label")
    record_parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    add_as_pid(record_parser)
    record_parser.set_defaults(func=command_record)

    done_parser = sub.add_parser("done")
    done_parser.add_argument("--root", help="only require replies from sessions under this path")
    done_parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    add_as_pid(done_parser)
    done_parser.set_defaults(func=command_done)

    protocol_parser = sub.add_parser("protocol")
    protocol_parser.add_argument("--root")
    protocol_parser.add_argument("--report-to", help="session name that collects results, defaults to the caller")
    protocol_parser.set_defaults(func=command_protocol)

    return parser


def main():
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
