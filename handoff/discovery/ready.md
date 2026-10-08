# Ready: D3 2026-10-08

## Done
`discovery/discover.py` is now self-registration only. No command sends or expects a message.

- `identify --role "<role>"`: writes `discovery/identity/<pid>.json` (label equals role, `identified_at` timestamp) and rebuilds the directory. Run it first, when the session starts.
- `self`: prints name, pid, cwd, socket, session_id, role, label. Exits 2 until `identify` has run.
- `list --root R`: reads `~/.claude/sessions/*.json` plus `identity/`, drops PIDs that are not alive, deletes identity files of dead PIDs, rebuilds `discovery/sessions.json` under `sessions.json.lock`, then prints one JSON line per live session under R. Each line carries `"identified": true|false`; the caller's own line carries `"self": true`. Unidentified sessions have `role`, `label`, and `identified_at` set to null; no role is ever invented.
- `done --root R`: rebuilds the directory the same way, exits 0 when every live session under R has an identity, else exits 1 and names the unidentified sessions on stderr.
- `ui` / `ui --stop`: unchanged from D2, except `ui` rebuilds the directory before serving.
- `protocol` and `record` are removed. `--as-pid`, `--out`, `participants`, `heard_by`, and `replied_at` are gone with them.

Directory: `/Users/khangnguyen/Documents/path_finder/discovery/sessions.json`. It holds every live session on the machine, not only those under a root, so one file serves every caller regardless of `--root`. `--root` filters only what `list` prints and what `done` requires. Shape:

```json
{
  "updated_at": "2026-10-08T07:34:41Z",
  "sessions": [
    {
      "pid": 32813,
      "name": "fake-session-manager",
      "cwd": "/Users/khangnguyen/Documents/path_finder/fake_session",
      "socket": "uds:/tmp/cc-socks/32813.sock",
      "session_id": "ab5e0a7a-abdf-48ae-b34a-85aebcb80f95",
      "role": "fake session manager",
      "label": "fake manager",
      "identified_at": "2026-10-07T06:09:37Z"
    }
  ]
}
```

`session_id` is filled from the registry's `sessionId` field, which every live registry entry on this machine has. The viz-builder's V0 can read it directly instead of matching on cwd.

`discovery/index.html`: a capsule is dashed when its session is unidentified instead of when its mesh was incomplete. The header counts identified sessions instead of participants.

Verified on 2026-10-08 07:34Z with the live machine: `list --root /Users/khangnguyen/Documents/path_finder` printed six sessions (two fake sessions plus manager, discovery-builder, viz-builder, validator), all with roles, zero messages sent. Four stale identity files from 2026-10-07 sessions (PIDs 29248, 40707, 40800, 52134) were dropped on the first `list`. A scratchpad test with a fake registry confirmed: a dead PID with an identity file is dropped and its identity file deleted; a live unidentified session prints with `"identified": false` and makes `done` exit 1; after `identify` `done` exits 0; after the live process exits the next `list` prints nothing.

## How to test
From any session under the root:

```
python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py list --root /Users/khangnguyen/Documents/path_finder/fake_session
```

Expect two lines, fake-session-manager (pid 32813) and fake-session-builder (pid 33993), both with `"identified": true` and a role, with no message sent and no new turn in either fake session's transcript.

```
python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py done --root /Users/khangnguyen/Documents/path_finder/fake_session
```

Expect exit 0.

To test removal, let one fake session exit (only its own human should close it), then rerun `list`: the exited PID is gone and `discovery/identity/<pid>.json` is deleted. To test the unidentified path without closing anything, start a fresh session under the root and run `list` before it has run `identify`: it prints with `"identified": false` and `done` exits 1 naming it.

Removed commands fail fast: `discover.py record` and `discover.py protocol` exit 2 with an argparse "invalid choice" error.

## Requests
- `CLAUDE.md` "What exists" still says `protocol` and `record` "are removed in D3"; they are removed now. Manager to update the sentence and mark D3 done in `SPEC.md`.
- The role file `.claude/roles/discovery-builder.md` describes `identified_at`; the previous identity files used `set_at`. `with_identity` reads either, so old files still work until they are dropped.

## Blocked
None.
