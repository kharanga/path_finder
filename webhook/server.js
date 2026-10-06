import { createServer } from "node:http";
import { readFileSync, existsSync, mkdtempSync, realpathSync, statSync, appendFileSync, mkdirSync } from "node:fs";
import { join, dirname, resolve, sep, extname } from "node:path";
import { tmpdir, homedir } from "node:os";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawn } from "node:child_process";
import { parseEventLine } from "./schema.js";
import { createState, applyEvent, snapshot } from "./state.js";
import { findDeadSessions, findStatusCorrections, isPidAlive, readRegistryStatus, DEFAULT_SESSIONS_DIR } from "./liveness.js";
import { tailFile } from "./tail.js";

const HERE = dirname(fileURLToPath(import.meta.url));

/** Default server options; every CLI flag overrides one of these. */
export const DEFAULTS = {
  eventsPath: join(homedir(), ".claude", "dashboard", "events.jsonl"),
  frontendDir: join(HERE, "..", "frontend"),
  sessionsDir: DEFAULT_SESSIONS_DIR,
  port: 4747,
  host: "127.0.0.1",
  livenessIntervalMs: 5000,
  pollMs: 300,
  heartbeatMs: 15000,
  messageLimit: 500,
  demo: false,
};

/** Content-Type by file extension for static files served from the frontend directory. */
export const CONTENT_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".txt": "text/plain; charset=utf-8",
};

/** Parses CLI flags (--events, --frontend, --sessions-dir, --port, --host, --liveness-interval, --poll, --demo) into options. */
export function parseArgs(argv, defaults = DEFAULTS) {
  const options = { ...defaults };
  const numeric = (flag, value) => {
    const parsed = Number(value);
    if (value === undefined || value === "" || Number.isNaN(parsed) || parsed < 0) throw new Error(`${flag} needs a non-negative number`);
    return parsed;
  };
  const text = (flag, value) => {
    if (value === undefined || value === "") throw new Error(`${flag} needs a value`);
    return value;
  };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--events") options.eventsPath = text(flag, value), index += 1;
    else if (flag === "--frontend") options.frontendDir = text(flag, value), index += 1;
    else if (flag === "--sessions-dir") options.sessionsDir = text(flag, value), index += 1;
    else if (flag === "--port") options.port = numeric(flag, value), index += 1;
    else if (flag === "--host") options.host = text(flag, value), index += 1;
    else if (flag === "--liveness-interval") options.livenessIntervalMs = numeric(flag, value), index += 1;
    else if (flag === "--poll") options.pollMs = numeric(flag, value), index += 1;
    else if (flag === "--demo") options.demo = true;
    else throw new Error(`unknown flag ${flag}`);
  }
  return options;
}

/** Formats one SSE frame with an event name and a JSON payload. */
export function sseFrame(eventName, payload) {
  return `event: ${eventName}\ndata: ${JSON.stringify(payload)}\n\n`;
}

/** Maps a URL path to a file inside frontendDir, or null when it escapes the directory or is not a regular file. */
export function resolveStaticFile(frontendDir, urlPath) {
  const root = resolve(frontendDir);
  let decoded;
  try {
    decoded = decodeURIComponent(urlPath);
  } catch {
    return null;
  }
  const relative = decoded === "/" ? "index.html" : decoded.replace(/^\/+/, "");
  const candidate = resolve(root, relative);
  if (candidate !== root && !candidate.startsWith(root + sep)) return null;
  let realRoot;
  let realCandidate;
  try {
    realRoot = realpathSync(root);
    realCandidate = realpathSync(candidate);
    if (!statSync(realCandidate).isFile()) return null;
  } catch {
    return null;
  }
  if (!realCandidate.startsWith(realRoot + sep)) return null;
  return { filePath: realCandidate, contentType: CONTENT_TYPES[extname(realCandidate).toLowerCase()] ?? "application/octet-stream" };
}

/** Creates the dashboard hub: in-memory state, connected SSE clients, ingestion, removal, liveness, and broadcast. */
export function createHub(options = {}) {
  const state = createState(options.messageLimit);
  const clients = new Set();
  const stats = { linesRead: 0, malformedLines: 0, eventsApplied: 0, livenessEnded: 0, statusCorrections: 0, removals: 0 };
  const selfWrittenLines = new Set();
  const isAlive = options.isAlive ?? isPidAlive;
  const readStatus = options.readStatus ?? ((pid) => readRegistryStatus(pid, options.sessionsDir ?? DEFAULT_SESSIONS_DIR));

  const broadcast = (eventName, payload) => {
    const frame = sseFrame(eventName, payload);
    for (const client of clients) client.write(frame);
  };

  const ingestLine = (line, { replaying = false } = {}) => {
    stats.linesRead += 1;
    if (selfWrittenLines.delete(line)) return state.sessions.get(JSON.parse(line).pid) ?? null;
    const event = parseEventLine(line);
    if (!event) {
      if (line.trim() !== "") stats.malformedLines += 1;
      return null;
    }
    const applied = applyEvent(state, event);
    stats.eventsApplied += 1;
    if (!replaying) broadcast(event.type, applied);
    return applied;
  };

  const removeSession = (pid, now = new Date()) => {
    const current = state.sessions.get(pid);
    if (!current) return null;
    const event = { ts: now.toISOString(), type: "session", session: current.session, folder: current.folder, pid, state: "removed", role: current.role };
    const line = JSON.stringify(event);
    if (options.eventsPath) {
      mkdirSync(dirname(options.eventsPath), { recursive: true });
      appendFileSync(options.eventsPath, `${line}\n`);
      selfWrittenLines.add(line);
    }
    const applied = applyEvent(state, event);
    stats.eventsApplied += 1;
    stats.removals += 1;
    broadcast("session", applied);
    return applied;
  };

  const runLivenessCheck = (now = new Date()) => {
    const ended = findDeadSessions(state, now, isAlive);
    for (const event of ended) {
      applyEvent(state, event);
      stats.livenessEnded += 1;
      broadcast("liveness", event);
    }
    const corrections = findStatusCorrections(state, now, readStatus);
    for (const event of corrections) {
      applyEvent(state, event);
      stats.statusCorrections += 1;
      broadcast("session", event);
    }
    return { ended, corrections };
  };

  const addClient = (response) => {
    clients.add(response);
    response.write(sseFrame("snapshot", snapshot(state)));
    return () => clients.delete(response);
  };

  return { state, clients, stats, ingestLine, removeSession, runLivenessCheck, addClient, broadcast };
}

/** Handles one HTTP request: /events streams SSE, /snapshot returns JSON, POST /sessions/<pid>/remove removes a session, everything else is a static file from frontendDir. */
export function handleRequest(hub, options, request, response) {
  const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  const removeMatch = url.pathname.match(/^\/sessions\/(\d+)\/remove$/);
  if (removeMatch) {
    if (request.method !== "POST") {
      response.writeHead(405, { "Content-Type": "text/plain", Allow: "POST" });
      response.end("method not allowed");
      return;
    }
    const removed = hub.removeSession(Number(removeMatch[1]));
    response.writeHead(removed ? 204 : 404, removed ? {} : { "Content-Type": "text/plain" });
    response.end(removed ? undefined : "unknown pid");
    return;
  }
  if (request.method !== "GET" && request.method !== "HEAD") {
    response.writeHead(405, { "Content-Type": "text/plain" });
    response.end("method not allowed");
    return;
  }
  if (url.pathname === "/events") {
    response.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-store",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    });
    response.write(": connected\n\n");
    const remove = hub.addClient(response);
    const heartbeat = setInterval(() => response.write(": ping\n\n"), options.heartbeatMs);
    request.on("close", () => {
      clearInterval(heartbeat);
      remove();
    });
    return;
  }
  if (url.pathname === "/snapshot") {
    response.writeHead(200, { "Content-Type": CONTENT_TYPES[".json"], "Cache-Control": "no-store" });
    response.end(JSON.stringify({ ...snapshot(hub.state), stats: hub.stats }));
    return;
  }
  const file = resolveStaticFile(options.frontendDir, url.pathname);
  if (!file) {
    response.writeHead(404, { "Content-Type": "text/plain" });
    response.end(url.pathname === "/" ? `frontend not found at ${options.frontendDir}` : "not found");
    return;
  }
  response.writeHead(200, { "Content-Type": file.contentType, "Cache-Control": "no-store" });
  response.end(request.method === "HEAD" ? undefined : readFileSync(file.filePath));
}

/** Starts the fake generator writing to a temp file and returns {eventsPath, child}. */
export function startDemoGenerator(extraArgs = []) {
  const eventsPath = join(mkdtempSync(join(tmpdir(), "cc-dashboard-demo-")), "events.jsonl");
  const child = spawn(process.execPath, [join(HERE, "fake.js"), "--out", eventsPath, ...extraArgs], { stdio: "ignore" });
  return { eventsPath, child };
}

/** Replays the events file, tails it, starts liveness checks, and listens; resolves to {server, hub, options, stop}. */
export async function startServer(overrides = {}) {
  const options = { ...DEFAULTS, ...overrides };
  let demo = null;
  if (options.demo) {
    demo = startDemoGenerator();
    options.eventsPath = demo.eventsPath;
  }
  const hub = createHub(options);
  let replaying = true;
  const stopTail = tailFile(options.eventsPath, (line) => hub.ingestLine(line, { replaying }), {
    pollMs: options.pollMs,
    onReplayComplete: () => {
      replaying = false;
    },
  });
  let livenessTimer = null;
  if (options.livenessIntervalMs > 0) {
    hub.runLivenessCheck();
    livenessTimer = setInterval(() => hub.runLivenessCheck(), options.livenessIntervalMs);
  }
  const server = createServer((request, response) => handleRequest(hub, options, request, response));
  await new Promise((resolvePromise, reject) => {
    server.once("error", reject);
    server.listen(options.port, options.host, resolvePromise);
  });
  const stop = () =>
    new Promise((resolvePromise) => {
      stopTail();
      if (livenessTimer) clearInterval(livenessTimer);
      for (const client of hub.clients) client.end();
      if (demo) demo.child.kill("SIGTERM");
      server.close(() => resolvePromise());
    });
  return { server, hub, options, stop };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const { hub, options: live, stop } = await startServer(options);
  console.log(`dashboard at http://${live.host}:${live.port}/`);
  console.log(`events file ${live.eventsPath}`);
  if (!existsSync(join(live.frontendDir, "index.html"))) console.log(`warning: no index.html in ${live.frontendDir}`);
  console.log(`replayed ${hub.stats.eventsApplied} events, skipped ${hub.stats.malformedLines} malformed lines`);
  const shutdown = () => stop().then(() => process.exit(0));
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
