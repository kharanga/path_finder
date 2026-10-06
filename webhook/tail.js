import { closeSync, openSync, readSync, statSync } from "node:fs";

/** How often tailFile checks the events file for new bytes, in milliseconds. */
export const DEFAULT_POLL_MS = 300;

/** Reads every complete line appended after `offset` and returns {lines, offset, truncated}. */
export function readNewLines(filePath, offset, carry = "") {
  let size;
  try {
    size = statSync(filePath).size;
  } catch {
    return { lines: [], offset, carry, truncated: false, missing: true };
  }
  const truncated = size < offset;
  const start = truncated ? 0 : offset;
  if (size === start) return { lines: [], offset: start, carry: truncated ? "" : carry, truncated, missing: false };
  const fd = openSync(filePath, "r");
  let text;
  try {
    const buffer = Buffer.alloc(size - start);
    readSync(fd, buffer, 0, buffer.length, start);
    text = (truncated ? "" : carry) + buffer.toString("utf8");
  } finally {
    closeSync(fd);
  }
  const parts = text.split("\n");
  const rest = parts.pop();
  return { lines: parts, offset: size, carry: rest, truncated, missing: false };
}

/** Polls a file for appended lines and calls onLine for each; returns a function that stops tailing. */
export function tailFile(filePath, onLine, options = {}) {
  const pollMs = options.pollMs ?? DEFAULT_POLL_MS;
  let offset = options.fromStart === false ? safeSize(filePath) : 0;
  let carry = "";
  const pump = () => {
    const result = readNewLines(filePath, offset, carry);
    offset = result.offset;
    carry = result.carry;
    if (result.truncated && options.onTruncate) options.onTruncate();
    for (const line of result.lines) onLine(line);
  };
  pump();
  if (options.onReplayComplete) options.onReplayComplete();
  const timer = setInterval(pump, pollMs);
  if (timer.unref) timer.unref();
  return () => clearInterval(timer);
}

function safeSize(filePath) {
  try {
    return statSync(filePath).size;
  } catch {
    return 0;
  }
}
