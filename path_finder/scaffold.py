import argparse
import os
from pathlib import Path

FIXED_ROLES = ("manager", "validator")
HANDOFF_KEEP_FILE = ".gitkeep"


def valid_builder_name(name):
    return bool(name) and name not in (".", "..") and "/" not in name and "\\" not in name and not name.isspace()


def unique_in_order(names):
    seen = []
    for name in names:
        if name not in seen:
            seen.append(name)
    return seen


def placeholder_paths(root, builders):
    root = Path(root)
    files = [root / "CLAUDE.md", root / "SPEC.md"]
    files += [root / ".claude" / "roles" / f"{role}.md" for role in FIXED_ROLES]
    files += [root / ".claude" / "roles" / f"{builder}.md" for builder in builders]
    folders = [root / "handoff" / builder for builder in builders]
    keep_files = [folder / HANDOFF_KEEP_FILE for folder in folders]
    return files, folders, keep_files


def create_empty_file(path):
    if path.exists():
        return "exists"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return "created"


def create_folder(path):
    if path.exists():
        return "exists"
    path.mkdir(parents=True)
    return "created"


def create_placeholders(root, builders):
    files, folders, keep_files = placeholder_paths(root, builders)
    outcomes = [(str(path.relative_to(root)), create_empty_file(path)) for path in files]
    for folder, keep_file in zip(folders, keep_files):
        outcomes.append((f"{folder.relative_to(root)}/", create_folder(folder)))
        outcomes.append((str(keep_file.relative_to(root)), create_empty_file(keep_file)))
    return outcomes


def build_parser():
    parser = argparse.ArgumentParser(
        prog="path-finder init",
        description="create the empty workspace placeholders that the setup-agent-workspace skill fills in: CLAUDE.md, SPEC.md, .claude/roles/, handoff/<builder>/",
    )
    parser.add_argument("--root", default=os.getcwd(), help="workspace root, default the current directory")
    parser.add_argument("--builder", action="append", default=[], metavar="NAME", help="a builder name (repeat for several); each gets a role file and a handoff folder")
    return parser


def run_init(arguments):
    parser = build_parser()
    options = parser.parse_args(arguments)
    builders = unique_in_order(options.builder)
    if not builders:
        parser.print_usage()
        print("path-finder init: at least one --builder NAME is required")
        return 2
    bad_names = [name for name in builders if not valid_builder_name(name)]
    if bad_names:
        parser.print_usage()
        print(f"path-finder init: a builder name must be a plain folder name, not {bad_names!r}")
        return 2
    root = Path(options.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for shown_path, outcome in create_placeholders(root, builders):
        print(f"{outcome} {shown_path}")
    return 0
