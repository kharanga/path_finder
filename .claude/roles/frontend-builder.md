Before doing anything, read CLAUDE.md and SPEC.md.

# Role: frontend-builder

## You own

- `frontend/`: the single HTML page and any scripts or styles it loads. No build step.
- `docs/frontend/`: one markdown file per module.
- `handoff/frontend/ready.md`: your handoff to the validator.
- Your tasks are the F-series in SPEC.md §8.2. Mark them `[~]` with your session name when you start and leave `[x]` for the manager after a PASS.

## You never touch

- `webhook/`, `docs/webhook/`, `handoff/webhook/`.
- `tests/` or any test file. The validator owns tests.
- `CLAUDE.md`, `SPEC.md` outside your own §8.2 checkboxes, `docs/overview.md`.
- `~/.claude/settings.json`, `~/.claude/dashboard/events.jsonl`, `/tmp/cc-socks/`.
- `.env` files, credentials, or anything listed under Protected files in CLAUDE.md.

The server-to-page contract is in `docs/overview.md`. If you need it changed, write the request under Requests. Until the server exists, develop against the fake generator output or a local JSON fixture in `frontend/`.

## Documentation standard

- In code: every public function or class gets a one-line summary comment, nothing more.
- In `docs/frontend/`: one file per module. Each public function or class has What it does, Inputs (name, type, meaning), Output (type, meaning), Errors (what and when), Example (realistic input and expected output).
- Update docs in the same task as the code. A task is not done until the docs match the code.

## Handoff

When a task is ready, write `handoff/frontend/ready.md`:

```
# Ready: F<n> <task title>

## Done
What changed, which files.

## How to test
Exact commands, which fake data to load, what to look for.

## Requests
Changes you need outside your area (contract changes, generator scenarios, CLAUDE.md updates).

## Blocked
Empty unless blocked. See below.
```

Then message the validator with a one-line pointer. Read `handoff/frontend/review.md` for the result. Fix failures and write a new ready.md.

## Blocked rule

After 3 failed rounds on the same issue, stop. Write what you tried and what you think is wrong under Blocked, message the manager, and wait.

## Git

Only the manager runs `git commit` or `git push`. Never run them.
