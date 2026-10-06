import { appendFileSync, mkdirSync, readFileSync, realpathSync } from "node:fs";
import { dirname } from "node:path";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

export const DEFAULT_RAW_LOG = "/tmp/cc-dashboard-raw.jsonl";

const KEPT_TOP_LEVEL_FIELDS = ["session_id", "hook_event_name", "cwd", "tool_name", "source", "reason", "stop_hook_active", "permission_mode"];
const KEPT_TOOL_INPUT_FIELDS = ["to", "notify_when_idle"];

/** Walks up from this process and returns the chain of {pid, ppid, command} ancestors, nearest first. */
export function ancestorChain(startPid = process.ppid, maxDepth = 6) {
  const chain = [];
  let pid = startPid;
  for (let depth = 0; depth < maxDepth && pid > 1; depth += 1) {
    let line;
    try {
      line = execFileSync("ps", ["-o", "ppid=,comm=", "-p", String(pid)], { encoding: "utf8" }).trim();
    } catch {
      break;
    }
    const match = line.match(/^\s*(\d+)\s+(.*)$/);
    if (!match) break;
    chain.push({ pid, ppid: Number(match[1]), command: match[2] });
    pid = Number(match[1]);
  }
  return chain;
}

/** Reads all of stdin synchronously and returns it as a string, or "" when stdin is a TTY or unreadable. */
export function readStdin() {
  if (process.stdin.isTTY) return "";
  try {
    return readFileSync(0, "utf8");
  } catch {
    return "";
  }
}

/** Replaces every value with a type description so shapes are logged without content. */
export function describeShape(value) {
  if (value === null) return "null";
  if (Array.isArray(value)) return [`array(${value.length})`];
  if (typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, inner]) => [key, describeShape(inner)]));
  }
  if (typeof value === "string") return `string(${value.length})`;
  return typeof value;
}

/** Keeps identifying hook fields verbatim, the shape of everything else, and the SendMessage recipient and notify flag. */
export function redactHookInput(input) {
  if (input === null || typeof input !== "object") return { shape: describeShape(input) };
  const kept = {};
  for (const key of KEPT_TOP_LEVEL_FIELDS) {
    if (key in input) kept[key] = input[key];
  }
  if (input.tool_name === "SendMessage" && input.tool_input && typeof input.tool_input === "object") {
    kept.tool_input = {};
    for (const key of KEPT_TOOL_INPUT_FIELDS) {
      if (key in input.tool_input) kept.tool_input[key] = input.tool_input[key];
    }
  }
  return { kept, shape: describeShape(input) };
}

/** Builds the raw capture record: timestamp, hook pid chain, argv, and the redacted stdin. */
export function buildRawRecord(stdinText, argv, now = new Date()) {
  let input;
  try {
    input = JSON.parse(stdinText);
  } catch {
    input = { unparseable: true, length: stdinText.length };
  }
  return {
    captured_at: now.toISOString(),
    hook_pid: process.pid,
    ancestors: ancestorChain(),
    argv,
    cwd: process.cwd(),
    input: redactHookInput(input),
  };
}

/** Appends one JSON line to the raw log, creating its directory, and never throws. */
export function appendRaw(logPath, record) {
  try {
    mkdirSync(dirname(logPath), { recursive: true });
    appendFileSync(logPath, `${JSON.stringify(record)}\n`);
  } catch {
    return false;
  }
  return true;
}

/** Entry point: captures redacted stdin plus process context to the raw log and always exits 0. */
export function main(argv = process.argv.slice(2)) {
  try {
    const logPath = argv[0] || process.env.CC_DASHBOARD_RAW_LOG || DEFAULT_RAW_LOG;
    appendRaw(logPath, buildRawRecord(readStdin(), argv));
  } catch {
    return;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  main();
}
