# tail.js

Follows `events.jsonl` by byte offset. Used by the server for the startup replay and the live tail. Handles partial last lines, truncation, and a file that does not exist yet.

## DEFAULT_POLL_MS

Constant `300`, how often `tailFile` checks for new bytes.

## readNewLines(filePath, offset, carry = "")

What it does: reads every byte after `offset`, splits complete lines, and keeps the unfinished tail for the next call.

Inputs:

- `filePath` (string): file to read.
- `offset` (integer): bytes already consumed.
- `carry` (string): unfinished line left over from the previous call.

Output: `{lines, offset, carry, truncated, missing}`. `lines` are complete lines without newline; `offset` is the new byte position; `carry` is the trailing partial line; `truncated` is true when the file is smaller than `offset`, in which case reading restarted at byte 0 and the old carry was dropped; `missing` is true when the file does not exist, with `lines` empty and `offset` unchanged.

Errors: none thrown. A missing file reports `missing: true`.

Example:

```js
import { writeFileSync, appendFileSync } from "node:fs";
import { readNewLines } from "./webhook/tail.js";
writeFileSync("/tmp/tail-example.jsonl", "a\nb\npartial");
let result = readNewLines("/tmp/tail-example.jsonl", 0);
// result.lines ["a", "b"], result.carry "partial", result.offset 11, result.truncated false, result.missing false
appendFileSync("/tmp/tail-example.jsonl", "-done\nc\n");
result = readNewLines("/tmp/tail-example.jsonl", result.offset, result.carry);
// result.lines ["partial-done", "c"], result.carry "", result.offset 19
writeFileSync("/tmp/tail-example.jsonl", "z\n");
result = readNewLines("/tmp/tail-example.jsonl", result.offset, result.carry);
// result.lines ["z"], result.truncated true, result.offset 2
readNewLines("/tmp/does-not-exist.jsonl", 0).missing // true
```

## tailFile(filePath, onLine, options = {})

What it does: calls `readNewLines` once immediately, which replays existing content, then again every `options.pollMs` milliseconds, passing each complete line to `onLine`.

Inputs:

- `filePath` (string).
- `onLine` (function(line)): called once per complete line, in order.
- `options.pollMs` (number, default 300).
- `options.fromStart` (boolean, default true): `false` skips existing content and only reports lines appended after the call.
- `options.onReplayComplete` (function): called after the first pass.
- `options.onTruncate` (function): called when the file shrank.

Output: a function that stops polling.

Errors: none thrown. A missing file is polled until it appears. The timer is unref'd so it never keeps the process alive on its own.

Example:

```js
import { writeFileSync, appendFileSync } from "node:fs";
import { tailFile } from "./webhook/tail.js";
writeFileSync("/tmp/tail-example.jsonl", "one\n");
const seen = [];
const stop = tailFile("/tmp/tail-example.jsonl", (line) => seen.push(line), { pollMs: 50, onReplayComplete: () => seen.push("<replayed>") });
appendFileSync("/tmp/tail-example.jsonl", "two\n");
await new Promise((resolve) => setTimeout(resolve, 150));
stop();
// seen ["one", "<replayed>", "two"]
```
