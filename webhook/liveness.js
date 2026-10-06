import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { SESSION_STATES } from "./schema.js";

export const SOCKET_DIR = "/tmp/cc-socks";
export const DEFAULT_SESSIONS_DIR = join(homedir(), ".claude", "sessions");

/** Returns true when a process with this PID exists, using signal 0 and treating EPERM as alive. */
export function isPidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code === "EPERM";
  }
}

/** Secondary liveness hint: whether Claude Code's messaging socket for this PID still exists. */
export function hasSocket(pid, socketDir = SOCKET_DIR) {
  return existsSync(join(socketDir, `${pid}.sock`));
}

/** Reads ~/.claude/sessions/<pid>.json and returns {status, name, statusUpdatedAt} or null when missing or unreadable. */
export function readRegistryStatus(pid, sessionsDir = DEFAULT_SESSIONS_DIR) {
  try {
    const entry = JSON.parse(readFileSync(join(sessionsDir, `${pid}.json`), "utf8"));
    return {
      status: typeof entry.status === "string" ? entry.status : null,
      name: typeof entry.name === "string" ? entry.name : null,
      statusUpdatedAt: Number.isFinite(entry.statusUpdatedAt) ? entry.statusUpdatedAt : null,
    };
  } catch {
    return null;
  }
}

/** Finds live sessions whose process is gone and returns a synthetic ended event for each. */
export function findDeadSessions(state, now = new Date(), isAlive = isPidAlive) {
  const ended = [];
  for (const session of state.sessions.values()) {
    if (session.state === "ended") continue;
    if (isAlive(session.pid)) continue;
    ended.push({ ...session, ts: now.toISOString(), state: "ended" });
  }
  return ended;
}

/** Compares hook state with the registry and returns corrective session events where the registry is newer and disagrees. */
export function findStatusCorrections(state, now = new Date(), readStatus = readRegistryStatus) {
  const corrections = [];
  for (const session of state.sessions.values()) {
    if (session.state === "ended") continue;
    const registry = readStatus(session.pid);
    if (!registry) continue;
    const registryIsNewer = registry.statusUpdatedAt !== null && registry.statusUpdatedAt > Date.parse(session.ts);
    const stateDisagrees = SESSION_STATES.includes(registry.status) && registry.status !== "ended" && registry.status !== session.state;
    const nameMissing = session.session === null && registry.name !== null;
    if (!(registryIsNewer && stateDisagrees) && !nameMissing) continue;
    corrections.push({
      ...session,
      ts: now.toISOString(),
      session: session.session ?? registry.name,
      state: registryIsNewer && stateDisagrees ? registry.status : session.state,
    });
  }
  return corrections;
}
