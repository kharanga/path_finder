# webhook docs

Owner: webhook-builder. One markdown file per module in `webhook/`.

| File | Module | Status |
|---|---|---|
| `hooks.md` | `webhook/hooks/dashboard-hook.js`, `webhook/hooks/capture-raw.js`, raw hook input shape | W1, W3 |
| `schema.md` | `webhook/schema.js` | W3 |
| `fake-generator.md` | `webhook/fake.js` | W4 |
| `server.md` | `webhook/server.js` | W5 |
| `tail.md` | `webhook/tail.js` | W6 |
| `state.md` | `webhook/state.js` | W6 |
| `liveness.md` | `webhook/liveness.js` | W6 |

Each public function, class, or endpoint is documented with What it does, Inputs, Output, Errors, and an Example with a realistic input and the expected output. Docs are updated in the same task as the code. The validator checks every example.
