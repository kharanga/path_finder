import { existsSync } from "node:fs";
import { join } from "node:path";

export const SOCKET_DIR = "/tmp/cc-socks";

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
