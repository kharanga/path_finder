import { createServer } from "node:http";
import { readFileSync, existsSync, mkdtempSync, realpathSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir, homedir } from "node:os";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawn } from "node:child_process";
import { parseEventLine } from "./schema.js";
import { createState, applyEvent, snapshot } from "./state.js";
import { findDeadSessions, isPidAlive } from "./liveness.js";
import { tailFile } from "./tail.js";

const HERE = dirname(fileURLToPath(import.meta.url));

export const DEFAULTS = {
  eventsPath: join(homedir(), ".claude", "dashboard", "events.jsonl"),
  frontendPath: join(HERE, "..", "frontend", "index.html"),
  port: 4747,
  host: "127.0.0.1",
  livenessIntervalMs: 5000,
  pollMs: 300,
  heartbeatMs: 15000,
  demo: false,
};

/** Parses CLI flags (--events, --frontend, --port, --host, --liveness-interval, --poll, --demo) into options. */
export function parseArgs(argv, defaults = DEFAULTS) {
  const options = { ...defaults };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--events") options.eventsPath = value, index += 1;
    else if (flag === "--frontend") options.frontendPath = value, index += 1;
    else if (flag === "--port") options.port = Number(value), index += 1;
    else if (flag === "--host") options.host = value, index += 1;
    else if (flag === "--liveness-interval") options.livenessIntervalMs = Number(value), index += 1;
    else if (flag === "--poll") options.pollMs = Number(value), index += 1;
    else if (flag === "--demo") options.demo = true;
    else throw new Error(`unknown flag ${flag}`);
  }
  return options;
}

/** Formats one SSE frame with an event name and a JSON payload. */
export function sseFrame(eventName, payload) {
  return `event: ${eventName}\ndata: ${JSON.stringify(payload)}\n\n`;
}

/** Creates the dashboard hub: in-memory state, connected SSE clients, and broadcast helpers. */
export function createHub(options = {}) {
  const state = createState(options.messageLimit);
  const clients = new Set();
  const stats = { linesRead: 0, malformedLines: 0, eventsApplied: 0 };

  const broadcast = (eventName, payload) => {
    const frame = sseFrame(eventName, payload);
    for (const client of clients) client.write(frame);
  };

  const ingestLine = (line, { replaying = false } = {}) => {
    stats.linesRead += 1;
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

  const runLivenessCheck = (now = new Date(), isAlive = options.isAlive ?? isPidAlive) => {
    const ended = findDeadSessions(state, now, isAlive);
    for (const event of ended) {
      applyEvent(state, event);
      broadcast("liveness", event);
    }
    return ended;
  };

  const addClient = (response) => {
    clients.add(response);
    response.write(sseFrame("snapshot", snapshot(state)));
    return () => clients.delete(response);
  };

  return { state, clients, stats, ingestLine, runLivenessCheck, addClient, broadcast };
}

/** Handles one HTTP request: GET / serves the page, GET /events streams SSE, GET /snapshot returns JSON. */
export function handleRequest(hub, options, request, response) {
  const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  if (request.method !== "GET") {
    response.writeHead(405, { "Content-Type": "text/plain" });
    response.end("method not allowed");
    return;
  }
  if (url.pathname === "/") {
    if (!existsSync(options.frontendPath)) {
      response.writeHead(404, { "Content-Type": "text/plain" });
      response.end(`frontend not found at ${options.frontendPath}`);
      return;
    }
    response.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" });
    response.end(readFileSync(options.frontendPath));
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
    response.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
    response.end(JSON.stringify({ ...snapshot(hub.state), stats: hub.stats }));
    return;
  }
  response.writeHead(404, { "Content-Type": "text/plain" });
  response.end("not found");
}

/** Starts the fake generator writing to a temp file and returns {eventsPath, child}. */
export function startDemoGenerator(extraArgs = []) {
  const eventsPath = join(mkdtempSync(join(tmpdir(), "cc-dashboard-demo-")), "events.jsonl");
  const child = spawn(process.execPath, [join(HERE, "fake.js"), "--out", eventsPath, ...extraArgs], { stdio: "ignore" });
  return { eventsPath, child };
}

/** Replays the events file, tails it, starts liveness checks, and listens; resolves to {server, hub, stop}. */
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
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(options.port, options.host, resolve);
  });
  const stop = () =>
    new Promise((resolve) => {
      stopTail();
      if (livenessTimer) clearInterval(livenessTimer);
      for (const client of hub.clients) client.end();
      if (demo) demo.child.kill("SIGTERM");
      server.close(() => resolve());
    });
  return { server, hub, options, stop };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const { hub, options: live, stop } = await startServer(options);
  const url = `http://${live.host}:${live.port}/`;
  console.log(`dashboard at ${url}`);
  console.log(`events file ${live.eventsPath}`);
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
