import json
import os
import select
import subprocess
import sys
import time

from conftest import WATCHER_SCRIPT


def read_line_within(stream, seconds):
    deadline = time.monotonic() + seconds
    collected = b""
    while time.monotonic() < deadline and b"\n" not in collected:
        ready, _, _ = select.select([stream], [], [], max(0.0, deadline - time.monotonic()))
        if ready:
            collected += os.read(stream.fileno(), 65536)
    return collected


def test_follow_prints_appended_entry_within_a_second(tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({"type": "assistant"}) + "\n")
    process = subprocess.Popen(
        [sys.executable, "-I", str(WATCHER_SCRIPT), "tail", str(transcript), "--follow", "--from-end"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        time.sleep(0.5)
        with open(transcript, "a") as handle:
            handle.write(json.dumps({"type": "user", "isMeta": True, "turnOrigin": "peer", "origin": {"msg_id": "m1"}}) + "\n")
        output = read_line_within(process.stdout, 1.0)
        assert json.loads(output.decode().strip())["origin"]["msg_id"] == "m1"
    finally:
        process.terminate()
        process.wait()
