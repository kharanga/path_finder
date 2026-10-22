import ast
import shutil
import subprocess
import sys

from conftest import DISCOVER_SCRIPT

SIBLING_FUNCTIONS = {
    "paths": ("checkout_holding", "data_dir", "now_iso"),
    "processes": ("pid_is_alive", "parent_and_command", "find_claude_ancestor_pid"),
    "registry": ("socket_address", "read_registry_entry", "live_sessions", "under_root", "own_session"),
    "identity": ("identity_path", "read_identity", "write_identity", "drop_identities_of_dead_sessions", "with_identity", "is_identified",
                 "directory_entries", "lock_directory", "write_directory", "rebuild_directory"),
}
PATH_CONSTANTS = ("SESSIONS_DIR", "SCRIPT_PATH", "HOME_ENV_VAR", "DISCOVERY_DIR", "DIRECTORY_PATH", "IDENTITY_DIR")
ENTRY_FUNCTIONS = {"bound_to_this_namespace", "re_export", "command_identify", "command_self", "command_list", "command_done", "build_parser", "main"}


def top_level_statements(path):
    return ast.parse(path.read_text(encoding="utf-8")).body


def function_names(statements):
    return {node.name for node in statements if isinstance(node, ast.FunctionDef)}


def imported_module_names(statements):
    names = []
    for node in statements:
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module)
    return names


def test_each_sibling_holds_exactly_the_functions_the_spec_assigns_and_the_entry_stays_thin():
    for module_name, names in SIBLING_FUNCTIONS.items():
        assert function_names(top_level_statements(DISCOVER_SCRIPT.parent / f"{module_name}.py")) == set(names), module_name
    assert function_names(top_level_statements(DISCOVER_SCRIPT)) == ENTRY_FUNCTIONS
    assert len(DISCOVER_SCRIPT.read_text(encoding="utf-8").splitlines()) < 150
    assert not (DISCOVER_SCRIPT.parent / "__init__.py").exists()


def test_entry_puts_its_own_folder_first_on_sys_path_before_importing_the_siblings():
    statements = top_level_statements(DISCOVER_SCRIPT)
    source_lines = [ast.get_source_segment(DISCOVER_SCRIPT.read_text(encoding="utf-8"), node) for node in statements]
    insert_index = next(index for index, line in enumerate(source_lines) if "sys.path.insert(0, OWN_FOLDER)" in line)
    first_sibling_import = next(index for index, node in enumerate(statements) if isinstance(node, ast.Import) and node.names[0].name in SIBLING_FUNCTIONS)
    assert insert_index < first_sibling_import
    assert set(imported_module_names(statements)) >= set(SIBLING_FUNCTIONS)


def test_re_exported_functions_keep_the_sibling_code_but_run_in_the_entry_namespace(discover):
    for module_name, names in SIBLING_FUNCTIONS.items():
        sibling = getattr(discover, module_name)
        for name in names:
            exported = getattr(discover, name)
            assert exported.__code__ is getattr(sibling, name).__code__, name
            assert exported.__defaults__ == getattr(sibling, name).__defaults__, name
            assert exported.__globals__ is vars(discover), name
    for name in PATH_CONSTANTS:
        assert hasattr(discover, name), name


def test_patching_the_entry_module_redirects_the_re_exported_functions_and_their_callees(discover, write_registry_entry, live_pid, tmp_path):
    assert discover.identity_path(7) == discover.IDENTITY_DIR / "7.json" == tmp_path / "discovery" / "identity" / "7.json"
    assert discover.identity.identity_path(7) == discover.identity.IDENTITY_DIR / "7.json" != discover.identity_path(7)
    write_registry_entry(live_pid, "probe", str(tmp_path))
    entries = discover.rebuild_directory()
    assert [entry["pid"] for entry in entries] == [live_pid]
    assert discover.DIRECTORY_PATH.is_file() and discover.IDENTITY_DIR.is_dir()


def test_a_copy_of_the_five_files_runs_from_another_cwd_in_isolated_mode_and_writes_no_bytecode(tmp_path):
    folder = tmp_path / "copy"
    folder.mkdir()
    for module in DISCOVER_SCRIPT.parent.glob("*.py"):
        shutil.copy(module, folder / module.name)
    helped = subprocess.run([sys.executable, "-I", str(folder / "discover.py"), "--help"], cwd="/", capture_output=True, text=True)
    assert helped.returncode == 0 and helped.stdout.startswith("usage: discover.py [-h] {identify,self,list,done}")
    assert sorted(path.name for path in folder.iterdir()) == ["discover.py", "identity.py", "paths.py", "processes.py", "registry.py"]
