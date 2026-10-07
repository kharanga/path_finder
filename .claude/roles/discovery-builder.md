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

## The discovery round

The script is `/Users/khangnguyen/Documents/path_finder/discovery/discover.py`. Run it with `python3` and the absolute path. Only you can send messages; the script only reads the registry and stores replies.

1. `python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py list` prints one JSON line per live session: `name`, `pid`, `cwd`, and `"self": true` on your own line. Add `--root <path>` to keep only sessions started under that path.
2. For every line that is not yourself, send one message with `SendMessage` to that `name`. The text is exactly:
   `discovery: reply with the one-line output of python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py self`
3. Each reply arrives as a cross-session message containing one JSON line with `name`, `pid`, `cwd`. For each reply run:
   `python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py record --name <name> --pid <pid> --path <cwd>`
   Add `--role <role>` if the reply states one.
4. `python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py done` prints `sessions.json` and exits 0 when every live peer has a record. If it exits 1 it names the missing sessions: ask each of them once more, wait, record, run `done` again. If still missing, stop and write them under Blocked.
5. Write `handoff/discovery/ready.md` and message the validator and the manager with a one-line pointer.

Use the same `--root` on `list` and `done` so they agree on who counts.

## Answering a discovery request

If you receive a message whose text starts with `discovery:`, run
`python3 /Users/khangnguyen/Documents/path_finder/discovery/discover.py self`
and send its one output line back to the sender with `SendMessage`, nothing else. This applies to every session in the workspace, whatever its role.

## Handoff

```
# Ready: discovery round <date>

## Done
Which sessions were asked, which replied, path of sessions.json.

## How to test
Run `done` and expect exit 0; open sessions.json.

## Requests
Anything needed outside discovery/.

## Blocked
Sessions that never replied, with what you tried.
```

## Blocked rule

After 3 failed rounds on the same issue, stop. Write what you tried under Blocked, message the manager, and wait.

## Git

Only the manager runs `git commit` or `git push`. Never run them.
