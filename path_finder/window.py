import http.client
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from path_finder.repo import watcher_script

WINDOW_SIZE = "380,720"
SERVER_START_TIMEOUT_S = 8.0
PORT_TRIES = 20

MAC_APP_BINARIES = (
    "Google Chrome.app/Contents/MacOS/Google Chrome",
    "Chromium.app/Contents/MacOS/Chromium",
    "Brave Browser.app/Contents/MacOS/Brave Browser",
    "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)
COMMAND_LINE_BINARIES = (
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "brave-browser", "brave", "microsoft-edge", "microsoft-edge-stable",
)


def page_url(port, page):
    path = "" if page in ("", "index", "index.html", "/") else page.lstrip("/")
    return f"http://127.0.0.1:{port}/{path}"


def read_state(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/state", timeout=1) as response:
            return json.load(response)
    except urllib.error.HTTPError:
        return {}
    except (urllib.error.URLError, OSError):
        return None
    except (http.client.HTTPException, ValueError):
        return {}


def server_answers(port):
    return read_state(port) is not None


def served_root(state):
    root = state.get("root") if isinstance(state, dict) else None
    return Path(root).resolve() if root else None


def choose_port(first_port, root, tries=PORT_TRIES):
    last_port = first_port + tries - 1
    first_silent_port = None
    for port in range(first_port, last_port + 1):
        state = read_state(port)
        if state is None:
            if first_silent_port is None:
                first_silent_port = port
        elif served_root(state) == Path(root).resolve():
            return port, True
    if first_silent_port is None:
        raise RuntimeError(f"no watcher for {root} and no free port between {first_port} and {last_port}")
    return first_silent_port, False


def server_log_path(port):
    return Path(tempfile.gettempdir()) / f"path-finder-serve-{port}.log"


def start_server_in_background(repo, port, root):
    log_path = server_log_path(port)
    with open(log_path, "a") as log:
        process = subprocess.Popen(
            [sys.executable, str(watcher_script(repo)), "serve", "--port", str(port), "--root", str(root)],
            stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True, cwd=str(repo),
        )
    deadline = time.monotonic() + SERVER_START_TIMEOUT_S
    while time.monotonic() < deadline:
        if server_answers(port):
            return process, log_path
        if process.poll() is not None:
            break
        time.sleep(0.1)
    raise RuntimeError(f"the watcher did not answer on port {port} within {SERVER_START_TIMEOUT_S:.0f} s, see {log_path}")


def app_mode_browser():
    if platform.system() == "Darwin":
        for applications in (Path("/Applications"), Path.home() / "Applications"):
            for relative in MAC_APP_BINARIES:
                binary = applications / relative
                if binary.is_file() and os.access(binary, os.X_OK):
                    return str(binary)
    for name in COMMAND_LINE_BINARIES:
        found = shutil.which(name)
        if found:
            return found
    return None


def open_app_window(url):
    browser = app_mode_browser()
    if browser is None:
        webbrowser.open(url)
        print(f"no Chrome, Chromium, Brave, or Edge found for an app-mode window; opened {url} in the default browser")
        return False
    subprocess.Popen(
        [browser, f"--app={url}", f"--window-size={WINDOW_SIZE}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True,
    )
    print(f"opened {url} in an app-mode window ({WINDOW_SIZE}) with {Path(browser).name}")
    return True


def open_window(repo, first_port, page, root):
    port, reused = choose_port(first_port, root)
    if reused:
        print(f"watcher for {root} already answering on port {port}")
    else:
        process, log_path = start_server_in_background(repo, port, root)
        print(f"started watcher pid {process.pid} for {root} on port {port}, log {log_path}")
    open_app_window(page_url(port, page))
    return 0
