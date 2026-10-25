import argparse
import fcntl
import json
import os
import subprocess
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

OWN_FOLDER = str(Path(__file__).resolve().parent)
if OWN_FOLDER not in sys.path:
    sys.path.insert(0, OWN_FOLDER)
sys.dont_write_bytecode = True

import identity
import paths
import processes
import registry


def bound_to_this_namespace(function):
    return types.FunctionType(function.__code__, globals(), function.__name__, function.__defaults__, function.__closure__)


def re_export(module, names):
    for name in names:
        value = getattr(module, name)
        globals()[name] = bound_to_this_namespace(value) if isinstance(value, types.FunctionType) else value


re_export(paths, ("SESSIONS_DIR", "SCRIPT_PATH", "HOME_ENV_VAR", "DISCOVERY_DIR", "DIRECTORY_PATH", "IDENTITY_DIR", "checkout_holding", "data_dir", "now_iso"))
re_export(processes, ("pid_is_alive", "parent_and_command", "find_claude_ancestor_pid"))
re_export(registry, ("USER_NAME_SOURCE", "socket_address", "comparable_name", "role_from_name", "read_registry_entry", "live_sessions", "under_root", "own_session"))
re_export(identity, ("identity_path", "read_identity", "write_identity", "drop_identities_of_dead_sessions", "session_role", "with_identity", "is_identified",
                     "directory_entries", "lock_directory", "write_directory", "rebuild_directory"))


def command_identify(args):
    role = args.role.strip()
    if not role:
        print("role is blank: pass the role your human entered, for example --role manager", file=sys.stderr)
        return 2
    me = own_session()
    if me is None:
        print("not running inside a Claude Code session", file=sys.stderr)
        return 1
    identity = write_identity(me, role)
    rebuild_directory()
    print(json.dumps(identity))
    return 0


def command_self(_args):
    me = own_session()
    if me is None:
        print("not running inside a Claude Code session", file=sys.stderr)
        return 1
    found = session_role(me)
    if found["role"] is None:
        print("identity not set: name this session with /rename <folder>_<role> (or just <role>), or run identify --role <role>", file=sys.stderr)
        return 2
    print(json.dumps({**me, "role": found["role"], "label": found["label"], "role_source": found["role_source"]}))
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


def build_parser():
    parser = argparse.ArgumentParser(description="Discovery helper: which sessions are live and what role each one has")
    sub = parser.add_subparsers(dest="command", required=True)

    identify_parser = sub.add_parser("identify", help="store this session's role explicitly; overrides the role taken from the session name")
    identify_parser.add_argument("--role", required=True)
    identify_parser.set_defaults(func=command_identify)

    sub.add_parser("self", help="print this session's name, pid, path, role, label, and role_source (identity or name)").set_defaults(func=command_self)

    list_parser = sub.add_parser("list", help="rebuild sessions.json and print live sessions with roles")
    list_parser.add_argument("--root", help="print only sessions whose cwd is under this path")
    list_parser.set_defaults(func=command_list)

    done_parser = sub.add_parser("done", help="exit 0 when every live session under the root has an identity")
    done_parser.add_argument("--root", help="only require identities from sessions under this path")
    done_parser.set_defaults(func=command_done)

    return parser


def main():
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
