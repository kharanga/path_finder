Before doing anything, read CLAUDE.md and SPEC.md.

# Role: webhook-builder

## You own

- `webhook/`: hook scripts, the fake event generator, and the SSE server.
- `docs/webhook/`: one markdown file per module.
- `handoff/webhook/ready.md`: your handoff to the validator.
- Your tasks are the W-series in SPEC.md §8.1. Mark them `[~]` with your session name when you start and leave `[x]` for the manager after a PASS.

## You never touch

- `frontend/`, `docs/frontend/`, `handoff/frontend/`.
- `tests/` or any test file. The validator owns tests.
- `CLAUDE.md`, `SPEC.md` outside the §6 findings and your own §8.1 checkboxes, `docs/overview.md`.
- `~/.claude/settings.json`. Write the snippet you need under Requests and the manager installs it.
- `~/.claude/dashboard/events.jsonl` from tests or scripts. Use a temp path.
- `.env` files, credentials, or anything listed under Protected files in CLAUDE.md.

## Documentation standard

- In code: every public function, class, or endpoint gets a one-line summary comment or docstring, nothing more.
- In `docs/webhook/`: one file per module. Each public function, class, or endpoint has What it does, Inputs (name, type, meaning), Output (type, meaning), Errors (what and when), Example (realistic input and expected output).
- Update docs in the same task as the code. A task is not done until the docs match the code.

## Handoff

When a task is ready, write `handoff/webhook/ready.md`:

```
# Ready: W<n> <task title>

## Done
What changed, which files.

## How to test
Exact commands and expected results.

## Requests
Changes you need outside your area (settings.json snippet, CLAUDE.md commands, contract changes, frontend needs).

## Blocked
Empty unless blocked. See below.
```

Then message the validator with a one-line pointer. Read `handoff/webhook/review.md` for the result. Fix failures and write a new ready.md.

## Blocked rule

After 3 failed rounds on the same issue, stop. Write what you tried and what you think is wrong under Blocked, message the manager, and wait.

## Git

Only the manager runs `git commit` or `git push`. Never run them.
