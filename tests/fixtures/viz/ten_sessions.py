import json
from pathlib import Path

NAMES = ["manager", "viz-builder", "validator", "discovery-builder", "fake manager", "fake builder", "listings-e6", "listings-bc", "tag-analyzer", "semantic-scores"]
PIDS = {name: 900 + index for index, name in enumerate(NAMES)}
BASE = "2026-10-20T13:00:"


def stamp(seconds):
    return f"{BASE}{seconds:06.3f}Z"


def socket_of(name):
    return f"uds:/tmp/cc-socks/{PIDS[name]}.sock"


class TenSessions:
    def __init__(self):
        self.lines = {pid: [{"type": "agent-name", "agentName": name}] for name, pid in PIDS.items()}
        self.sent = 0

    def text(self, name, seconds, body):
        self.lines[PIDS[name]].append({"type": "assistant", "timestamp": stamp(seconds), "message": {"role": "assistant", "content": [{"type": "text", "text": body}]}})

    def tool(self, name, seconds, tool_name, inputs):
        block = {"type": "tool_use", "id": f"t-{PIDS[name]}-{seconds}", "name": tool_name, "input": inputs}
        self.lines[PIDS[name]].append({"type": "assistant", "timestamp": stamp(seconds), "message": {"role": "assistant", "content": [block]}})

    def turn_end(self, name, seconds):
        self.lines[PIDS[name]].append({"type": "system", "subtype": "turn_duration", "timestamp": stamp(seconds)})

    def send(self, sender, receiver, seconds, summary, land=None, read=None, fail=None, notify=False):
        self.sent += 1
        msg_id, tool_id = f"m-{self.sent}", f"send-{self.sent}"
        body = f"{summary}\nmore text"
        block = {"type": "tool_use", "id": tool_id, "name": "SendMessage", "input": {"to": socket_of(receiver), "summary": summary, "message": body, "notify_when_idle": notify}}
        self.lines[PIDS[sender]].append({"type": "assistant", "timestamp": stamp(seconds), "message": {"role": "assistant", "content": [block]}})
        result = {"success": False, "message": fail} if fail else {"success": True, "msg_id": msg_id}
        self.lines[PIDS[sender]].append({"type": "user", "timestamp": stamp(seconds + 0.3), "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": [{"type": "text", "text": json.dumps(result)}]}]}, "toolUseResult": result})
        if fail:
            return
        if land is not None:
            content = f'<cross-session-message from="{socket_of(sender)}" from-name="{sender}" from-mode="prompting">\n{summary}'
            self.lines[PIDS[receiver]].append({"type": "queue-operation", "operation": "enqueue", "timestamp": stamp(land), "content": content})
        if read is not None:
            self.lines[PIDS[receiver]].append({"type": "queue-operation", "operation": "dequeue", "timestamp": stamp(read - 0.05)})
            origin = {"kind": "peer", "from": socket_of(sender), "verifiedPeerPid": PIDS[sender], "msg_id": msg_id, "name": sender, "body": body}
            self.lines[PIDS[receiver]].append({"type": "user", "isMeta": True, "turnOrigin": "peer", "uuid": f"u-{msg_id}", "timestamp": stamp(read), "origin": origin, "message": {"role": "user", "content": "wrapped"}})

    def write(self, out_dir):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for pid, entries in self.lines.items():
            entries.sort(key=lambda entry: entry.get("timestamp", ""))
            path = out_dir / f"{pid}.jsonl"
            path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
            fixtures.append((pid, str(path)))
        return fixtures


def ten_sessions_round():
    ten = TenSessions()
    ten.text("manager", 0.5, "Assigning the next round.")
    ten.tool("manager", 0.8, "Read", {"file_path": "handoff/viz/ready.md"})
    ten.send("manager", "viz-builder", 1.0, "V8 assigned", land=1.6, read=2.0)
    ten.tool("viz-builder", 2.5, "Bash", {"command": "python3 -m pytest tests -q", "description": "Run the suite"})
    ten.send("viz-builder", "validator", 6.5, "V7 ready", land=7.1)
    ten.send("viz-builder", "manager", 7.4, "V7 ready, handoff written", land=8.0)
    ten.turn_end("manager", 3.0)
    ten.send("manager", "discovery-builder", 11.5, "D4 assigned", land=12.1)
    ten.send("manager", "semantic-scores", 11.8, "rerun scores")
    ten.send("validator", "viz-builder", 14.0, "V6 review: PASS", land=14.6)
    ten.send("validator", "manager", 15.0, "V6 review: PASS", fail="Not sent: relay loop cut")
    ten.send("listings-e6", "listings-bc", 4.8, "rerun scores", land=5.4)
    ten.send("semantic-scores", "listings-bc", 10.2, "batch 3 written", land=10.8)
    ten.send("tag-analyzer", "listings-e6", 17.0, "tags done", land=17.6, read=19.0)
    ten.send("fake manager", "fake builder", 12.0, "second hello", land=12.5, read=13.0)
    ten.text("fake builder", 13.5, "Replied with a hi back.")
    ten.turn_end("fake builder", 13.8)
    ten.tool("listings-e6", 19.5, "Edit", {"file_path": "scores.py"})
    ten.turn_end("validator", 16.0)
    return ten


if __name__ == "__main__":
    import sys
    print(" ".join(f"--fixture {pid}={path}" for pid, path in ten_sessions_round().write(sys.argv[1])))


SIX = NAMES[:6]
LONG_DESCRIPTION = "Run the whole suite and compare the change counts against the pinned numbers for every fixture"


def six_sessions_round():
    six = TenSessions()
    for name in NAMES[6:]:
        del six.lines[PIDS[name]]
    six.text("manager", 0.5, "Assigning V11.")
    six.send("manager", "viz-builder", 1.0, "V11 assigned", land=1.6, read=2.0, notify=True)
    six.turn_end("manager", 3.0)
    six.tool("viz-builder", 2.5, "Bash", {"command": "python3 -m pytest tests -q", "description": LONG_DESCRIPTION})
    six.send("validator", "manager", 4.0, "V10 review: PASS", land=4.6)
    six.turn_end("validator", 5.0)
    six.send("fake manager", "fake builder", 6.0, "second hello", land=6.5, read=7.0)
    six.text("fake builder", 7.5, "Replied with a hi back.")
    six.turn_end("fake builder", 7.8)
    six.turn_end("fake manager", 8.0)
    six.send("manager", "discovery-builder", 1.2, "D5 assigned", land=1.8, read=2.2)
    six.turn_end("discovery-builder", 2.6)
    return six
