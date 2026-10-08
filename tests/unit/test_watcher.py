import json
import os
import time

import pytest

from conftest import FIXTURES_DIR

ROOT = "/home/user/path_finder"
FAKE_ROOT = f"{ROOT}/fake_session"
SESSION_ID = "ab5e0a7a-abdf-48ae-b34a-85aebcb80f95"
OTHER_ID = "67139bc5-30c6-43e1-aa4c-71415790bb63"


def registry_entry(pid=32813, cwd=FAKE_ROOT, session_id=SESSION_ID, started_at_ms=1_791_349_700_855, name="fake-session-manager"):
    return {"pid": pid, "name": name, "cwd": cwd, "socket": f"uds:/tmp/cc-socks/{pid}.sock", "session_id": session_id, "started_at_ms": started_at_ms}


def write_transcript(watcher, cwd, session_id, mtime=None):
    folder = watcher.PROJECTS_DIR / watcher.encoded_cwd(cwd)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{session_id}.jsonl"
    path.write_text('{"type":"summary"}\n')
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def write_registry(watcher, entry):
    on_disk = {"pid": entry["pid"], "name": entry["name"], "cwd": entry["cwd"], "sessionId": entry["session_id"], "startedAt": entry["started_at_ms"]}
    (watcher.SESSIONS_DIR / f"{entry['pid']}.json").write_text(json.dumps({k: v for k, v in on_disk.items() if v is not None}))


@pytest.mark.parametrize("cwd, expected", [
    ("/Users/me/Documents/path_finder", "-Users-me-Documents-path-finder"),
    ("/Users/me/Documents/path_finder/fake_session", "-Users-me-Documents-path-finder-fake-session"),
    ("/private/tmp/claude-501/-Users-me-x/scratchpad", "-private-tmp-claude-501--Users-me-x-scratchpad"),
    ("/a.b/c d", "-a-b-c-d"),
])
def test_encoded_cwd_replaces_every_non_alphanumeric_character(watcher, cwd, expected):
    assert watcher.encoded_cwd(cwd) == expected


def test_read_registry_entry_from_sanitized_fixture_carries_session_id_and_start(watcher):
    entry = watcher.read_registry_entry(FIXTURES_DIR / "discovery" / "registry_entry.json")
    assert entry["session_id"] == SESSION_ID
    assert entry["started_at_ms"] == 1791349700855
    assert entry["socket"] == "uds:/tmp/cc-socks/32813.sock"
    assert entry["cwd"] == FAKE_ROOT


def test_read_registry_entry_without_session_id_or_start_leaves_them_null(watcher, tmp_path):
    path = tmp_path / "e.json"
    path.write_text(json.dumps({"pid": 1, "name": "n", "cwd": ROOT}))
    entry = watcher.read_registry_entry(path)
    assert entry["session_id"] is None
    assert entry["started_at_ms"] is None


@pytest.mark.parametrize("content", ["{broken", json.dumps({"pid": "1"}), json.dumps({})])
def test_read_registry_entry_rejects_bad_files(watcher, tmp_path, content):
    path = tmp_path / "e.json"
    path.write_text(content)
    assert watcher.read_registry_entry(path) is None


def test_read_registry_entry_missing_file(watcher, tmp_path):
    assert watcher.read_registry_entry(tmp_path / "none.json") is None


def test_read_identity_missing_or_corrupt_gives_nulls(watcher):
    assert watcher.read_identity(5) == {"role": None, "label": None}
    (watcher.IDENTITY_DIR / "5.json").write_text("{nope")
    assert watcher.read_identity(5) == {"role": None, "label": None}


def test_read_identity_reads_role_and_label(watcher):
    (watcher.IDENTITY_DIR / "5.json").write_text(json.dumps({"pid": 5, "role": "manager", "label": "mgr"}))
    assert watcher.read_identity(5) == {"role": "manager", "label": "mgr"}


def test_resolve_by_registry_session_id(watcher):
    path = write_transcript(watcher, FAKE_ROOT, SESSION_ID)
    resolved = watcher.resolve_transcript(registry_entry())
    assert resolved == {"transcript": str(path), "method": "registry sessionId"}


def test_resolve_by_registry_session_id_not_written_yet(watcher):
    resolved = watcher.resolve_transcript(registry_entry())
    assert resolved["transcript"] is None
    assert resolved["method"] == "registry sessionId, transcript not written yet"


def test_resolve_prefers_transcript_under_own_cwd_folder_when_id_appears_twice(watcher):
    write_transcript(watcher, "/elsewhere", SESSION_ID)
    own = write_transcript(watcher, FAKE_ROOT, SESSION_ID)
    resolved = watcher.resolve_transcript(registry_entry())
    assert resolved == {"transcript": str(own), "method": "registry sessionId"}


def test_resolve_reports_ambiguity_when_id_appears_twice_outside_own_folder(watcher):
    write_transcript(watcher, "/elsewhere", SESSION_ID)
    write_transcript(watcher, "/another", SESSION_ID)
    resolved = watcher.resolve_transcript(registry_entry())
    assert resolved["transcript"] is None
    assert resolved["method"] == "registry sessionId, ambiguous (2 files)"


def test_resolve_ambiguous_without_cwd_does_not_crash(watcher):
    write_transcript(watcher, "/elsewhere", SESSION_ID)
    write_transcript(watcher, "/another", SESSION_ID)
    resolved = watcher.resolve_transcript(registry_entry(cwd=None))
    assert resolved["transcript"] is None


def test_fallback_single_transcript_since_start(watcher):
    started = 1_000_000_000_000
    chosen = write_transcript(watcher, FAKE_ROOT, SESSION_ID, mtime=started / 1000 + 10)
    write_transcript(watcher, FAKE_ROOT, OTHER_ID, mtime=started / 1000 - 10)
    resolved = watcher.resolve_transcript(registry_entry(session_id=None, started_at_ms=started))
    assert resolved == {"transcript": str(chosen), "session_id": SESSION_ID, "method": "cwd folder, single transcript since start"}


def test_fallback_ambiguous_when_two_transcripts_since_start(watcher):
    started = 1_000_000_000_000
    write_transcript(watcher, FAKE_ROOT, SESSION_ID, mtime=started / 1000 + 10)
    write_transcript(watcher, FAKE_ROOT, OTHER_ID, mtime=started / 1000 + 20)
    resolved = watcher.resolve_transcript(registry_entry(session_id=None, started_at_ms=started))
    assert resolved == {"transcript": None, "method": "cwd folder, ambiguous (2 candidates)"}


def test_fallback_zero_candidates_when_folder_missing(watcher):
    resolved = watcher.resolve_transcript(registry_entry(session_id=None))
    assert resolved == {"transcript": None, "method": "cwd folder, ambiguous (0 candidates)"}


def test_fallback_without_cwd_or_start(watcher):
    resolved = watcher.resolve_transcript(registry_entry(session_id=None, cwd=None, started_at_ms=None))
    assert resolved["transcript"] is None


def test_fallback_without_start_accepts_any_mtime(watcher):
    chosen = write_transcript(watcher, FAKE_ROOT, SESSION_ID, mtime=1)
    resolved = watcher.resolve_transcript(registry_entry(session_id=None, started_at_ms=None))
    assert resolved["transcript"] == str(chosen)


def test_session_map_merges_registry_identity_and_transcript(watcher, monkeypatch):
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: pid in {32813, 33993})
    manager = registry_entry()
    builder = registry_entry(pid=33993, session_id=OTHER_ID, name="fake-session-builder")
    write_registry(watcher, manager)
    write_registry(watcher, builder)
    write_registry(watcher, registry_entry(pid=1, session_id="dead", name="dead"))
    write_transcript(watcher, FAKE_ROOT, SESSION_ID)
    write_transcript(watcher, FAKE_ROOT, OTHER_ID)
    (watcher.IDENTITY_DIR / "32813.json").write_text(json.dumps({"role": "fake session manager", "label": "fake manager"}))
    rows = watcher.session_map(FAKE_ROOT)
    assert [r["pid"] for r in rows] == [32813, 33993]
    assert rows[0]["label"] == "fake manager" and rows[0]["role"] == "fake session manager"
    assert rows[1]["label"] is None and rows[1]["role"] is None
    assert rows[0]["transcript"].endswith(f"{SESSION_ID}.jsonl")
    assert rows[1]["transcript"].endswith(f"{OTHER_ID}.jsonl")
    assert all(r["method"] == "registry sessionId" for r in rows)


def test_session_map_root_filter_and_no_root(watcher, monkeypatch):
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: True)
    write_registry(watcher, registry_entry(pid=1, cwd=FAKE_ROOT))
    write_registry(watcher, registry_entry(pid=2, cwd="/elsewhere", session_id=OTHER_ID))
    assert [r["pid"] for r in watcher.session_map(FAKE_ROOT)] == [1]
    assert [r["pid"] for r in watcher.session_map(None)] == [1, 2]
    assert watcher.session_map("/nowhere") == []


def test_command_map_text_output_and_exit_codes(watcher, monkeypatch, capsys):
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: True)
    write_registry(watcher, registry_entry())
    write_transcript(watcher, FAKE_ROOT, SESSION_ID)
    args = watcher.build_parser().parse_args(["map", "--root", FAKE_ROOT])
    assert watcher.command_map(args) == 0
    fields = capsys.readouterr().out.rstrip("\n").split("\t")
    assert fields[0] == "32813"
    assert fields[1] == SESSION_ID
    assert fields[2].endswith(f"{SESSION_ID}.jsonl")
    assert fields[3] == "fake-session-manager"
    assert fields[4] == "registry sessionId"


def test_command_map_exit_1_when_a_session_is_unmapped(watcher, monkeypatch, capsys):
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: True)
    write_registry(watcher, registry_entry())
    args = watcher.build_parser().parse_args(["map"])
    assert watcher.command_map(args) == 1
    assert "transcript not written yet" in capsys.readouterr().out


def test_command_map_json_output(watcher, monkeypatch, capsys):
    monkeypatch.setattr(watcher, "pid_is_alive", lambda pid: True)
    write_registry(watcher, registry_entry())
    write_transcript(watcher, FAKE_ROOT, SESSION_ID)
    (watcher.IDENTITY_DIR / "32813.json").write_text(json.dumps({"role": "r", "label": "l"}))
    args = watcher.build_parser().parse_args(["map", "--json"])
    assert watcher.command_map(args) == 0
    rows = json.loads(capsys.readouterr().out)
    assert set(rows[0]) == {"pid", "name", "cwd", "socket", "session_id", "started_at_ms", "role", "label", "transcript", "method"}


def test_command_map_empty_exit_code_differs_between_text_and_json(watcher, capsys):
    text_args = watcher.build_parser().parse_args(["map", "--root", "/nowhere"])
    json_args = watcher.build_parser().parse_args(["map", "--root", "/nowhere", "--json"])
    assert watcher.command_map(text_args) == 1
    assert watcher.command_map(json_args) == 0
    capsys.readouterr()


def test_parser_rejects_unknown_command(watcher):
    with pytest.raises(SystemExit) as exit_info:
        watcher.build_parser().parse_args(["tail"])
    assert exit_info.value.code == 2
