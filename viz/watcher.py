import argparse
import copy
import json
import os
import queue
import re
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
VIZ_DIR = Path(__file__).resolve().parent
DISCOVERY_DIR = VIZ_DIR.parent / "discovery"
IDENTITY_DIR = DISCOVERY_DIR / "identity"
STATIC_DIRS = (VIZ_DIR,)
PAGE_ROUTES = {"/web": "/web.html"}
EVENT_LOG_PATH = VIZ_DIR / "events.jsonl"
UI_PORT = 4780
POLL_INTERVAL_S = 0.25
SSE_KEEPALIVE_S = 15

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
REGISTRY_SOURCE = "registry"
SPEC_SOURCE = "spec"
SPEC_PATH = VIZ_DIR.parent / "SPEC.md"
TASK_LINE = re.compile(r"^- \[(?P<mark>[ x~])\] (?P<id>[A-Za-z]+\d+): (?P<text>.+)$")
TASK_STATES = {" ": "todo", "x": "done", "~": "in_progress"}
TASK_OWNERS = {"D": "discovery-builder", "V": "viz-builder"}
TASK_AREAS = {"D": "Discovery", "V": "Visualization"}
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


ACTIVITY_MAX = 140
TOOL_TARGET_FIELDS = ("file_path", "path", "url", "skill", "query", "pattern", "to", "command", "prompt")


def first_line(text, limit=ACTIVITY_MAX):
    line = next((part.strip() for part in str(text or "").splitlines() if part.strip()), "")
    return line if len(line) <= limit else line[:limit - 1] + "…"


def describe_tool_use(block, entry):
    name = block.get("name") or "tool"
    raw = dict((entry.get("wireToolInputs") or {}).get(block.get("id")) or {})
    raw.update({k: v for k, v in (block.get("input") or {}).items() if v not in (None, "")})
    headline = raw.get("description") or raw.get("summary")
    if headline:
        return f"{name}: {first_line(headline)}"
    target = next((raw[field] for field in TOOL_TARGET_FIELDS if raw.get(field)), None)
    return f"{name} {first_line(target)}" if target else name


def entry_source(entry):
    kind = entry.get("type")
    if kind == "assistant":
        content = entry.get("message", {}).get("content")
        blocks = content if isinstance(content, list) else []
        if any(isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "SendMessage" for block in blocks):
            return "assistant → tool_use SendMessage"
        return "assistant"
    if kind == "user":
        if (entry.get("origin") or {}).get("kind") == "peer":
            return "user · origin.kind = peer"
        if entry.get("turnOrigin") == "system" and content_text(entry.get("message", {})).startswith(IDLE_NOTICE_PREFIX):
            return "user · cross-session idle notice"
        results = tool_result_blocks(entry)
        if results:
            succeeded = all(send_result_from(entry, block).get("success") for block in results)
            return "toolUseResult.success" if succeeded else "toolUseResult.error"
        return "user"
    if kind == "system":
        return f"system · {entry.get('subtype')}"
    if kind == "queue-operation":
        return f"queue-operation · {entry.get('operation')}"
    return str(kind)


class StateModel:
    def __init__(self):
        self.sessions = {}
        self.messages = {}
        self.message_key_by_tool_use = {}
        self.pid_by_name = {}
        self.unmatched_enqueues = {}
        self.latest_source_by_pid = {}
        self.source_sequence = 0

    def register_session(self, row):
        pid = row["pid"]
        session = self.sessions.get(pid) or {
            "pid": pid,
            "status": "IDLE",
            "inbox": 0,
            "last_text": None,
            "watching": [],
            "last_seen_at": None,
            "activity": None,
            "activity_at": None,
            "idle_since": None,
            "last_assistant_text": None,
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
            "sources": [self.latest_source_by_pid[pid] for pid in sorted(self.latest_source_by_pid)],
        }

    def note_source(self, pid, timestamp, source):
        self.source_sequence += 1
        self.latest_source_by_pid[pid] = {"pid": pid, "at": timestamp, "source": source, "seq": self.source_sequence}

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
        source = entry_source(entry)
        changes = [{"event": "session", "at": timestamp, "source": source, "source_pid": pid, **self.sessions[p]} for p in sorted(touched["sessions"]) if p in self.sessions]
        changes += [{"event": "message", "at": timestamp, "source": source, "source_pid": pid, **self.messages[k]} for k in touched["messages"] if k in self.messages]
        if changes:
            self.note_source(pid, timestamp, source)
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
        name_changed = session["name"] != name
        session["name"] = name
        self.learn_name(name, pid)
        if name_changed:
            touched["sessions"].add(pid)

    def apply_assistant(self, pid, entry, touched):
        self.set_status(pid, "WORKING", touched)
        content = entry.get("message", {}).get("content")
        if not isinstance(content, list):
            return
        blocks = [block for block in content if isinstance(block, dict)]
        texts = [first_line(block.get("text")) for block in blocks if block.get("type") == "text" and first_line(block.get("text"))]
        tool_uses = [block for block in blocks if block.get("type") == "tool_use"]
        session = self.session(pid)
        if texts:
            session["last_assistant_text"] = texts[-1]
        activity = describe_tool_use(tool_uses[-1], entry) if tool_uses else (texts[-1] if texts else None)
        self.set_activity(pid, activity, entry.get("timestamp"), touched)
        for block in tool_uses:
            if block.get("name") == "SendMessage":
                self.apply_send(pid, entry, block, touched)

    def set_activity(self, pid, activity, timestamp, touched):
        session = self.session(pid)
        if activity and activity != session["activity"]:
            session["activity"] = activity
            session["activity_at"] = timestamp
            touched["sessions"].add(pid)

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
        self.claim_unmatched_enqueue(message)
        if message["enqueued_at"] is not None:
            message["stage"] = "IN_INBOX"
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
            if message["stage"] == "PENDING":
                message["stage"] = "IN_INBOX"
            touched["messages"].add(message["key"])
        else:
            self.unmatched_enqueues.setdefault((from_pid, pid), []).append(entry.get("timestamp"))

    def apply_peer_delivery(self, pid, entry, origin, touched):
        from_pid = origin.get("verifiedPeerPid") or pid_from_socket(origin.get("from"))
        self.learn_name(origin.get("name"), from_pid)
        msg_id = origin.get("msg_id") or f"peer:{entry.get('uuid')}"
        message = self.messages.get(msg_id)
        if message is None:
            message = self.adopt_pending_send(from_pid, pid, msg_id) or self.new_message(msg_id, msg_id=msg_id, from_pid=from_pid)
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

    def adopt_pending_send(self, from_pid, to_pid, msg_id):
        candidates = [
            m for m in self.messages.values()
            if m["msg_id"] is None and m["kind"] == "message" and m["from_pid"] == from_pid
            and m["stage"] in ("PENDING", "IN_INBOX") and m["to_pid"] in (to_pid, None)
        ]
        if not candidates:
            return None
        message = min(candidates, key=lambda m: m["sent_at"] or "")
        del self.messages[message["key"]]
        message["key"] = msg_id
        message["msg_id"] = msg_id
        self.messages[msg_id] = message
        if message["tool_use_id"] in self.message_key_by_tool_use:
            self.message_key_by_tool_use[message["tool_use_id"]] = msg_id
        return message

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
            session = self.session(pid)
            if session["idle_since"] != entry.get("timestamp"):
                session["idle_since"] = entry.get("timestamp")
                touched["sessions"].add(pid)
            self.set_activity(pid, session["last_assistant_text"], entry.get("timestamp"), touched)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class EventBroadcaster:
    def __init__(self):
        self.subscribers = set()
        self.lock = threading.Lock()

    def subscribe(self):
        subscriber = queue.Queue()
        with self.lock:
            self.subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber):
        with self.lock:
            self.subscribers.discard(subscriber)

    def publish(self, change):
        with self.lock:
            subscribers = list(self.subscribers)
        for subscriber in subscribers:
            subscriber.put(change)


def identified_live_sessions(root):
    rows = []
    for entry in live_sessions():
        if under_root(entry["cwd"], root):
            rows.append({**entry, **read_identity(entry["pid"])})
    return rows


def task_title(text):
    stripped = text.strip()
    match = re.search(r"\.(\s|$)", stripped)
    return (stripped[:match.start()] if match else stripped).strip()


def task_area(task_id):
    series = task_id[0].upper()
    return TASK_AREAS.get(series, series)


def parse_spec_tasks(text):
    tasks = []
    in_tasks = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_tasks = line.strip() == "## Tasks"
            continue
        if not in_tasks:
            continue
        match = TASK_LINE.match(line.rstrip())
        if not match:
            continue
        task_id = match.group("id")
        tasks.append({
            "id": task_id,
            "state": TASK_STATES[match.group("mark")],
            "title": task_title(match.group("text")),
            "text": match.group("text").strip(),
            "owner": TASK_OWNERS.get(task_id[0].upper()),
            "area": task_area(task_id),
        })
    return tasks


def task_counts(tasks):
    return {state: sum(1 for task in tasks if task["state"] == state) for state in ("done", "in_progress", "todo")}


class SpecTasks:
    def __init__(self, path):
        self.path = Path(path) if path else None
        self.signature = None
        self.tasks = []

    def refresh(self):
        if self.path is None:
            return False
        try:
            stat = self.path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            signature = None
        if signature == self.signature:
            return False
        self.signature = signature
        try:
            tasks = parse_spec_tasks(self.path.read_text(encoding="utf-8"))
        except OSError:
            tasks = []
        changed = tasks != self.tasks
        self.tasks = tasks
        return changed

    def payload(self):
        return {"tasks": copy.deepcopy(self.tasks), "task_counts": task_counts(self.tasks), "spec_path": str(self.path) if self.path else None}


class Watcher:
    def __init__(self, root=None, fixtures=None, log_path=None, spec_path=SPEC_PATH):
        self.root = root
        self.fixtures = fixtures
        self.spec = SpecTasks(spec_path)
        self.model = StateModel()
        self.tailers = {}
        self.last_timestamp_by_pid = {}
        self.lock = threading.RLock()
        self.broadcaster = EventBroadcaster()
        self.stop_event = threading.Event()
        self.log_path = Path(log_path) if log_path else None
        self.log_handle = None

    def emit(self, change):
        if self.log_path:
            if self.log_handle is None:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                self.log_handle = open(self.log_path, "a", encoding="utf-8")
            self.log_handle.write(json.dumps(change) + "\n")
            self.log_handle.flush()
        self.broadcaster.publish(change)

    def close(self):
        self.stop_event.set()
        if self.log_handle:
            self.log_handle.close()
            self.log_handle = None

    def session_rows(self):
        if self.fixtures:
            known = {row["pid"]: row for row in identified_live_sessions(None)}
            return [{**known.get(pid, {"pid": pid}), "transcript": path} for pid, path in self.fixtures]
        rows = []
        for row in identified_live_sessions(self.root):
            if row["pid"] in self.tailers:
                rows.append(row)
            else:
                rows.append({**row, **resolve_transcript(row)})
        return rows

    def refresh_sessions(self):
        current = {}
        for row in self.session_rows():
            if row["pid"] in self.tailers or row.get("transcript"):
                current[row["pid"]] = row
        for pid, row in current.items():
            before = copy.deepcopy(self.model.sessions.get(pid))
            session = self.model.register_session(row)
            if pid not in self.tailers:
                self.tailers[pid] = TranscriptTailer(row["transcript"])
            if before != session:
                registered_at = now_iso()
                self.model.note_source(pid, registered_at, REGISTRY_SOURCE)
                self.emit({"event": "session", "at": registered_at, "source": REGISTRY_SOURCE, "source_pid": pid, **copy.deepcopy(session)})
        for pid in list(self.tailers):
            if pid not in current:
                del self.tailers[pid]
                self.model.sessions.pop(pid, None)
                self.model.latest_source_by_pid.pop(pid, None)
                self.emit({"event": "session_removed", "at": now_iso(), "source": REGISTRY_SOURCE, "source_pid": pid, "pid": pid})

    def poll_once(self):
        with self.lock:
            self.refresh_sessions()
            self.refresh_tasks()
            for pid, entry in self.entries_in_time_order():
                for change in self.model.apply(pid, entry):
                    self.emit(change)

    def refresh_tasks(self):
        if self.spec.refresh():
            self.emit({"event": "tasks", "at": now_iso(), "source": SPEC_SOURCE, "source_pid": None, **self.spec.payload()})

    def entries_in_time_order(self):
        timed = []
        for file_index, (pid, tailer) in enumerate(list(self.tailers.items())):
            last_timestamp = self.last_timestamp_by_pid.get(pid, "")
            for line_index, entry in enumerate(tailer.poll()):
                last_timestamp = entry.get("timestamp") or last_timestamp
                timed.append((last_timestamp, file_index, line_index, pid, entry))
            self.last_timestamp_by_pid[pid] = last_timestamp
        timed.sort(key=lambda item: item[:3])
        return [(pid, entry) for _timestamp, _file_index, _line_index, pid, entry in timed]

    def run(self):
        while not self.stop_event.is_set():
            self.poll_once()
            self.stop_event.wait(POLL_INTERVAL_S)

    def snapshot(self):
        with self.lock:
            return {"generated_at": now_iso(), **copy.deepcopy(self.model.snapshot()), **self.spec.payload()}


class VizRequestHandler(SimpleHTTPRequestHandler):
    watcher = None
    quiet = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIRS[-1]), **kwargs)

    def log_message(self, format, *args):
        if not self.quiet:
            super().log_message(format, *args)

    def do_GET(self):
        route = urllib.parse.urlparse(self.path).path
        if route in PAGE_ROUTES:
            route = PAGE_ROUTES[route]
            self.path = route
        if route == "/state":
            self.send_state()
        elif route == "/events":
            self.send_events()
        else:
            self.directory = str(self.static_dir_for(route))
            super().do_GET()

    def static_dir_for(self, route):
        relative = route.lstrip("/") or "index.html"
        for folder in STATIC_DIRS:
            if (folder / relative).is_file():
                return folder
        return STATIC_DIRS[-1]

    def send_json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_state(self):
        self.send_json(self.watcher.snapshot())

    def send_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        subscriber = self.watcher.broadcaster.subscribe()
        try:
            self.write_sse({"event": "snapshot", **self.watcher.snapshot()})
            while True:
                try:
                    change = subscriber.get(timeout=SSE_KEEPALIVE_S)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                self.write_sse(change)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.watcher.broadcaster.unsubscribe(subscriber)

    def write_sse(self, payload):
        self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())
        self.wfile.flush()


def command_serve(args):
    watcher = Watcher(root=args.root, fixtures=args.fixture or None, log_path=None if args.no_log else args.log, spec_path=args.spec)
    handler = type("BoundVizRequestHandler", (VizRequestHandler,), {"watcher": watcher, "quiet": not args.verbose})
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError as error:
        print(f"cannot bind 127.0.0.1:{args.port}: {error}", file=sys.stderr)
        return 1
    server.daemon_threads = True
    poller = threading.Thread(target=watcher.run, name="watcher-poll", daemon=True)
    poller.start()
    print(f"http://127.0.0.1:{args.port}/  (/state, /events)", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        watcher.close()
        server.server_close()
    return 0


def entries_in_time_order(fixtures):
    timed = []
    for pid, path in fixtures:
        last_timestamp = ""
        for index, line in enumerate(open(path, "rb").read().split(b"\n")):
            if not line.strip():
                continue
            try:
                timestamp = json.loads(line).get("timestamp") or last_timestamp
            except (ValueError, AttributeError):
                timestamp = last_timestamp
            last_timestamp = timestamp
            timed.append((timestamp, index, pid, line))
    timed.sort(key=lambda item: (item[0], item[2], item[1]))
    return timed


def command_replay(args):
    outputs = {}
    for pid, _path in args.fixture:
        target = Path(args.out_dir) / f"{pid}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not args.after:
            target.write_bytes(b"")
        outputs[pid] = target
    print(" ".join(f"{pid}={path}" for pid, path in outputs.items()), flush=True)
    previous_timestamp = None
    for timestamp, _index, pid, line in entries_in_time_order(args.fixture):
        if args.after and (not timestamp or timestamp <= args.after):
            continue
        if args.until and timestamp and timestamp > args.until:
            break
        if previous_timestamp and timestamp and args.speed > 0:
            gap_s = (parse_timestamp(timestamp) - parse_timestamp(previous_timestamp)).total_seconds()
            time.sleep(max(0.0, min(gap_s / args.speed, args.max_gap)))
        with open(outputs[pid], "ab") as handle:
            handle.write(line + b"\n")
        previous_timestamp = timestamp or previous_timestamp
    return 0


def parse_timestamp(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


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
    serve_parser = sub.add_parser("serve", help="serve /state, /events, and the static page on one port")
    serve_parser.add_argument("--port", type=int, default=UI_PORT)
    serve_parser.add_argument("--root", help="only sessions whose cwd is under this path")
    serve_parser.add_argument("--fixture", action="append", type=parse_fixture_argument, metavar="PID=PATH", help="tail this file for this PID instead of the registry; repeatable")
    serve_parser.add_argument("--verbose", action="store_true", help="log every request")
    serve_parser.add_argument("--log", default=str(EVENT_LOG_PATH), help="append every change here as one JSON line")
    serve_parser.add_argument("--no-log", action="store_true", help="do not write the event log")
    serve_parser.add_argument("--spec", default=str(SPEC_PATH), help="SPEC.md to read the task list from")
    serve_parser.set_defaults(func=command_serve)
    replay_parser = sub.add_parser("replay", help="write fixture lines into fresh files in timestamp order, for serve --fixture to tail")
    replay_parser.add_argument("--fixture", action="append", required=True, type=parse_fixture_argument, metavar="PID=PATH")
    replay_parser.add_argument("--out-dir", required=True, help="folder for the replayed <pid>.jsonl files")
    replay_parser.add_argument("--speed", type=float, default=1.0, help="time scale; 0 writes everything at once")
    replay_parser.add_argument("--max-gap", type=float, default=2.0, help="longest pause between lines in seconds")
    replay_parser.add_argument("--until", help="stop before the first line whose timestamp is after this ISO time, to freeze a frame")
    replay_parser.add_argument("--after", help="append only lines after this ISO time to the existing files, to continue a frozen frame")
    replay_parser.set_defaults(func=command_replay)
    return parser


def main():
    args = build_parser().parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
