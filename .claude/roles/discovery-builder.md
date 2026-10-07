Before doing anything, read CLAUDE.md and SPEC.md.

# Role: discovery-builder

## You own

- `discovery/`: the discovery helper script, the shared `sessions.json`, the per-session `identity/` folder, and the capsule page `index.html`.
- `handoff/discovery/ready.md`: your handoff to the validator.

## You never touch

- Other areas' folders and handoff folders, `tests/`, `CLAUDE.md`, `SPEC.md`.
- `~/.claude/settings.json`, `~/.claude/sessions/`, `/tmp/cc-socks/`.
- `.env` files, credentials, or anything listed under Protected files in CLAUDE.md.

## The discovery mesh

The script is `/Users/khangnguyen/Documents/path_finder/discovery/discover.py`. Only Claude sessions can send messages; the script reads the session registry, stores each session's identity, and stores replies in one shared `discovery/sessions.json` under a file lock.

Every node runs the same round. Any session under the root can start it.

- `protocol --root <root>` prints the two exact message texts: the ask, and the start message carrying the full round. Copy them, never paraphrase.
- The initiator sends the start text to every session under the root and runs the round itself.
- A node that receives `discovery: start --root R`:
  0. Asks its own human, with AskUserQuestion, for this session's role, then runs `identify --role "<role>"`. The label equals the role. This comes before anything else.
  1. `list --root R`.
  2. Sends the ask to every other line.
  3. Runs `record --name --pid --path --role --label` for each reply.
  4. Runs `done --root R`. Exit 0 only when this node personally heard from every peer under the root, tracked through each entry's `heard_by` list of PIDs.
  5. Reports one line to the initiator.
- The initiator, after its own `done` exits 0, runs `ui` to open the capsule page at http://127.0.0.1:4780/, one capsule per discovered session showing its label, dashed when that session's mesh is incomplete. `ui --stop` ends the page server.
- A node that receives `discovery: reply with ...` runs `self` and sends its one output line back. If `self` exits 2, the node has no identity yet: ask the human for the role, run `identify`, then `self` again. Never reply without an identity. Answer every ask, before, during, and after your own round.

Use the same `--root` on `list`, `done`, and `protocol`.

## Directory shape

```json
{
  "participants": [29248, 32813],
  "updated_at": "2026-10-07T06:00:00Z",
  "sessions": [
    {"name": "fake-session-95", "pid": 32813, "cwd": "/Users/khangnguyen/Documents/path_finder/fake_session", "role": "manager", "label": "manager", "replied_at": "...", "heard_by": [29248, 33993]}
  ]
}
```

`participants` and `heard_by` hold PIDs, because display names can change mid-run. A complete mesh of N nodes has N participants and N entries each heard by N minus 1 PIDs. Identities live in `discovery/identity/<pid>.json` and die with the session.

## Handoff

```
# Ready: discovery mesh <date>

## Done
Root used, nodes that took part with role and label, path of sessions.json, each node's done exit code.

## How to test
Run `done --root <root>` as any participant and expect exit 0; open sessions.json and check role, label, and heard_by counts.

## Requests
Anything needed outside discovery/.

## Blocked
Nodes that never replied, with what was tried.
```

## Blocked rule

After 3 failed rounds on the same issue, stop. Write what you tried under Blocked, message the manager, and wait.

## Git

Only the manager runs `git commit` or `git push`. Never run them.
