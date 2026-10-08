import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
VIZ_DIR = Path(__file__).resolve().parent
IDENTITY_DIR = VIZ_DIR.parent / "discovery" / "identity"
POLL_INTERVAL_S = 0.25

KEPT_ENTRY_TYPES = {
    "assistant",
    "user",
    "system",
    "queue-operation",
    "attachment",
    "agent-name",
    "custom-title",
    "ai-title",
    "permission-mode",
    "mode",
    "last-prompt",
    "summary",
}
KEPT_ATTACHMENT_TYPES = {
    "queued_command",
    "hook_success",
    "hook_non_blocking_error",
    "hook_blocking_error",
    "hook_cancelled",
}
KEPT_META_TURN_ORIGINS = {"peer", "system"}


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


def entry_is_kept(entry):
    if not isinstance(entry, dict) or entry.get("type") not in KEPT_ENTRY_TYPES:
        return False
    if entry.get("isSidechain"):
        return False
    if entry.get("isMeta") and entry.get("turnOrigin") not in KEPT_META_TURN_ORIGINS:
        return False
    if entry.get("type") == "attachment":
        attachment = entry.get("attachment")
        return isinstance(attachment, dict) and attachment.get("type") in KEPT_ATTACHMENT_TYPES
    return True


class TranscriptTailer:
    def __init__(self, path, start_at_end=False):
        self.path = Path(path)
        self.offset = self.path.stat().st_size if start_at_end and self.path.exists() else 0
        self.partial_line = b""
        self.unknown_types = set()
        self.malformed_lines = 0
        self.skipped_entries = 0

    def read_new_bytes(self):
        try:
            size = self.path.stat().st_size
        except OSError:
            return b""
        if size < self.offset:
            self.offset = 0
            self.partial_line = b""
        if size == self.offset:
            return b""
        with open(self.path, "rb") as handle:
            handle.seek(self.offset)
            chunk = handle.read(size - self.offset)
        self.offset += len(chunk)
        return chunk

    def complete_lines(self, chunk):
        data = self.partial_line + chunk
        lines = data.split(b"\n")
        self.partial_line = lines.pop()
        return [line for line in lines if line.strip()]

    def parse_line(self, line):
        try:
            entry = json.loads(line)
        except ValueError:
            self.malformed_lines += 1
            return None
        if not isinstance(entry, dict):
            self.malformed_lines += 1
            return None
        entry_type = entry.get("type")
        if entry_type not in KEPT_ENTRY_TYPES:
            self.unknown_types.add(entry_type)
            return None
        if not entry_is_kept(entry):
            self.skipped_entries += 1
            return None
        return entry

    def poll(self):
        entries = []
        for line in self.complete_lines(self.read_new_bytes()):
            entry = self.parse_line(line)
            if entry is not None:
                entries.append(entry)
        return entries


def command_tail(args):
    tailer = TranscriptTailer(args.transcript, start_at_end=args.from_end)
    while True:
        for entry in tailer.poll():
            print(json.dumps(entry), flush=True)
        if not args.follow:
            break
        time.sleep(POLL_INTERVAL_S)
    if args.stats:
        stats = {
            "offset": tailer.offset,
            "buffered_bytes": len(tailer.partial_line),
            "unknown_types": sorted(t if t is not None else "null" for t in tailer.unknown_types),
            "malformed_lines": tailer.malformed_lines,
            "skipped_entries": tailer.skipped_entries,
        }
        print(json.dumps(stats), file=sys.stderr)
    return 0


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
    else:
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
    tail_parser = sub.add_parser("tail", help="print kept transcript entries as JSON lines")
    tail_parser.add_argument("transcript", help="path to a transcript .jsonl file")
    tail_parser.add_argument("--follow", action="store_true", help="keep polling every 250 ms")
    tail_parser.add_argument("--from-end", action="store_true", help="start at the current end of the file")
    tail_parser.add_argument("--stats", action="store_true", help="print offset, buffer, and skip counts to stderr at exit")
    tail_parser.set_defaults(func=command_tail)
    return parser


def main():
    args = build_parser().parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
