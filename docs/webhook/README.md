# webhook docs

Owner: webhook-builder.

One markdown file per module in `webhook/`. Expected files as the area grows:

- `hooks.md`: the hook script, raw hook input shape, each exported function.
- `fake-generator.md`: the fake event generator and its options.
- `server.md`: the server, each public function, and each HTTP endpoint.

Each public function, class, or endpoint is documented with:

- What it does
- Inputs: name, type, and meaning
- Output: type and meaning
- Errors: what it can throw and when
- Example: a realistic input and the expected output

Docs are updated in the same task as the code. The validator checks every example.
