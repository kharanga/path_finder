# Review: W1 2026-10-05 (re-review)

PASS

# Review: W2 2026-10-05

PASS

## What was checked for W1

Acceptance: all four W-U findings filled in with evidence from the raw log, and `docs/webhook/hooks.md` describes the raw hook input shape.

- SPEC.md §6: W-U1 to W-U4 each carry quoted redacted fragments and timestamps. Every timestamp cited (06:03:57 PostToolUse SendMessage from PID 52134 to path-finder-e5, 06:04:10 UserPromptSubmit for 40707, 06:04:57 Stop for 40707, 06:04:33 Stop and 06:04:49 UserPromptSubmit for 29248, 06:04:09 Notification for 29248, 06:04:48 SendMessage to path-finder-18 and its 06:04:53 UserPromptSubmit) exists in `/tmp/cc-dashboard-raw.jsonl`, checked with the redacted summary script from ready.md.
- Privacy: 95 records. Zero matches for four phrases taken from this session's own outgoing messages. Longest kept string value is 49 characters (a path), so no prompt or message text is present.
- `docs/webhook/hooks.md`: raw input shape table rewritten from observed records, with `SessionStart` and `SessionEnd` fields marked as not yet observed. All function examples still produce the documented output (re-run after the entry-point change).
- Import guard (`capture-raw.js:106`): a bare `import()` with `CC_DASHBOARD_RAW_LOG` pointing at a temp path returns 8 exports and creates no file. Direct runs by absolute path, relative path, and an unnormalized path (`./webhook/hooks/../hooks/capture-raw.js`) all append a record and exit 0.

## Notes, not failures

1. `capture-raw.js:106`: when the script is run through a symlink, `process.argv[1]` is the link path while `import.meta.url` is the resolved path, so `main()` is skipped and nothing is logged, exit 0. Verified with a symlink in a temp dir. The installed snippet uses the real absolute path, so it does not bite today, but a packaged plugin (M4) might. Comparing `realpathSync(process.argv[1])` closes it. Same applies to the W3 hook if it copies this guard.
2. Review note 2 from the first round (package-lock.json) is now a manager request in ready.md. Nothing further from me.

# V1: test structure 2026-10-05

Created `tests/` at the repo root. Framework is `node:test` with `node:assert/strict`, built into Node 24, no dependencies.

```
tests/
  README.md                       layout, run command, conventions
  unit/harness.test.js            checks the helpers themselves (V2, V3 tests go in unit/webhook/, unit/frontend/)
  integration/placeholder.test.js todo marker for V4
  docs-examples/placeholder.test.js todo marker for V5
  helpers/dom-stub.js             minimal document for render.js tests, no browser or jsdom
  helpers/tmp-dir.js              temp directory per test, never real data
```

Run from the repo root:

```
node --test "tests/**/*.test.js"
```

Manager: the assigned form `node --test tests/` fails on Node 24, which treats the directory as a single file. The quoted glob is the working command; please record it in `CLAUDE.md` under run tests. Current run: 4 tests, 2 pass, 2 todo, 0 fail.

V2 not started, awaiting assignment.
