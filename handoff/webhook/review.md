# Review: W2 2026-10-05

PASS

# Review: W1 2026-10-05

NOT YET REVIEWABLE. Acceptance requires all four W-U findings filled in from the raw log. W-U3 and W-U4 are pending the manager installing the catch-all (M1). The parts that exist now pass; re-review after the raw log lands and SPEC.md §6 is complete.

## What was checked

Smoke test from ready.md, run against a temp log path instead of `/tmp/raw-test.jsonl`:

| Step | Expected | Actual |
|---|---|---|
| SendMessage PostToolUse record | exit 0 | exit 0 |
| `not json` on stdin | exit 0 | exit 0 |
| unwritable log path | exit 0 | exit 0 |
| line count | 2 | 2 |
| `input.kept.tool_input` | `{"to":"listings-bc","notify_when_idle":true}` | identical |
| `input.shape.tool_input.message` | `string(11)` | identical |
| `grep "hello there"` in the log | 0 matches | 0 matches |
| stdout + stderr across all runs | 0 bytes | 0 bytes |
| stdin from `/dev/null` | exit 0, record appended | exit 0, record appended |
| run time per invocation | fast | 34 ms |

Docs examples in `docs/webhook/hooks.md`, each run by importing the module:

| Function | Result |
|---|---|
| `describeShape` | documented output |
| `describeShape([1,2,3])` | `["array(3)"]`, matches the documented form |
| `redactHookInput` (SendMessage example) | `kept` and `shape` identical to the docs |
| `redactHookInput("str")`, `redactHookInput(null)` | `{shape}` only, as documented |
| `buildRawRecord("not json", ...)` | `{unparseable: true, length: 8}` |
| `appendRaw("/nonexistent-root/raw.jsonl", ...)` | `false` |
| `readStdin()` with no stdin | `""` |
| `main` Stop example | exit 0, `input.kept` identical to the docs |
| `ancestorChain` | PIDs differ by nature; observed chain is hook -> /bin/zsh -> claude, matching the documented structure |

W2: `node --version` is v24.14.0. `cd webhook && npm install` completes with 0 dependencies. `package.json` is ESM, private, engines `>=20`.

SPEC.md §6: W-U1 and W-U2 are filled in with evidence. W-U2 quotes the session file shape without leaking a full session id.

## Notes, not failures

1. `webhook/hooks/capture-raw.js:112` calls `main()` at module load. Importing the module from a unit test reads stdin and appends a record to `$CC_DASHBOARD_RAW_LOG` or `/tmp/cc-dashboard-raw.jsonl` (verified: one line written on a bare import). For V2 tests, guard the call with an entry-point check such as comparing `import.meta.url` to `pathToFileURL(process.argv[1]).href`, or move `main()` into a separate `bin` file. Same request applies to the W3 hook.
2. `npm install` in `webhook/` writes `package-lock.json`. I deleted the one my run created. Builder decides whether to commit it or add it to `.gitignore`.
3. V1 request (ready.md Requests item 4) noted: `node:test`, ESM modules with exported functions. That matches my drafted proposal.
