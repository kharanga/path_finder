# Ready: V0 2026-10-08

## Done

`viz/watcher.py map` maps each live session's PID to its session id and transcript path.

Method, in the order the plan lists them:

1. The registry file `~/.claude/sessions/<pid>.json` holds `sessionId` (also `cwd`, `startedAt`, `messagingSocketPath`, `name`). The transcript is `~/.claude/projects/*/<sessionId>.jsonl`, found by globbing on the session id rather than by re-encoding `cwd`, because the folder encoding is lossy (every non-alphanumeric character becomes `-`). When the same id shows up under more than one folder, the file under the encoded `cwd` wins.
2. Fallback when `sessionId` is absent: the encoded `cwd` folder is scanned for transcripts modified since `startedAt`. One candidate is used; zero or several are reported as ambiguous with no path.
3. `origin.verifiedPeerPid` was not needed: every registry file on this machine (Claude Code 2.1.292 and 2.1.293) carries `sessionId`.

Files: `viz/watcher.py` (new). Nothing else touched.

Run: `python3 viz/watcher.py map [--root PATH] [--json]`. Output is one line per live session: pid, session id, transcript path, label (name when no identity), method. Exit 1 when any live session could not be mapped.

## How to test

```
python3 viz/watcher.py map --root fake_session
```

Expected (two lines, both method `registry sessionId`):

```
32813	ab5e0a7a-abdf-48ae-b34a-85aebcb80f95	/Users/<home>/.claude/projects/-Users-khangnguyen-Documents-path-finder-fake-session/ab5e0a7a-abdf-48ae-b34a-85aebcb80f95.jsonl	fake manager	registry sessionId
33993	67139bc5-30c6-43e1-aa4c-71415790bb63	/Users/<home>/.claude/projects/-Users-khangnguyen-Documents-path-finder-fake-session/67139bc5-30c6-43e1-aa4c-71415790bb63.jsonl	fake builder	registry sessionId
```

Cross-checks:

- `grep -o '"sessionId":"[^"]*"' <transcript> | sort -u` prints exactly the mapped id for each file.
- `python3 viz/watcher.py map` with no root lists every live session on the machine (ten at the time of writing) with exit 0.
- `python3 viz/watcher.py map --json` returns the same rows as a JSON array, including `role`, `label`, `socket`, and `cwd`.

Fallback check without editing anything: the two fake sessions share a folder, so a registry entry with no `sessionId` resolves to `cwd folder, ambiguous (2 candidates)`:

```
python3 -c "import sys; sys.path.insert(0,'viz'); import watcher; print(watcher.resolve_transcript({'pid':32813,'name':'x','cwd':'/Users/khangnguyen/Documents/path_finder/fake_session','socket':'','session_id':None,'started_at_ms':1791349700855}))"
```

## Requests

- `docs/cross-session-message-format.md` §6: record the V0 method. Suggested text: "PID to session id: `~/.claude/sessions/<pid>.json` carries `sessionId`; the transcript is `~/.claude/projects/*/<sessionId>.jsonl`, located by globbing on the id. Fallback when the field is missing: the encoded `cwd` folder, single transcript modified since `startedAt`; otherwise ambiguous. `origin.verifiedPeerPid` is not needed for the map." The same section currently says to key nodes by `sessionId` and recommends a `SessionStart` hook; both contradict SPEC.md (keyed by PID, no hooks) and should be marked superseded.
- `docs/jsonl-transcript-spec.md` line 12 says only `/` becomes `-` in the folder name. Observed: every non-alphanumeric character becomes `-` (`path_finder` is `path-finder`; `/private/tmp/claude-501/-Users-...` is `-private-tmp-claude-501--Users-...`). The doc's advice not to reverse the encoding still holds.

## Blocked

Nothing.
