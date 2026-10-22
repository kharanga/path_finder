import os
import subprocess


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
