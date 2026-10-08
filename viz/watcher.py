import argparse
import json
import os
import re
import sys
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
VIZ_DIR = Path(__file__).resolve().parent
IDENTITY_DIR = VIZ_DIR.parent / "discovery" / "identity"


def pid_is_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def socket_address(pid):
    return f"uds:/tmp/cc-socks/{pid}.sock"


def encoded_cwd(cwd):
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


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
        "started_at_ms": entry.get("startedAt"),
    }


def read_identity(pid):
    try:
        with open(IDENTITY_DIR / f"{pid}.json") as handle:
            identity = json.load(handle)
    except (OSError, ValueError):
        return {"role": None, "label": None}
    return {"role": identity.get("role"), "label": identity.get("label")}


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


def transcripts_named_by_session_id(session_id, cwd):
    matches = sorted(PROJECTS_DIR.glob(f"*/{session_id}.jsonl"))
    if len(matches) > 1 and cwd:
        under_own_folder = [m for m in matches if m.parent.name == encoded_cwd(cwd)]
        if under_own_folder:
            return under_own_folder
    return matches


def transcripts_started_after_session(cwd, started_at_ms):
    if not cwd:
        return []
    folder = PROJECTS_DIR / encoded_cwd(cwd)
    if not folder.is_dir():
        return []
    started_at_s = (started_at_ms or 0) / 1000
    return sorted(
        path for path in folder.glob("*.jsonl") if path.stat().st_mtime >= started_at_s
    )


def resolve_transcript(entry):
    if entry["session_id"]:
        matches = transcripts_named_by_session_id(entry["session_id"], entry["cwd"])
        if len(matches) == 1:
            return {"transcript": str(matches[0]), "method": "registry sessionId"}
        if not matches:
            return {"transcript": None, "method": "registry sessionId, transcript not written yet"}
        return {"transcript": None, "method": f"registry sessionId, ambiguous ({len(matches)} files)"}
    candidates = transcripts_started_after_session(entry["cwd"], entry["started_at_ms"])
    if len(candidates) == 1:
        return {
            "transcript": str(candidates[0]),
            "session_id": candidates[0].stem,
            "method": "cwd folder, single transcript since start",
        }
    return {"transcript": None, "method": f"cwd folder, ambiguous ({len(candidates)} candidates)"}


def session_map(root=None):
    mapped = []
    for entry in live_sessions():
        if not under_root(entry["cwd"], root):
            continue
        resolved = resolve_transcript(entry)
        mapped.append({**entry, **read_identity(entry["pid"]), **resolved})
    return mapped


def command_map(args):
    mapped = session_map(args.root)
    if args.json:
        print(json.dumps(mapped, indent=2))
        return 0 if all(m["transcript"] for m in mapped) else 1
    for m in mapped:
        print(f"{m['pid']}\t{m['session_id']}\t{m['transcript']}\t{m['label'] or m['name']}\t{m['method']}")
    return 0 if mapped and all(m["transcript"] for m in mapped) else 1


def build_parser():
    parser = argparse.ArgumentParser(description="Session visualization watcher")
    sub = parser.add_subparsers(dest="command", required=True)
    map_parser = sub.add_parser("map", help="print pid, session id, and transcript path for live sessions")
    map_parser.add_argument("--root", help="only sessions whose cwd is under this path")
    map_parser.add_argument("--json", action="store_true", help="print the map as JSON")
    map_parser.set_defaults(func=command_map)
    return parser


def main():
    args = build_parser().parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
