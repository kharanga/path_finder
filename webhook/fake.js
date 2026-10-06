import { appendFileSync, mkdirSync, writeFileSync, realpathSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { homedir } from "node:os";
import { spawn } from "node:child_process";
import { pathToFileURL } from "node:url";
import { validateEvent } from "./schema.js";

export const REAL_EVENTS_PATH = join(homedir(), ".claude", "dashboard", "events.jsonl");

export const FOLDERS = [
  "listings", "listings", "listings",
  "tag_analyzer",
  "path_finder", "path_finder", "path_finder",
  "back_to_the_future",
  "graphify",
  "notes",
  "infra",
  "mobile_app",
  "data_pipeline",
  "docs_site",
  "experiments",
];

const MESSAGE_TEXTS = [
  "L16 is ready, look at it",
  "handoff/webhook/ready.md is up, please review",
  "tests pass on my side, your turn",
  "can you check docs/overview.md section 7",
  "blocked on the settings snippet, see ready.md",
  "PASS, moving to the next task",
  "review.md has two failures, both in hooks.md",
  "restarting to pick up the new hooks",
];

/** Deterministic pseudo-random generator (mulberry32) so a seed reproduces the same stream. */
export function createRandom(seed) {
  let value = seed >>> 0;
  const next = () => {
    value = (value + 0x6d2b79f5) >>> 0;
    let t = value;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    int: (min, max) => min + Math.floor(next() * (max - min + 1)),
    pick: (items) => items[Math.floor(next() * items.length)],
    hex2: () => Math.floor(next() * 256).toString(16).padStart(2, "0"),
  };
}

/** Parses CLI flags (--out, --speed, --sessions, --seed, --instant, --duration) into options. */
export function parseArgs(argv) {
  const options = { out: null, speed: 1, sessions: 15, seed: 42, instant: false, durationSeconds: null };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--out") options.out = value, index += 1;
    else if (flag === "--speed") options.speed = Number(value), index += 1;
    else if (flag === "--sessions") options.sessions = Number(value), index += 1;
    else if (flag === "--seed") options.seed = Number(value), index += 1;
    else if (flag === "--duration") options.durationSeconds = Number(value), index += 1;
    else if (flag === "--instant") options.instant = true;
    else throw new Error(`unknown flag ${flag}`);
  }
  if (!options.out) throw new Error("--out <path> is required");
  if (resolve(options.out) === REAL_EVENTS_PATH) throw new Error("refusing to write to the real events file");
  if (!(options.speed > 0)) throw new Error("--speed must be a positive number");
  return options;
}

/** Creates the generator: holds fake sessions, writes validated events, and owns the placeholder processes. */
export function createGenerator(options, deps = {}) {
  const random = createRandom(options.seed);
  const write = deps.write ?? ((line) => appendFileSync(options.out, line));
  const now = deps.now ?? (() => new Date());
  const children = [];
  const sessions = [];
  let fakePidCounter = 70000;
  let simulatedMs = 0;

  const timestamp = () => {
    if (options.instant) {
      simulatedMs += 1000;
      return new Date(now().getTime() + simulatedMs).toISOString();
    }
    return now().toISOString();
  };

  const emit = (event) => {
    const check = validateEvent(event);
    if (!check.ok) throw new Error(`invalid fake event: ${check.errors.join("; ")}`);
    write(`${JSON.stringify(event)}\n`);
    return event;
  };

  const allocatePid = () => {
    if (options.instant || deps.noChildren) {
      fakePidCounter += random.int(1, 40);
      return { pid: fakePidCounter, child: null };
    }
    const child = spawn("sleep", ["86400"], { stdio: "ignore" });
    children.push(child);
    return { pid: child.pid, child };
  };

  const sessionEvent = (session, state) =>
    emit({ ts: timestamp(), type: "session", session: session.name, folder: session.folder, pid: session.pid, state, role: session.role });

  const startSession = (folder) => {
    const { pid, child } = allocatePid();
    const session = { name: `${folder.replace(/_/g, "-")}-${random.hex2()}`, folder, pid, child, role: null, state: "started" };
    sessions.push(session);
    sessionEvent(session, "started");
    return session;
  };

  const setState = (session, state) => {
    session.state = state;
    sessionEvent(session, state);
  };

  const endSession = (session) => {
    setState(session, "ended");
    if (session.child) session.child.kill("SIGTERM");
  };

  const killSilently = (session) => {
    session.state = "dead";
    if (session.child) session.child.kill("SIGKILL");
  };

  const sendMessage = (from, to, notifyOnIdle) =>
    emit({ ts: timestamp(), type: "message", from: from.name, to: to.name, text: random.pick(MESSAGE_TEXTS), notify_on_idle: notifyOnIdle });

  const live = () => sessions.filter((session) => session.state !== "ended" && session.state !== "dead");

  const shutdown = () => {
    for (const child of children) {
      try {
        child.kill("SIGTERM");
      } catch {
        continue;
      }
    }
  };

  return { random, sessions, live, startSession, setState, endSession, killSilently, sendMessage, shutdown, emit };
}

/** Plays the scripted scenario, then random activity until duration or SIGINT; resolves when done. */
export async function runScenario(generator, options, sleepFn) {
  const wait = (seconds) => (options.instant ? Promise.resolve() : sleepFn((seconds * 1000) / options.speed));
  const busyThenIdle = async (session, busySeconds) => {
    generator.setState(session, "busy");
    await wait(busySeconds);
    generator.setState(session, "idle");
  };

  await wait(3);

  const folders = FOLDERS.slice(0, Math.max(0, options.sessions));
  for (const folder of folders) {
    const session = generator.startSession(folder);
    await wait(0.5);
    await busyThenIdle(session, generator.random.int(1, 3));
    const others = generator.live().filter((candidate) => candidate !== session);
    if (others.length >= 1 && generator.random.next() < 0.5) {
      const recipient = generator.random.pick(others);
      generator.sendMessage(session, recipient, false);
      await wait(1);
      await busyThenIdle(recipient, 1);
    }
  }

  const everyone = generator.live();
  if (everyone.length >= 2) {
    const [sender, recipient] = [everyone[0], everyone[1]];
    generator.sendMessage(sender, recipient, true);
    await wait(2);
    await busyThenIdle(recipient, 4);
  }

  if (everyone.length >= 3) {
    const restarting = everyone[2];
    generator.endSession(restarting);
    await wait(2);
    const reborn = generator.startSession(restarting.folder);
    await busyThenIdle(reborn, 2);
  }

  if (generator.live().length >= 4) {
    const dying = generator.live()[3];
    generator.setState(dying, "busy");
    await wait(1);
    generator.killSilently(dying);
  }

  if (options.instant) return;

  const deadline = options.durationSeconds ? Date.now() + options.durationSeconds * 1000 : Infinity;
  while (Date.now() < deadline) {
    const population = generator.live();
    if (population.length === 0) break;
    const actor = generator.random.pick(population);
    const roll = generator.random.next();
    if (roll < 0.6) {
      await busyThenIdle(actor, generator.random.int(2, 6));
    } else {
      const targets = population.filter((candidate) => candidate !== actor);
      if (targets.length === 0) continue;
      const recipient = generator.random.pick(targets);
      const notify = generator.random.next() < 0.3;
      generator.sendMessage(actor, recipient, notify);
      await wait(1);
      await busyThenIdle(recipient, generator.random.int(1, 4));
    }
    await wait(generator.random.int(1, 3));
  }
}

const sleep = (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms));

async function main() {
  const options = parseArgs(process.argv.slice(2));
  mkdirSync(dirname(resolve(options.out)), { recursive: true });
  writeFileSync(options.out, "");
  const generator = createGenerator(options);
  const stop = () => {
    generator.shutdown();
    process.exit(0);
  };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  process.on("exit", () => generator.shutdown());
  await runScenario(generator, options, sleep);
  generator.shutdown();
}

if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
