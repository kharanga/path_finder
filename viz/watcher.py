import argparse
import copy
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
SOCKET_PREFIX = "uds:/tmp/cc-socks/"
PEER_MESSAGE_PREFIX = "<cross-session-message"
IDLE_NOTICE_PREFIX = "[Cross-session idle notice]"
SENDER_OWNED_MESSAGE_FIELDS = ("pending_key", "tool_use_id", "from_pid", "to", "summary", "body", "notify_when_idle", "sent_at")


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


def pid_from_socket(address):
    if not isinstance(address, str) or not address.startswith(SOCKET_PREFIX) or not address.endswith(".sock"):
        return None
    pid_text = address[len(SOCKET_PREFIX):-len(".sock")]
    return int(pid_text) if pid_text.isdigit() else None


def bare_name(target):
    if not isinstance(target, str):
        return None
    return re.sub(r"\s*\[[0-9a-f]+\]$", "", target.strip())


def first_quoted(text):
    match = re.search(r'"([^"]+)"', text or "")
    return match.group(1) if match else None


def content_text(message):
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")
    return ""


def tool_result_blocks(entry):
    content = entry.get("message", {}).get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict) and block.get("type") == "tool_result"]


def send_result_from(entry, block):
    result = entry.get("toolUseResult")
    if isinstance(result, dict) and "success" in result:
        return result
    text = block.get("content")
    if isinstance(text, list):
        text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
    try:
        parsed = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and "success" in parsed:
        return parsed
    return {"success": not block.get("is_error", False), "message": text if isinstance(text, str) else ""}


class StateModel:
    def __init__(self):
        self.sessions = {}
        self.messages = {}
        self.message_key_by_tool_use = {}
        self.pid_by_name = {}
        self.unmatched_enqueues = {}

    def register_session(self, row):
        pid = row["pid"]
        session = self.sessions.get(pid) or {
            "pid": pid,
            "status": "IDLE",
            "inbox": 0,
            "last_text": None,
            "watching": [],
            "last_seen_at": None,
        }
        for field in ("session_id", "name", "role", "label", "cwd", "transcript"):
            if row.get(field) is not None:
                session[field] = row[field]
        session.setdefault("name", None)
        session.setdefault("role", None)
        session.setdefault("label", None)
        session.setdefault("session_id", None)
        session.setdefault("cwd", None)
        session["socket"] = socket_address(pid)
        if session["name"]:
            self.pid_by_name[session["name"]] = pid
        self.sessions[pid] = session
        return session

    def session(self, pid):
        return self.sessions.get(pid) or self.register_session({"pid": pid})

    def resolve_target(self, target):
        pid = pid_from_socket(target)
        if pid is not None:
            return pid
        return self.pid_by_name.get(bare_name(target))

    def learn_name(self, name, pid):
        if name and pid is not None:
            self.pid_by_name[name] = pid
            if pid in self.sessions and not self.sessions[pid].get("name"):
                self.sessions[pid]["name"] = name

    def snapshot(self):
        return {
            "sessions": [self.sessions[pid] for pid in sorted(self.sessions)],
            "messages": sorted(self.messages.values(), key=lambda m: (m.get("sent_at") or m.get("read_at") or "", m["key"])),
        }

    def apply(self, pid, entry):
        touched = {"sessions": set(), "messages": set()}
        handler = {
            "assistant": self.apply_assistant,
            "user": self.apply_user,
            "system": self.apply_system,
            "queue-operation": self.apply_queue_operation,
            "agent-name": self.apply_agent_name,
        }.get(entry.get("type"))
        if handler is None:
            return []
        handler(pid, entry, touched)
        timestamp = entry.get("timestamp")
        for session_pid in self.sessions:
            if session_pid in touched["sessions"] and timestamp:
                self.sessions[session_pid]["last_seen_at"] = timestamp
        changes = [{"event": "session", "at": timestamp, **self.sessions[p]} for p in sorted(touched["sessions"]) if p in self.sessions]
        changes += [{"event": "message", "at": timestamp, **self.messages[k]} for k in touched["messages"] if k in self.messages]
        return copy.deepcopy(changes)

    def set_status(self, pid, status, touched):
        session = self.session(pid)
        if session["status"] != status:
            session["status"] = status
            touched["sessions"].add(pid)

    def new_message(self, key, **fields):
        message = {
            "key": key,
            "pending_key": key,
            "msg_id": None,
            "tool_use_id": None,
            "kind": "message",
            "from_pid": None,
            "to": None,
            "to_pid": None,
            "summary": None,
            "body": None,
            "stage": "PENDING",
            "notify_when_idle": False,
            "reason": None,
            "sent_at": None,
            "accepted_at": None,
            "enqueued_at": None,
            "read_at": None,
        }
        message.update(fields)
        self.messages[key] = message
        return message

    def apply_agent_name(self, pid, entry, touched):
        name = entry.get("agentName")
        if not name:
            return
        session = self.session(pid)
        self.learn_name(name, pid)
        if session["name"] != name:
            session["name"] = name
            touched["sessions"].add(pid)

    def apply_assistant(self, pid, entry, touched):
        self.set_status(pid, "WORKING", touched)
        content = entry.get("message", {}).get("content")
        if not isinstance(content, list):
            return
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "SendMessage":
                self.apply_send(pid, entry, block, touched)

    def apply_send(self, pid, entry, block, touched):
        raw_input = block.get("input") or {}
        wire = (entry.get("wireToolInputs") or {}).get(block.get("id")) or {}
        target = raw_input.get("to") or wire.get("to")
        summary = raw_input.get("summary") or wire.get("summary")
        body = raw_input.get("message") or wire.get("message")
        notify = bool(raw_input.get("notify_when_idle") or wire.get("notify_when_idle"))
        key = f"pending:{block.get('id')}"
        message = self.new_message(
            key,
            tool_use_id=block.get("id"),
            from_pid=pid,
            to=target,
            to_pid=self.resolve_target(target),
            summary=summary,
            body=body,
            notify_when_idle=notify,
            sent_at=entry.get("timestamp"),
        )
        self.message_key_by_tool_use[block.get("id")] = key
        session = self.session(pid)
        if summary or body:
            session["last_text"] = summary or body
        if notify:
            watched = message["to_pid"] if message["to_pid"] is not None else bare_name(target)
            if watched not in session["watching"]:
                session["watching"].append(watched)
        touched["sessions"].add(pid)
        touched["messages"].add(key)

    def apply_user(self, pid, entry, touched):
        origin = entry.get("origin") or {}
        if origin.get("kind") == "peer":
            self.apply_peer_delivery(pid, entry, origin, touched)
            return
        text = content_text(entry.get("message", {}))
        if entry.get("turnOrigin") == "system" and text.startswith(IDLE_NOTICE_PREFIX):
            self.apply_idle_notice(pid, entry, text, touched)
            return
        results = tool_result_blocks(entry)
        if results:
            for block in results:
                self.apply_send_result(pid, entry, block, touched)
            return
        if entry.get("turnOrigin") == "human" or entry.get("promptSource") == "typed":
            self.set_status(pid, "WORKING", touched)

    def apply_send_result(self, pid, entry, block, touched):
        key = self.message_key_by_tool_use.pop(block.get("tool_use_id"), None)
        if key is None or key not in self.messages:
            return
        message = self.messages.pop(key)
        result = send_result_from(entry, block)
        msg_id = result.get("msg_id")
        if result.get("success") and msg_id:
            existing = self.messages.get(msg_id)
            if existing:
                for field in SENDER_OWNED_MESSAGE_FIELDS:
                    if message.get(field) is not None:
                        existing[field] = message[field]
                if existing["to_pid"] is None:
                    existing["to_pid"] = message["to_pid"]
                message = existing
            message["key"] = msg_id
            message["msg_id"] = msg_id
            if message["stage"] in ("PENDING", "IN_INBOX"):
                message["stage"] = "IN_INBOX"
            message["accepted_at"] = entry.get("timestamp")
            self.messages[msg_id] = message
            self.claim_unmatched_enqueue(message)
            touched["messages"].add(msg_id)
        else:
            message["stage"] = "FAILED"
            message["reason"] = result.get("message") or block.get("content")
            message["accepted_at"] = entry.get("timestamp")
            self.messages[key] = message
            touched["messages"].add(key)

    def claim_unmatched_enqueue(self, message):
        if message["enqueued_at"] is not None or message["to_pid"] is None:
            return
        pending = self.unmatched_enqueues.get((message["from_pid"], message["to_pid"]))
        if pending:
            message["enqueued_at"] = pending.pop(0)

    def apply_queue_operation(self, pid, entry, touched):
        operation = entry.get("operation")
        session = self.session(pid)
        content = entry.get("content") or ""
        if operation == "enqueue":
            session["inbox"] += 1
            touched["sessions"].add(pid)
            if content.startswith(PEER_MESSAGE_PREFIX):
                self.apply_peer_enqueue(pid, entry, content, touched)
        elif operation in ("dequeue", "remove"):
            session["inbox"] = max(0, session["inbox"] - 1)
            touched["sessions"].add(pid)

    def apply_peer_enqueue(self, pid, entry, content, touched):
        from_match = re.search(r'from="([^"]+)"', content)
        name_match = re.search(r'from-name="([^"]+)"', content)
        from_pid = pid_from_socket(from_match.group(1)) if from_match else None
        if name_match:
            self.learn_name(name_match.group(1), from_pid)
        if from_pid is None:
            return
        candidates = [
            m for m in self.messages.values()
            if m["kind"] == "message" and m["from_pid"] == from_pid and m["enqueued_at"] is None
            and m["stage"] in ("PENDING", "IN_INBOX") and m["to_pid"] in (pid, None)
        ]
        if candidates:
            message = min(candidates, key=lambda m: m["sent_at"] or "")
            message["enqueued_at"] = entry.get("timestamp")
            message["to_pid"] = pid
            touched["messages"].add(message["key"])
        else:
            self.unmatched_enqueues.setdefault((from_pid, pid), []).append(entry.get("timestamp"))

    def apply_peer_delivery(self, pid, entry, origin, touched):
        from_pid = origin.get("verifiedPeerPid") or pid_from_socket(origin.get("from"))
        self.learn_name(origin.get("name"), from_pid)
        msg_id = origin.get("msg_id") or f"peer:{entry.get('uuid')}"
        message = self.messages.get(msg_id)
        if message is None:
            message = self.new_message(msg_id, msg_id=msg_id, from_pid=from_pid)
        message["to_pid"] = pid
        if message["from_pid"] is None:
            message["from_pid"] = from_pid
        if message["body"] is None:
            message["body"] = origin.get("body")
        message["stage"] = "READ"
        message["read_at"] = entry.get("timestamp")
        self.claim_unmatched_enqueue(message)
        session = self.session(pid)
        session["last_text"] = origin.get("body") or session["last_text"]
        session["status"] = "WORKING"
        touched["sessions"].add(pid)
        touched["messages"].add(msg_id)

    def apply_idle_notice(self, pid, entry, text, touched):
        watched_name = first_quoted(text)
        watched_pid = self.pid_by_name.get(watched_name)
        key = f"idle:{entry.get('uuid')}"
        self.new_message(
            key,
            msg_id=key,
            kind="idle_notice",
            from_pid=watched_pid,
            to=watched_name,
            to_pid=pid,
            summary=f"{watched_name} is idle",
            body=text,
            stage="READ",
            sent_at=entry.get("timestamp"),
            read_at=entry.get("timestamp"),
        )
        session = self.session(pid)
        session["watching"] = [w for w in session["watching"] if w not in (watched_pid, watched_name)]
        session["status"] = "WORKING"
        touched["sessions"].add(pid)
        touched["messages"].add(key)

    def apply_system(self, pid, entry, touched):
        if entry.get("subtype") == "turn_duration":
            self.set_status(pid, "IDLE", touched)


def parse_fixture_argument(text):
    pid_text, _, path = text.partition("=")
    if not pid_text.isdigit() or not path:
        raise argparse.ArgumentTypeError(f"expected PID=PATH, got {text!r}")
    return int(pid_text), path


def command_state(args):
    model = StateModel()
    known = {row["pid"]: row for row in session_map()}
    for pid, _path in args.fixtures:
        model.register_session(known.get(pid, {"pid": pid}))
    changes = []
    for pid, path in args.fixtures:
        tailer = TranscriptTailer(path)
        for entry in tailer.poll():
            changes += model.apply(pid, entry)
    if args.events:
        for change in changes:
            print(json.dumps(change))
    else:
        print(json.dumps(model.snapshot(), indent=2))
    return 0


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
    state_parser = sub.add_parser("state", help="feed transcript files through the state model and print the snapshot")
    state_parser.add_argument("fixtures", nargs="+", type=parse_fixture_argument, metavar="PID=PATH", help="transcript file for the session with this PID, fed whole in the given order")
    state_parser.add_argument("--events", action="store_true", help="print the change stream instead of the snapshot")
    state_parser.set_defaults(func=command_state)
    return parser


def main():
    args = build_parser().parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
