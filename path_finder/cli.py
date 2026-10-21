import argparse
import os
import runpy
import sys
from pathlib import Path

from path_finder.repo import VENDOR_DIR, RepoNotFound, data_dir_description, discover_script, find_repo, vendored_copies_present, watcher_script
from path_finder.window import open_window

DISCOVER_COMMANDS = ("identify", "self", "list", "done")
WATCHER_COMMANDS = ("serve", "state", "replay", "map", "tail")
COMMANDS_WITH_ROOT = ("list", "done", "serve", "map")
DEFAULT_PORT = 4780
DEFAULT_PAGE = "web"


def find_code_folder():
    try:
        return find_repo()
    except RepoNotFound:
        if vendored_copies_present():
            return VENDOR_DIR
        raise


def has_root_flag(arguments):
    return any(argument == "--root" or argument.startswith("--root=") for argument in arguments)


def with_default_root(command, arguments):
    if command in COMMANDS_WITH_ROOT and not has_root_flag(arguments):
        return [*arguments, "--root", os.getcwd()]
    return list(arguments)


def run_script_in_place(script, command, arguments):
    sys.argv = [str(script), command, *arguments]
    runpy.run_path(str(script), run_name="__main__")
    return 0


def usage():
    return "\n".join([
        "usage: path-finder <command> [arguments]",
        "",
        "discovery:  " + "  ".join(DISCOVER_COMMANDS),
        "watcher:    " + "  ".join(WATCHER_COMMANDS),
        "window:     window [--port 4780] [--page web] [--root DIR]",
        "",
        "Every command runs the checkout's discovery/discover.py or viz/watcher.py in place,",
        "or the copies vendored in this package when no checkout is found.",
        "--root defaults to the current working directory for list, done, map, serve, and window.",
        "",
        data_dir_description(),
    ])


def parse_window_arguments(arguments):
    parser = argparse.ArgumentParser(prog="path-finder window", description="open the page in a small app-mode browser window")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--page", default=DEFAULT_PAGE, help="page path on the watcher, for example web or index")
    parser.add_argument("--root", default=os.getcwd(), help="passed to serve when the watcher has to be started")
    return parser.parse_args(arguments)


def dispatch(command, arguments):
    repo = find_code_folder()
    if command in DISCOVER_COMMANDS:
        return run_script_in_place(discover_script(repo), command, with_default_root(command, arguments))
    if command in WATCHER_COMMANDS:
        return run_script_in_place(watcher_script(repo), command, with_default_root(command, arguments))
    if command == "window":
        window = parse_window_arguments(arguments)
        return open_window(repo, window.port, window.page, Path(window.root).resolve())
    print(usage(), file=sys.stderr)
    print(f"\npath-finder: unknown command {command!r}", file=sys.stderr)
    return 2


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in ("-h", "--help"):
        print(usage())
        return 0
    try:
        return dispatch(arguments[0], arguments[1:])
    except RepoNotFound as error:
        print(f"path-finder: {error}", file=sys.stderr)
        return 1
    except SystemExit as exit_request:
        code = exit_request.code
        return 0 if code is None else code if isinstance(code, int) else 1


if __name__ == "__main__":
    sys.exit(main())
