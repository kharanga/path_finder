import { basename, dirname } from "node:path";
import { mkdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { SESSION_STATES } from "./schema.js";
import { appendEvent, findClaudeAncestorPid, lookupSessionRegistryByPid, DEFAULT_EVENTS_PATH, DEFAULT_ROLES_PATH } from "./hooks/dashboard-hook.js";

const ROLE_PATTERN = /^[A-Za-z0-9][A-Za-z0-9 _-]{0,39}$/;

/** Validates the role argument: 1 to 40 characters of letters, digits, space, underscore, or dash. */
export function parseRole(argv) {
  const role = (argv[0] ?? "").trim();
  if (!ROLE_PATTERN.test(role)) throw new Error("usage: declare-role.js <role>   (1-40 letters, digits, spaces, _ or -)");
  return role;
}

/** Resolves the calling session from the process tree and registry, returning {pid, name, cwd, folder, state} or throwing. */
export function resolveCallingSession(options = {}) {
  const pid = (options.findPid ?? findClaudeAncestorPid)();
  if (!Number.isInteger(pid)) throw new Error("declare-role: no claude process found above this one");
  const entry = (options.lookup ?? lookupSessionRegistryByPid)(pid);
  if (!entry) throw new Error(`declare-role: no registry entry for claude pid ${pid}`);
  const state = SESSION_STATES.includes(entry.status) && entry.status !== "ended" ? entry.status : "busy";
  return { pid, name: entry.name, cwd: entry.cwd, folder: basename(entry.cwd || ""), state };
}

/** Saves the role for a start folder in roles.json so the hook re-applies it on later sessions; returns false on write failure. */
export function saveRole(rolesPath, cwd, role) {
  if (typeof cwd !== "string" || cwd === "") return false;
  let roles = {};
  try {
    roles = JSON.parse(readFileSync(rolesPath, "utf8"));
    if (roles === null || typeof roles !== "object" || Array.isArray(roles)) roles = {};
  } catch {
    roles = {};
  }
  roles[cwd] = role;
  try {
    mkdirSync(dirname(rolesPath), { recursive: true });
    writeFileSync(rolesPath, `${JSON.stringify(roles, null, 2)}\n`);
    return true;
  } catch {
    return false;
  }
}

/** Builds the session event that carries the declared role. */
export function buildRoleEvent(session, role, now = new Date()) {
  return { ts: now.toISOString(), type: "session", session: session.name, folder: session.folder, pid: session.pid, state: session.state, role };
}

/** Entry point: declares the role for the calling session; exit 0 silently, or exit 1 with one stderr line. */
export function main(argv = process.argv.slice(2)) {
  try {
    const role = parseRole(argv);
    const session = resolveCallingSession();
    const eventsPath = process.env.CC_DASHBOARD_EVENTS || DEFAULT_EVENTS_PATH;
    const rolesPath = process.env.CC_DASHBOARD_ROLES || DEFAULT_ROLES_PATH;
    if (!appendEvent(eventsPath, buildRoleEvent(session, role))) throw new Error(`declare-role: cannot write ${eventsPath}`);
    if (!saveRole(rolesPath, session.cwd, role)) throw new Error(`declare-role: cannot write ${rolesPath}`);
    return 0;
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    return 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  process.exit(main());
}
