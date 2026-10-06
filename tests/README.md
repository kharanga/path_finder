# tests

Owner: validator. Framework: `node:test` and `node:assert/strict`, built into Node 24. No dependencies.

Run everything from the repo root:

```
node --test "tests/**/*.test.js"
```

`node --test tests/` does not work on Node 24 (the path is treated as one file). Quote the glob so the shell does not expand it.

## Layout

| Folder | Scope | Task |
|---|---|---|
| `unit/` | one function at a time, filesystem and process calls mocked, no network | V2 (webhook), V3 (frontend) |
| `integration/` | fake generator output through the server to an SSE client, temp `events.jsonl` only | V4 |
| `docs-examples/` | every fenced example in `docs/` run and compared with its documented output | V5 |
| `helpers/` | shared test utilities, not tests | |

Files are named `<module>.test.js` and mirror the source module: `unit/webhook/state.test.js` tests `webhook/state.js`, `unit/frontend/layout.test.js` tests `frontend/layout.js`.

## Conventions

- Tests never read or write `~/.claude/settings.json`, `~/.claude/dashboard/events.jsonl`, `/tmp/cc-socks/`, or any `.env`. Use `helpers/tmp-dir.js` for files and `CC_DASHBOARD_RAW_LOG` or the equivalent path argument to redirect hook output.
- Process liveness, timers, and the filesystem are mocked with `node:test`'s `mock.fn`, `mock.method`, and `mock.timers`, or by injecting a function (for example `findDeadSessions(state, now, isAlive)`).
- Frontend DOM tests use `helpers/dom-stub.js`, a minimal `document` that supports the selectors `render.js` needs. No browser, no jsdom.
- A test asserts the acceptance criteria in `SPEC.md`, not just current behavior. Name the task ID in the test description when one applies.
