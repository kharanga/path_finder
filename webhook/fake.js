import { appendFileSync, mkdirSync, writeFileSync, realpathSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { homedir } from "node:os";
import { spawn } from "node:child_process";
import { pathToFileURL } from "node:url";
import { validateEvent } from "./schema.js";
import { createState, applyEvent, snapshot } from "./state.js";

/** The real hooks output file; the generator refuses to write here. */
export const REAL_EVENTS_PATH = join(homedir(), ".claude", "dashboard", "events.jsonl");
/** Recipient name used for the message whose session never appears on the ring. */
export const GHOST_RECIPIENT = "ghost-session-00";
/** Name a session takes mid-stream in the rename scenario, same PID, mirroring Claude Code's auto-rename. */
export const RENAMED_NAME = "manager-drives-feature-work";
/** Virtual seconds between a silent death and its liveness entry in fixture mode. */
export const DEFAULT_LIVENESS_DELAY_SECONDS = 5;

/** Start folders for the fake sessions, in start order; repeats make same-folder siblings. */
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

/** Parses CLI flags (--out, --fixture, --speed, --sessions, --seed, --instant, --duration, --snapshot-until) into options. */
export function parseArgs(argv) {
  const options = {
    out: null,
    fixture: null,
    speed: 1,
    sessions: 15,
    seed: 42,
    instant: false,
    durationSeconds: null,
    snapshotUntilSeconds: 0,
    startTime: null,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--out") options.out = value, index += 1;
    else if (flag === "--fixture") options.fixture = value, index += 1;
    else if (flag === "--speed") options.speed = Number(value), index += 1;
    else if (flag === "--sessions") options.sessions = Number(value), index += 1;
    else if (flag === "--seed") options.seed = Number(value), index += 1;
    else if (flag === "--duration") options.durationSeconds = Number(value), index += 1;
    else if (flag === "--snapshot-until") options.snapshotUntilSeconds = Number(value), index += 1;
    else if (flag === "--start-time") options.startTime = value, index += 1;
    else if (flag === "--instant") options.instant = true;
    else throw new Error(`unknown flag ${flag}`);
  }
  if (!options.out && !options.fixture) throw new Error("--out <path> or --fixture <path> is required");
  if (options.out && options.fixture) throw new Error("use either --out or --fixture, not both");
  if (options.out && resolve(options.out) === REAL_EVENTS_PATH) throw new Error("refusing to write to the real events file");
  if (!(options.speed > 0)) throw new Error("--speed must be a positive number");
  if (options.fixture) options.instant = true;
  if (options.instant && options.durationSeconds === null) options.durationSeconds = 60;
  if (options.startTime !== null && Number.isNaN(Date.parse(options.startTime))) throw new Error("--start-time must be ISO 8601");
  return options;
}

/** Creates the generator: fake sessions, a virtual or real clock, validated emission, and placeholder processes. */
export function createGenerator(options, deps = {}) {
  const random = createRandom(options.seed);
  const startMs = options.startTime ? Date.parse(options.startTime) : (deps.now ?? (() => new Date()))().getTime();
  const nowFn = deps.now ?? (() => new Date());
  const entries = [];
  const children = [];
  const sessions = [];
  let fakePidCounter = 70000;
  let virtualMs = 0;

  const currentMs = () => (options.instant ? startMs + virtualMs : nowFn().getTime());
  const advance = (ms) => {
    virtualMs += ms;
  };

  const record = (eventName, data) => {
    const entry = { atMs: currentMs() - startMs, event: eventName, data };
    entries.push(entry);
    if (deps.write) deps.write(entry);
    else if (options.out && eventName !== "liveness") appendFileSync(options.out, `${JSON.stringify(data)}\n`);
    return entry;
  };

  const emit = (event) => {
    const check = validateEvent(event);
    if (!check.ok) throw new Error(`invalid fake event: ${check.errors.join("; ")}`);
    record(event.type, event);
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
    emit({ ts: new Date(currentMs()).toISOString(), type: "session", session: session.name, folder: session.folder, pid: session.pid, state, role: session.role });

  const startSession = (folder, { anonymous = false } = {}) => {
    const { pid, child } = allocatePid();
    const name = anonymous ? null : `${folder.replace(/_/g, "-")}-${random.hex2()}`;
    const session = { name, folder, pid, child, role: null, state: "started" };
    sessions.push(session);
    sessionEvent(session, "started");
    return session;
  };

  const setState = (session, state) => {
    session.state = state;
    sessionEvent(session, state);
  };

  const nameSession = (session) => {
    session.name = `${session.folder.replace(/_/g, "-")}-${random.hex2()}`;
    sessionEvent(session, session.state);
  };

  const renameSession = (session, newName) => {
    session.name = newName;
    sessionEvent(session, session.state);
    return session;
  };

  const endSession = (session) => {
    setState(session, "ended");
    if (session.child) session.child.kill("SIGTERM");
  };

  const removeSession = (session) => {
    session.state = "removed";
    sessionEvent(session, "removed");
  };

  const killSilently = (session) => {
    session.state = "dead";
    if (session.child) session.child.kill("SIGKILL");
  };

  const emitLiveness = (session) => {
    if (!options.instant) return null;
    const data = { ts: new Date(currentMs()).toISOString(), type: "session", session: session.name, folder: session.folder, pid: session.pid, state: "ended", role: session.role };
    return record("liveness", data);
  };

  const sendMessage = (from, to, notifyOnIdle) =>
    emit({
      ts: new Date(currentMs()).toISOString(),
      type: "message",
      from: from.name,
      to: typeof to === "string" ? to : to.name,
      text: random.pick(MESSAGE_TEXTS),
      notify_on_idle: notifyOnIdle,
    });

  const live = () => sessions.filter((session) => !["ended", "dead", "removed"].includes(session.state) && session.name !== null);

  const shutdown = () => {
    for (const child of children) {
      try {
        child.kill("SIGTERM");
      } catch {
        continue;
      }
    }
  };

  return { random, sessions, entries, live, advance, startSession, setState, nameSession, renameSession, endSession, removeSession, killSilently, emitLiveness, sendMessage, shutdown, emit };
}

/** Plays the scripted scenario, then random activity until the duration ends or SIGINT; resolves when done. */
export async function runScenario(generator, options, sleepFn) {
  const wait = async (seconds) => {
    if (options.instant) {
      generator.advance(seconds * 1000);
      return;
    }
    await sleepFn((seconds * 1000) / options.speed);
  };
  const busyThenIdle = async (session, busySeconds) => {
    generator.setState(session, "busy");
    await wait(busySeconds);
    generator.setState(session, "idle");
  };
  const virtualElapsed = () => generator.entries.length === 0 ? 0 : generator.entries[generator.entries.length - 1].atMs / 1000;

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

  const population = generator.live();

  if (population.length >= 2) {
    const [sender, recipient] = population;
    generator.sendMessage(sender, recipient, true);
    await wait(2);
    await busyThenIdle(recipient, 4);
  }

  if (population.length >= 3) {
    const [sender, , recipient] = population;
    generator.sendMessage(sender, recipient, true);
    await wait(1);
    generator.setState(recipient, "busy");
    await wait(2);
    generator.setState(recipient, "waiting");
    await wait(4);
    generator.setState(recipient, "busy");
    await wait(2);
    generator.setState(recipient, "idle");
  }

  if (population.length >= 1) {
    generator.sendMessage(population[0], GHOST_RECIPIENT, true);
    await wait(3);
  }

  if (population.length >= 5) {
    const anonymous = generator.startSession(population[4].folder, { anonymous: true });
    await wait(1);
    generator.setState(anonymous, "busy");
    generator.sendMessage(anonymous, population[0], false);
    await wait(1);
    await busyThenIdle(population[0], 1);
    generator.nameSession(anonymous);
    await wait(1);
    generator.setState(anonymous, "idle");
  }

  if (population.length >= 2) {
    const renaming = population[1];
    const partner = population[0];
    generator.sendMessage(renaming, partner, false);
    await wait(1);
    await busyThenIdle(partner, 1);
    generator.renameSession(renaming, RENAMED_NAME);
    await wait(1);
    generator.sendMessage(partner, renaming, true);
    await wait(1);
    await busyThenIdle(renaming, 2);
    generator.sendMessage(renaming, partner, false);
    await wait(1);
  }

  if (population.length >= 4) {
    const restarting = population[3];
    generator.endSession(restarting);
    await wait(2);
    const reborn = generator.startSession(restarting.folder);
    await busyThenIdle(reborn, 2);
  }

  if (population.length >= 6) {
    const dying = population[5];
    generator.setState(dying, "busy");
    await wait(1);
    generator.killSilently(dying);
    await wait(DEFAULT_LIVENESS_DELAY_SECONDS);
    generator.emitLiveness(dying);
  }

  if (population.length >= 7) {
    const removedForGood = population[6];
    generator.setState(removedForGood, "ended");
    await wait(1);
    generator.removeSession(removedForGood);
    await wait(2);
    const removedByMistake = population[0];
    generator.removeSession(removedByMistake);
    await wait(3);
    await busyThenIdle(removedByMistake, 2);
  }

  if (population.length >= 8) {
    const [sender, , , , , , , recipient] = population;
    generator.sendMessage(sender, recipient, true);
    await wait(1);
    generator.setState(recipient, "busy");
    await wait(2);
    generator.killSilently(recipient);
    await wait(DEFAULT_LIVENESS_DELAY_SECONDS);
    generator.emitLiveness(recipient);
  }

  const startedRandomAt = options.instant ? virtualElapsed() : Date.now() / 1000;
  const elapsedSinceRandomStart = () => (options.instant ? virtualElapsed() : Date.now() / 1000) - startedRandomAt;
  while (options.durationSeconds === null || elapsedSinceRandomStart() < options.durationSeconds) {
    const actors = generator.live();
    if (actors.length === 0) break;
    const actor = generator.random.pick(actors);
    const roll = generator.random.next();
    if (roll < 0.5) {
      await busyThenIdle(actor, generator.random.int(2, 6));
    } else if (roll < 0.6) {
      generator.setState(actor, "busy");
      await wait(1);
      generator.setState(actor, "waiting");
      await wait(generator.random.int(2, 5));
      generator.setState(actor, "busy");
      await wait(1);
      generator.setState(actor, "idle");
    } else {
      const targets = actors.filter((candidate) => candidate !== actor);
      if (targets.length === 0) {
        await wait(1);
        continue;
      }
      const recipient = generator.random.pick(targets);
      generator.sendMessage(actor, recipient, generator.random.next() < 0.3);
      await wait(1);
      await busyThenIdle(recipient, generator.random.int(1, 4));
    }
    await wait(generator.random.int(1, 3));
  }
}

/** Converts recorded entries into the page fixture {snapshot, events}, folding entries up to snapshotUntilSeconds into the snapshot and dividing delays by speed. */
export function buildFixture(entries, snapshotUntilSeconds = 0, speed = 1) {
  const cutoffMs = snapshotUntilSeconds * 1000;
  const state = createState();
  const events = [];
  let previousMs = cutoffMs;
  for (const entry of entries) {
    if (entry.atMs <= cutoffMs) {
      applyEvent(state, entry.data);
      continue;
    }
    events.push({ delayMs: Math.round((entry.atMs - previousMs) / speed), event: entry.event, data: entry.data });
    previousMs = entry.atMs;
  }
  return { snapshot: snapshot(state), events };
}

const sleep = (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms));

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const target = options.out ?? options.fixture;
  mkdirSync(dirname(resolve(target)), { recursive: true });
  if (options.out) writeFileSync(options.out, "");
  const generator = createGenerator(options);
  const stop = () => {
    generator.shutdown();
    process.exit(0);
  };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  process.on("exit", () => generator.shutdown());
  await runScenario(generator, options, sleep);
  if (options.fixture) {
    writeFileSync(options.fixture, `${JSON.stringify(buildFixture(generator.entries, options.snapshotUntilSeconds, options.speed), null, 2)}\n`);
  }
  generator.shutdown();
}

if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
