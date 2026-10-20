import json

import pytest

from conftest import FIXTURES_DIR

ROOT = "/home/user/path_finder"
FAKE_ROOT = f"{ROOT}/fake_session"


def test_read_registry_entry_from_sanitized_fixture(discover):
    entry = discover.read_registry_entry(FIXTURES_DIR / "discovery" / "registry_entry.json")
    assert entry == {
        "pid": 32813,
        "name": "fake-session-manager",
        "cwd": FAKE_ROOT,
        "socket": "uds:/tmp/cc-socks/32813.sock",
        "session_id": "ab5e0a7a-abdf-48ae-b34a-85aebcb80f95",
    }


def test_read_registry_entry_missing_file_returns_none(discover, tmp_path):
    assert discover.read_registry_entry(tmp_path / "missing.json") is None


def test_read_registry_entry_invalid_json_returns_none(discover, tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert discover.read_registry_entry(broken) is None


@pytest.mark.parametrize("entry", [{}, {"pid": "123"}, {"pid": None}, {"name": "x"}])
def test_read_registry_entry_without_integer_pid_returns_none(discover, tmp_path, entry):
    path = tmp_path / "entry.json"
    path.write_text(json.dumps(entry))
    assert discover.read_registry_entry(path) is None


def test_read_registry_entry_without_session_id_leaves_it_null(discover, tmp_path):
    path = tmp_path / "entry.json"
    path.write_text(json.dumps({"pid": 5, "name": "n", "cwd": ROOT}))
    assert discover.read_registry_entry(path)["session_id"] is None


def test_socket_address_is_derived_from_pid(discover):
    assert discover.socket_address(4242) == "uds:/tmp/cc-socks/4242.sock"


def test_pid_is_alive_for_own_process_and_dead_child(discover, live_pid, gone_pid):
    assert discover.pid_is_alive(live_pid) is True
    assert discover.pid_is_alive(gone_pid) is False


def test_under_root_accepts_descendants_and_rejects_siblings(discover):
    assert discover.under_root(FAKE_ROOT, ROOT) is True
    assert discover.under_root(ROOT, ROOT) is True
    assert discover.under_root("/home/user/path_finder_other", ROOT) is False
    assert discover.under_root("/home/user", ROOT) is False


def test_under_root_without_root_accepts_everything(discover):
    assert discover.under_root("/anywhere", None) is True
    assert discover.under_root(None, None) is True


def test_under_root_with_null_cwd_is_rejected(discover):
    assert discover.under_root(None, ROOT) is False


def test_live_sessions_drops_dead_pids_and_unreadable_entries(discover, write_registry_entry, live_pid, gone_pid):
    write_registry_entry(live_pid, "alive", ROOT)
    write_registry_entry(gone_pid, "gone", ROOT)
    (discover.SESSIONS_DIR / "junk.json").write_text("not json")
    assert [s["pid"] for s in discover.live_sessions()] == [live_pid]


def test_live_sessions_with_empty_registry(discover):
    assert discover.live_sessions() == []


def test_with_identity_reads_identified_at(discover, write_identity_file):
    write_identity_file(7, "manager")
    entry = discover.with_identity({"pid": 7, "name": "m", "cwd": ROOT})
    assert entry["role"] == "manager"
    assert entry["label"] == "manager"
    assert entry["identified_at"] == "2026-10-08T00:00:00Z"


def test_with_identity_accepts_d1_set_at_files(discover):
    discover.IDENTITY_DIR.mkdir(parents=True)
    source = FIXTURES_DIR / "discovery" / "identity_d1_set_at.json"
    (discover.IDENTITY_DIR / "32813.json").write_text(source.read_text())
    entry = discover.with_identity({"pid": 32813, "name": "m", "cwd": FAKE_ROOT})
    assert entry["role"] == "fake session manager"
    assert entry["label"] == "fake manager"
    assert entry["identified_at"] == "2026-10-07T06:09:37Z"


def test_with_identity_without_file_sets_nulls(discover):
    entry = discover.with_identity({"pid": 9, "name": "n", "cwd": ROOT})
    assert (entry["role"], entry["label"], entry["identified_at"]) == (None, None, None)
    assert discover.is_identified(entry) is False


def test_with_identity_with_corrupt_file_sets_nulls(discover):
    discover.IDENTITY_DIR.mkdir(parents=True)
    (discover.IDENTITY_DIR / "9.json").write_text("{broken")
    entry = discover.with_identity({"pid": 9, "name": "n", "cwd": ROOT})
    assert entry["role"] is None


def test_is_identified_requires_a_role(discover):
    assert discover.is_identified({"role": "x"}) is True
    assert discover.is_identified({"role": None}) is False
    assert discover.is_identified({}) is False


def test_drop_identities_of_dead_sessions_keeps_live_and_removes_rest(discover, write_identity_file):
    write_identity_file(1, "keep")
    write_identity_file(2, "drop")
    (discover.IDENTITY_DIR / "notes.json").write_text("{}")
    discover.drop_identities_of_dead_sessions({1})
    assert sorted(p.name for p in discover.IDENTITY_DIR.glob("*.json")) == ["1.json"]


def test_drop_identities_creates_missing_identity_dir(discover):
    discover.drop_identities_of_dead_sessions(set())
    assert discover.IDENTITY_DIR.is_dir()


def test_write_identity_sets_label_equal_to_role(discover):
    session = {"pid": 3, "name": "n", "cwd": ROOT, "socket": "uds:/tmp/cc-socks/3.sock", "session_id": None}
    identity = discover.write_identity(session, "viz-builder")
    assert identity["label"] == "viz-builder"
    assert identity["role"] == "viz-builder"
    assert identity["identified_at"].endswith("Z")
    assert json.loads(discover.identity_path(3).read_text()) == identity


def test_rebuild_directory_writes_sessions_json_and_prunes_identities(
    discover, write_registry_entry, write_identity_file, live_pid, gone_pid
):
    write_registry_entry(live_pid, "alive", ROOT)
    write_registry_entry(gone_pid, "gone", ROOT)
    write_identity_file(live_pid, "manager")
    write_identity_file(gone_pid, "stale")
    entries = discover.rebuild_directory()
    on_disk = json.loads(discover.DIRECTORY_PATH.read_text())
    assert on_disk["sessions"] == entries
    assert [e["pid"] for e in entries] == [live_pid]
    assert entries[0]["role"] == "manager"
    assert set(on_disk) == {"updated_at", "sessions"}
    assert not discover.identity_path(gone_pid).exists()
    assert discover.DIRECTORY_PATH.with_suffix(".json.lock").exists()
    assert not discover.DIRECTORY_PATH.with_suffix(".json.tmp").exists()


def test_rebuild_directory_includes_sessions_outside_any_root(discover, write_registry_entry, live_pid):
    write_registry_entry(live_pid, "elsewhere", "/home/user/other")
    assert [e["cwd"] for e in discover.rebuild_directory()] == ["/home/user/other"]


def test_command_identify_outside_claude_exits_1(discover, monkeypatch, capsys):
    monkeypatch.setattr(discover, "own_session", lambda: None)
    args = discover.build_parser().parse_args(["identify", "--role", "x"])
    assert discover.command_identify(args) == 1
    assert "not running inside a Claude Code session" in capsys.readouterr().err


def test_command_identify_writes_identity_and_directory(discover, monkeypatch, write_registry_entry, live_pid, capsys):
    write_registry_entry(live_pid, "me", ROOT, session_id="sid-1")
    monkeypatch.setattr(discover, "find_claude_ancestor_pid", lambda: live_pid)
    args = discover.build_parser().parse_args(["identify", "--role", "validator"])
    assert discover.command_identify(args) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["role"] == "validator"
    assert printed["label"] == "validator"
    assert printed["session_id"] == "sid-1"
    directory = json.loads(discover.DIRECTORY_PATH.read_text())
    assert directory["sessions"][0]["role"] == "validator"


def test_command_self_exits_2_before_identify(discover, monkeypatch, write_registry_entry, live_pid, capsys):
    write_registry_entry(live_pid, "me", ROOT)
    monkeypatch.setattr(discover, "find_claude_ancestor_pid", lambda: live_pid)
    assert discover.command_self(None) == 2
    assert "identity not set" in capsys.readouterr().err


def test_command_self_prints_role_after_identify(discover, monkeypatch, write_registry_entry, write_identity_file, live_pid, capsys):
    write_registry_entry(live_pid, "me", ROOT)
    write_identity_file(live_pid, "manager")
    monkeypatch.setattr(discover, "find_claude_ancestor_pid", lambda: live_pid)
    assert discover.command_self(None) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["pid"] == live_pid
    assert printed["role"] == "manager"
    assert printed["label"] == "manager"


def test_command_list_marks_identified_self_and_filters_root(
    discover, monkeypatch, write_registry_entry, write_identity_file, live_pid, capsys
):
    write_registry_entry(live_pid, "me", ROOT)
    monkeypatch.setattr(discover, "pid_is_alive", lambda pid: pid in {live_pid, 100, 101})
    write_registry_entry(100, "identified-fake", FAKE_ROOT)
    write_registry_entry(101, "unidentified-fake", FAKE_ROOT)
    write_identity_file(100, "fake manager")
    write_identity_file(live_pid, "validator")
    monkeypatch.setattr(discover, "find_claude_ancestor_pid", lambda: live_pid)
    args = discover.build_parser().parse_args(["list", "--root", FAKE_ROOT])
    assert discover.command_list(args) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["pid"] for r in rows] == [100, 101]
    assert rows[0]["identified"] is True and rows[0]["role"] == "fake manager"
    assert rows[1]["identified"] is False and rows[1]["role"] is None
    assert "self" not in rows[0] and "self" not in rows[1]


def test_command_list_marks_self(discover, monkeypatch, write_registry_entry, write_identity_file, live_pid, capsys):
    write_registry_entry(live_pid, "me", ROOT)
    write_identity_file(live_pid, "validator")
    monkeypatch.setattr(discover, "find_claude_ancestor_pid", lambda: live_pid)
    args = discover.build_parser().parse_args(["list", "--root", ROOT])
    discover.command_list(args)
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert rows == [{**rows[0], "self": True}]


def test_command_list_outside_claude_still_lists(discover, monkeypatch, write_registry_entry, live_pid, capsys):
    write_registry_entry(live_pid, "someone", ROOT)
    monkeypatch.setattr(discover, "own_session", lambda: None)
    args = discover.build_parser().parse_args(["list", "--root", ROOT])
    assert discover.command_list(args) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert rows[0]["identified"] is False
    assert "self" not in rows[0]


def test_command_list_without_root_prints_every_live_session(discover, monkeypatch, write_registry_entry, capsys):
    monkeypatch.setattr(discover, "pid_is_alive", lambda pid: True)
    monkeypatch.setattr(discover, "own_session", lambda: None)
    write_registry_entry(1, "a", ROOT)
    write_registry_entry(2, "b", "/elsewhere")
    args = discover.build_parser().parse_args(["list"])
    discover.command_list(args)
    assert len(capsys.readouterr().out.splitlines()) == 2


def test_command_done_exit_1_names_unidentified_under_root(discover, monkeypatch, write_registry_entry, write_identity_file, capsys):
    monkeypatch.setattr(discover, "pid_is_alive", lambda pid: True)
    write_registry_entry(100, "identified-fake", FAKE_ROOT)
    write_registry_entry(101, "unidentified-fake", FAKE_ROOT)
    write_registry_entry(102, "unidentified-outside", "/elsewhere")
    write_identity_file(100, "fake manager")
    args = discover.build_parser().parse_args(["done", "--root", FAKE_ROOT])
    assert discover.command_done(args) == 1
    err = capsys.readouterr().err
    assert "unidentified-fake (pid 101)" in err
    assert "102" not in err


def test_command_done_exit_0_when_all_identified(discover, monkeypatch, write_registry_entry, write_identity_file, capsys):
    monkeypatch.setattr(discover, "pid_is_alive", lambda pid: True)
    write_registry_entry(100, "a", FAKE_ROOT)
    write_registry_entry(101, "b", FAKE_ROOT)
    write_identity_file(100, "fake manager")
    write_identity_file(101, "fake builder")
    args = discover.build_parser().parse_args(["done", "--root", FAKE_ROOT])
    assert discover.command_done(args) == 0
    assert "every live session under the root has an identity" in capsys.readouterr().out


def test_command_done_exit_0_with_no_sessions(discover, capsys):
    args = discover.build_parser().parse_args(["done", "--root", FAKE_ROOT])
    assert discover.command_done(args) == 0


def test_session_exit_removes_it_on_next_list(discover, monkeypatch, write_registry_entry, write_identity_file, capsys):
    alive = {100, 101}
    monkeypatch.setattr(discover, "pid_is_alive", lambda pid: pid in alive)
    monkeypatch.setattr(discover, "own_session", lambda: None)
    write_registry_entry(100, "fake-manager", FAKE_ROOT)
    write_registry_entry(101, "fake-builder", FAKE_ROOT)
    write_identity_file(100, "fake manager")
    write_identity_file(101, "fake builder")
    args = discover.build_parser().parse_args(["list", "--root", FAKE_ROOT])
    discover.command_list(args)
    first = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["pid"] for r in first] == [100, 101]
    assert all(r["identified"] for r in first)
    alive.remove(101)
    discover.command_list(args)
    second = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["pid"] for r in second] == [100]
    assert not discover.identity_path(101).exists()
    assert discover.identity_path(100).exists()


@pytest.mark.parametrize("removed", ["record", "protocol", "ui"])
def test_removed_mesh_commands_are_rejected(discover, removed, capsys):
    with pytest.raises(SystemExit) as exit_info:
        discover.build_parser().parse_args([removed])
    assert exit_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


@pytest.mark.parametrize("flag", [["list", "--as-pid", "1"], ["list", "--out", "x"], ["identify"]])
def test_removed_flags_and_missing_role_are_rejected(discover, flag):
    with pytest.raises(SystemExit) as exit_info:
        discover.build_parser().parse_args(flag)
    assert exit_info.value.code == 2


@pytest.mark.parametrize("role", ["", "   ", "\t\n"])
def test_command_identify_blank_role_exits_2_and_writes_nothing(discover, monkeypatch, role, capsys):
    monkeypatch.setattr(discover, "own_session", lambda: pytest.fail("own_session consulted for a blank role"))
    args = discover.build_parser().parse_args(["identify", "--role", role])
    assert discover.command_identify(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "role is blank" in captured.err
    assert not discover.IDENTITY_DIR.exists()
    assert not discover.DIRECTORY_PATH.exists()


def test_command_identify_stores_the_role_stripped(discover, monkeypatch, write_registry_entry, live_pid, capsys):
    write_registry_entry(live_pid, "me", ROOT, session_id="sid-1")
    monkeypatch.setattr(discover, "find_claude_ancestor_pid", lambda: live_pid)
    args = discover.build_parser().parse_args(["identify", "--role", "  viz-builder \n"])
    assert discover.command_identify(args) == 0
    printed = json.loads(capsys.readouterr().out)
    assert (printed["role"], printed["label"]) == ("viz-builder", "viz-builder")
    stored = json.loads(discover.identity_path(live_pid).read_text())
    assert (stored["role"], stored["label"]) == ("viz-builder", "viz-builder")


def test_module_has_no_ui_leftovers(discover):
    assert not any(name.startswith("UI_") or "ui" in name.lower().split("_") for name in dir(discover))
    assert not hasattr(discover, "time") and not hasattr(discover, "urllib")
