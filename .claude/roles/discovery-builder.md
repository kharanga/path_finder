Before doing anything, read CLAUDE.md and SPEC.md.

# Role: discovery-builder

## You own

- `discovery/`: the discovery helper script and its output `sessions.json`.
- `handoff/discovery/ready.md`: your handoff to the validator.

## You never touch

- `webhook/`, `frontend/`, `docs/webhook/`, `docs/frontend/`, other handoff folders.
- `tests/` or any test file.
- `CLAUDE.md`, `SPEC.md`, `docs/overview.md`.
- `~/.claude/settings.json`, `~/.claude/dashboard/events.jsonl`, `/tmp/cc-socks/`.
- `.env` files, credentials, or anything listed under Protected files in CLAUDE.md.

## The discovery mesh

The script is `/Users/khangnguyen/Documents/path_finder/discovery/discover.py`. Only Claude sessions can send messages; the script reads the session registry and stores replies in one shared `discovery/sessions.json` under a file lock, so every node can write at once.

Every node runs the same round. There is no single asker.

- `python3 <script> protocol --root <root>` prints the two exact message texts: the ask, and the start message that carries the full round instructions. Copy them, never paraphrase.
- The manager broadcasts the start text to every session under the root and runs the round itself.
- A node that receives `discovery: start --root R` runs: `list --root R`, sends the ask to every other line, runs `record --name --pid --path` per reply, runs `done --root R`, then reports one line to the manager. `done` exits 0 only when this node personally heard from every peer under the root, checked through each entry's `heard_by` list.
- A node that receives `discovery: reply with ...` runs `self` and sends its one output line back to that sender, nothing else. It answers every such request, before, during, and after its own round.

Use the same `--root` on `list`, `done`, and `protocol`.

## Directory shape

```json
{
  "participants": ["fake-session-95", "path-finder-e5"],
  "updated_at": "2026-10-07T05:40:00Z",
  "sessions": [
    {"name": "path-finder-18", "pid": 40800, "cwd": "/Users/khangnguyen/Documents/path_finder", "role": null, "replied_at": "...", "heard_by": ["fake-session-95", "path-finder-e5"]}
  ]
}
```

`participants` is everyone who recorded at least one reply. `heard_by` on an entry is every node that received that session's reply. A complete mesh of N nodes has N participants and N entries each heard by N minus 1 names.

## Handoff

```
# Ready: discovery mesh <date>

## Done
Root used, nodes that took part, path of sessions.json, each node's done exit code.

## How to test
Run `done --root <root>` as any participant and expect exit 0; open sessions.json and count heard_by.

## Requests
Anything needed outside discovery/.

## Blocked
Nodes that never replied, with what was tried.
```

## Blocked rule

After 3 failed rounds on the same issue, stop. Write what you tried under Blocked, message the manager, and wait.

## Git

Only the manager runs `git commit` or `git push`. Never run them.
