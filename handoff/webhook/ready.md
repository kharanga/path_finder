# Ready: W6 documentation standard

## Done

- Docstrings: every export in `webhook/` now has a one-line `/** */` summary, including the 13 exported constants that lacked one (`SESSION_STATES`, `DEFAULTS`, `CONTENT_TYPES`, `FOLDERS`, path defaults, and so on). No other comments exist in the code.
- One docs file per module in `docs/webhook/`: `hooks.md` (`dashboard-hook.js`, `capture-raw.js`), `schema.md`, `fake-generator.md`, `server.md` (now `server.js` only), and three new files `tail.md`, `state.md`, `liveness.md` that previously shared `server.md` with abbreviated entries. Every public function, constant, and endpoint has What it does, Inputs, Output, Errors, Example. `README.md` indexes them.
- Every example runs as written. `handoff/webhook/docs-examples.mjs` executes all 44 documented examples across the seven files and asserts the documented outputs, including the CLI examples (`fake.js` fixture and raw runs, both hook scripts via stdin) and the HTTP examples (`startServer` on port 0, static file types, 405, and the exact SSE snapshot frame). It writes only under a temp directory.
- One code fix found by the runner: `capture-raw.js` `buildRawRecord` on non-JSON stdin wrote a redacted shape of the marker object instead of the documented `{unparseable: true, length}`. The code now matches the docs.
- `SPEC.md`: W6 marked in progress under my name. W1 to W5 checkboxes are the manager's.

## How to test

Docstring coverage, expect no output between the markers:

```
cd /Users/khangnguyen/Documents/path_finder
echo "--- exports without docstring:"
for f in webhook/*.js webhook/hooks/*.js; do awk -v f="$f" 'prev !~ /^\/\*\*.*\*\/$/ && /^export (async )?(function|const|class)/ {print f":"NR": "$0} {prev=$0}' "$f"; done
echo "--- non-docstring comments:"
grep -n "^\s*//" webhook/*.js webhook/hooks/*.js
echo "--- end"
```

Module to docs coverage, expect every module listed with a file:

```
for m in schema state tail liveness server fake; do test -f docs/webhook/$( [ $m = fake ] && echo fake-generator || echo $m ).md && echo "$m ok"; done; grep -c "^### \|^## " docs/webhook/hooks.md
```

Expected: six `ok` lines, and `hooks.md` has more than 15 headed sections.

All docs examples, run inside a Claude Code session so the two registry-dependent hook examples resolve a real session (the runner asserts this session's own PID and name in two checks, see note 1 under Requests):

```
node handoff/webhook/docs-examples.mjs /tmp/webhook-docs-examples
```

Expected: `passed 44, failed 0`, exit 0. Each `check(...)` name in the script maps to a heading in the docs file named by its prefix (`schema`, `state`, `liveness`, `tail`, `server`, `fake`, `capture`, `hook`).

## Requests

1. Validator: two checks in `docs-examples.mjs` (`hook registry`, `hook ancestor`) assert the session id, PID, and name of the session that wrote the docs (`177234a7-…`, 52134, `path-finder-37`), because the `hooks.md` examples quote those values. From another session they fail by design. Either run them with the values of your own session by editing the two literals, or treat those two as "value differs by nature" like you did for `ancestorChain` in the W1 review. If you adopt the runner for V5, it is yours to move into `tests/`; I will not touch it after this handoff.
2. Manager: `docs/webhook/README.md` and the three new files are the only docs changes outside `webhook/`'s own code. Nothing needed in `docs/overview.md`.

## Blocked

Empty.
