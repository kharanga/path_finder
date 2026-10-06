import { appendFileSync, mkdirSync, readdirSync, readFileSync, realpathSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { homedir } from "node:os";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

/** Where the hook appends events when CC_DASHBOARD_EVENTS is not set. */
export const DEFAULT_EVENTS_PATH = join(homedir(), ".claude", "dashboard", "events.jsonl");
/** Claude Code session registry directory used to map session_id to PID and display name. */
export const DEFAULT_SESSIONS_DIR = join(homedir(), ".claude", "sessions");

const STATE_BY_HOOK_EVENT = {
  SessionStart: "started",
  UserPromptSubmit: "busy",
  Stop: "idle",
  SessionEnd: "ended",
};
const WAITING_NOTIFICATION_TYPE = "permission_prompt";

/** Returns the §3 session state a hook input maps to, or null when the hook carries no state change. */
export function stateForHook(hookInput) {
  if (hookInput.hook_event_name === "Notification") {
    return hookInput.notification_type === WAITING_NOTIFICATION_TYPE ? "waiting" : null;
  }
  return STATE_BY_HOOK_EVENT[hookInput.hook_event_name] ?? null;
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

function normalizeRegistryEntry(entry) {
  if (!Number.isInteger(entry.pid)) return null;
  return {
    pid: entry.pid,
    sessionId: typeof entry.sessionId === "string" ? entry.sessionId : null,
    name: typeof entry.name === "string" ? entry.name : null,
    cwd: typeof entry.cwd === "string" ? entry.cwd : null,
    status: typeof entry.status === "string" ? entry.status : null,
  };
}

/** Reads every <pid>.json in the session registry and returns the parseable entries as {pid, sessionId, name, cwd, status}. */
export function readSessionRegistry(sessionsDir = DEFAULT_SESSIONS_DIR) {
  let files;
  try {
    files = readdirSync(sessionsDir).filter((file) => file.endsWith(".json"));
  } catch {
    return [];
  }
  const entries = [];
  for (const file of files) {
    try {
      const entry = normalizeRegistryEntry(JSON.parse(readFileSync(join(sessionsDir, file), "utf8")));
      if (entry) entries.push(entry);
    } catch {
      continue;
    }
  }
  return entries;
}

/** Finds the Claude Code session registry entry whose sessionId matches, returning {pid, name} or null. */
export function lookupSessionRegistry(sessionId, sessionsDir = DEFAULT_SESSIONS_DIR) {
  const entry = readSessionRegistry(sessionsDir).find((candidate) => candidate.sessionId === sessionId);
  return entry ? { pid: entry.pid, name: entry.name } : null;
}

/** Finds the registry entry for a PID, returning {pid, sessionId, name, cwd, status} or null. */
export function lookupSessionRegistryByPid(pid, sessionsDir = DEFAULT_SESSIONS_DIR) {
  return readSessionRegistry(sessionsDir).find((candidate) => candidate.pid === pid) ?? null;
}

/** Walks up the process tree from the hook and returns the PID of the nearest `claude` process, or null. */
export function findClaudeAncestorPid(startPid = process.ppid, maxDepth = 6) {
  let pid = startPid;
  for (let depth = 0; depth < maxDepth && pid > 1; depth += 1) {
    let line;
    try {
      line = execFileSync("ps", ["-o", "ppid=,comm=", "-p", String(pid)], { encoding: "utf8" }).trim();
    } catch {
      return null;
    }
    const match = line.match(/^\s*(\d+)\s+(.*)$/);
    if (!match) return null;
    if (/(^|\/)claude(\.ex)?$/.test(match[2].trim())) return pid;
    pid = Number(match[1]);
  }
  return null;
}

/** Resolves {pid, name} for a hook input, preferring the session registry and falling back to the process tree. */
export function resolveSession(hookInput, options = {}) {
  const fromRegistry = lookupSessionRegistry(hookInput.session_id, options.sessionsDir);
  if (fromRegistry) return fromRegistry;
  const pid = (options.findPid ?? findClaudeAncestorPid)();
  return { pid, name: null };
}

/** Converts raw hook input plus resolved session identity into a §3 event, or null when the hook is not one we log. */
export function buildEvent(hookInput, identity, now = new Date()) {
  const ts = now.toISOString();
  const state = stateForHook(hookInput);
  if (state) {
    if (!Number.isInteger(identity.pid)) return null;
    return {
      ts,
      type: "session",
      session: identity.name ?? null,
      folder: basename(hookInput.cwd || ""),
      pid: identity.pid,
      state,
      role: null,
    };
  }
  if (hookInput.hook_event_name === "PostToolUse" && hookInput.tool_name === "SendMessage") {
    const input = hookInput.tool_input || {};
    if (typeof input.to !== "string") return null;
    return {
      ts,
      type: "message",
      from: identity.name ?? null,
      to: input.to,
      text: typeof input.message === "string" ? input.message : "",
      notify_on_idle: input.notify_when_idle === true,
    };
  }
  return null;
}

/** Appends one event as a JSON line, creating the directory, and returns false instead of throwing. */
export function appendEvent(eventsPath, event) {
  try {
    mkdirSync(dirname(eventsPath), { recursive: true });
    appendFileSync(eventsPath, `${JSON.stringify(event)}\n`);
    return true;
  } catch {
    return false;
  }
}

/** Entry point: reads the hook JSON from stdin, appends the matching event, and always exits 0 silently. */
export function main() {
  try {
    const hookInput = JSON.parse(readStdin());
    const eventsPath = process.env.CC_DASHBOARD_EVENTS || DEFAULT_EVENTS_PATH;
    const event = buildEvent(hookInput, resolveSession(hookInput));
    if (event) appendEvent(eventsPath, event);
  } catch {
    return;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  main();
}
