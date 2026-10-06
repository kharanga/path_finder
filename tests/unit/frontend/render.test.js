import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { installDomStub, uninstallDomStub } from "../../helpers/dom-stub.js";
import { createState, applySnapshot, applyEvent } from "../../../frontend/state.js";

const NOW = 1_000_000;
const fixture = (name) => JSON.parse(readFileSync(new URL(`../../../frontend/fixtures/${name}.json`, import.meta.url), "utf8"));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let createRenderer;

test.before(async () => {
  installDomStub();
  ({ createRenderer } = await import("../../../frontend/render.js"));
});
test.after(() => uninstallDomStub());

const setup = (options) => {
  const svg = installDomStub(options?.media);
  const draw = createRenderer(svg, options);
  return { svg, draw, q: (s) => svg.querySelector(s), qa: (s) => svg.querySelectorAll(s) };
};
const replay = (draw, name, state = createState()) => {
  const fx = fixture(name);
  applySnapshot(state, fx.snapshot, NOW);
  draw(state);
  for (const step of fx.events) {
    applyEvent(state, step.event, step.data, NOW);
    draw(state);
  }
  return state;
};

test("empty state shows the dashed ring and the empty label; bodies hide it", () => {
  const { svg, draw, q, qa } = setup({ reducedMotion: true });
  assert.equal(svg.getAttribute("viewBox"), "0 0 1360 1000");
  draw(createState());
  assert.equal(q(".empty-label").textContent, "No sessions running");
  assert.equal(q(".empty-label").classList.contains("hidden"), false);
  assert.equal(q(".ring").classList.contains("empty"), true);
  const state = createState();
  applySnapshot(state, fixture("few").snapshot, NOW);
  draw(state);
  assert.equal(qa(".body").length, 5);
  assert.equal(q(".empty-label").classList.contains("hidden"), true);
  assert.equal(q(".ring").classList.contains("empty"), false);
});

test("bodies carry state, folder, labels, roles, tooltips, and accessibility attributes", () => {
  const { draw, q } = setup({ reducedMotion: true });
  const state = createState();
  applySnapshot(state, fixture("few").snapshot, NOW);
  draw(state);
  const body = q('.body[data-pid="30111"]');
  assert.equal(body.dataset.state, "busy");
  assert.equal(body.dataset.folder, "tag-analyzer");
  assert.equal(body.querySelector(".role").textContent, "validator");
  assert.equal(body.querySelector("title").textContent, "tag-analyzer-63 (validator) in tag-analyzer");
  assert.equal(body.getAttribute("aria-label"), "tag-analyzer-63, busy, validator, folder tag-analyzer");
  assert.equal(body.getAttribute("tabindex"), "0");
  assert.equal(q('.body[data-pid="29904"] .role').classList.contains("hidden"), true);
  assert.equal(q('.body[data-pid="30444"] .name').textContent, "pid 30444");
});

test("reduced motion: particles appear arrived at the recipient and threads appear fully drawn, then vanish at once", async () => {
  const { draw, q, qa } = setup({ reducedMotion: true, lingerMs: 60000 });
  const state = createState();
  const fx = fixture("messages");
  applySnapshot(state, fx.snapshot, NOW);
  draw(state);
  assert.equal(qa(".particle").length, 0);
  applyEvent(state, "message", fx.events[0].data, NOW);
  draw(state);
  const particle = q(".particle");
  assert.equal(particle.dataset.messageIndex, "1");
  assert.equal(particle.classList.contains("notify"), true);
  assert.equal(particle.classList.contains("arrived"), true);
  assert.equal(particle.querySelector("animateMotion"), null);
  assert.equal(q(".thread").getAttribute("data-thread-id"), "1");
  assert.equal(q(".thread").getAttribute("stroke-dashoffset"), "0");
  applyEvent(state, "session", fx.events[4].data, NOW);
  draw(state);
  assert.equal(q(".thread").classList.contains("snapping"), true);
  await sleep(5);
  assert.equal(qa(".thread").length, 0);
});

test("full motion: particles animate along their own path and threads draw on from the sender", async () => {
  const { draw, q } = setup({ reducedMotion: false, travelMs: 5, lingerMs: 60000 });
  const state = createState();
  const fx = fixture("messages");
  applySnapshot(state, fx.snapshot, NOW);
  draw(state);
  applyEvent(state, "message", fx.events[0].data, NOW);
  draw(state);
  const motion = q(".particle-dot").children[0];
  assert.equal(motion.tagName, "animateMotion");
  assert.equal(motion.getAttribute("dur"), "5ms");
  assert.equal(motion.children[0].getAttribute("href"), `#${q(".particle-path").getAttribute("id")}`);
  assert.equal(q(".particle").classList.contains("arrived"), false);
  const thread = q(".thread");
  assert.ok(Number(thread.getAttribute("stroke-dasharray")) > 0);
  assert.equal(thread.getAttribute("stroke-dashoffset"), "0");
  assert.equal(thread.classList.contains("drawing"), false);
  await sleep(40);
  assert.equal(q(".particle").classList.contains("arrived"), true);
});

test("reduced motion defaults from matchMedia when no override is given", () => {
  const { draw, q } = setup({ media: { reducedMotion: true }, lingerMs: 60000 });
  const state = createState();
  applySnapshot(state, fixture("messages").snapshot, NOW);
  draw(state);
  applyEvent(state, "message", fixture("messages").events[0].data, NOW);
  draw(state);
  assert.equal(q(".particle").classList.contains("arrived"), true);
  assert.equal(q(".thread").getAttribute("stroke-dashoffset"), "0");
});

test("ghosts linger for ghostMs, are revived when the pid returns, and vanish immediately under instant draws", async () => {
  const { draw, q, qa } = setup({ reducedMotion: true, ghostMs: 10 });
  const state = createState();
  applySnapshot(state, fixture("few").snapshot, NOW);
  draw(state);
  draw(createState());
  assert.equal(qa(".body").length, 5);
  assert.equal(q('.body[data-pid="30111"]').dataset.state, "ended");
  assert.equal(q('.body[data-pid="30111"]').classList.contains("leaving"), true);
  draw(state);
  assert.equal(qa(".leaving").length, 0);
  assert.equal(q('.body[data-pid="30111"]').dataset.state, "busy");
  draw(createState(), { instant: true });
  assert.equal(qa(".body").length, 0);
  draw(state);
  draw(createState());
  await sleep(30);
  assert.equal(qa(".body").length, 0);
});

test("instant draws skip fade-in and never spawn particles for replayed states", () => {
  const { draw, qa } = setup({ reducedMotion: true, lingerMs: 60000 });
  const state = replay(draw, "messages");
  const live = qa(".particle").length;
  assert.ok(live > 0);
  const replayed = createState();
  applySnapshot(replayed, fixture("messages").snapshot, NOW);
  replayed.snapshotSeq = -1;
  draw(replayed, { instant: true });
  assert.equal(qa(".particle").length, 0);
  assert.equal(qa(".body").every((b) => !b.classList.contains("entering")), true);
});

test("a new snapshot clears particles and threads and redraws waiting threads from it", () => {
  const { draw, qa } = setup({ reducedMotion: true, lingerMs: 60000 });
  const state = replay(draw, "messages");
  applySnapshot(state, { sessions: fixture("messages").snapshot.sessions, messages: [fixture("messages").events[0].data] }, NOW);
  draw(state);
  assert.equal(qa(".particle").length, 0);
  assert.equal(qa(".thread").length, 1);
});

test("placeholders render as placeholder bodies and messages route to them; null senders start at the center", () => {
  const { draw, q, qa } = setup({ reducedMotion: true, lingerMs: 60000 });
  const state = createState();
  applySnapshot(state, { sessions: [{ ts: "2026-10-05T22:00:00Z", type: "session", session: "a-1", folder: "a", pid: 1, state: "idle", role: null }], messages: [] }, NOW);
  draw(state);
  applyEvent(state, "message", { ts: "2026-10-05T22:00:01Z", type: "message", from: "a-1", to: "b-22", text: "x", notify_on_idle: true }, NOW);
  draw(state);
  const placeholder = q('.body[data-pid="placeholder:b-22"]');
  assert.equal(placeholder.dataset.state, "placeholder");
  assert.equal(placeholder.querySelector("title").textContent, "b-22, no session event yet (folder guessed: b)");
  const [x, y] = placeholder.style.transform.match(/[\d.]+/g);
  assert.equal(q(".particle-dot").getAttribute("cx"), String(Number(x)));
  assert.equal(q(".particle-dot").getAttribute("cy"), String(Number(y)));
  applyEvent(state, "message", { ts: "2026-10-05T22:00:02Z", type: "message", from: null, to: "a-1", text: "y", notify_on_idle: false }, NOW);
  draw(state);
  const last = qa(".particle").at(-1);
  assert.ok(last.querySelector(".particle-path").getAttribute("d").startsWith("M 680 500 Q"));
  assert.equal(last.querySelector("title").textContent, "unknown sender → a-1: y");
});

test("renames update the label in place with a flash and a tooltip, and route former names to the body", () => {
  const { draw, q, qa } = setup({ reducedMotion: true, lingerMs: 60000 });
  const state = createState();
  const fx = fixture("rename");
  applySnapshot(state, fx.snapshot, NOW);
  draw(state);
  const before = q('.body[data-pid="29248"]').style.transform;
  for (const step of fx.events.slice(0, 2)) {
    applyEvent(state, step.event, step.data, NOW);
    draw(state);
  }
  const body = q('.body[data-pid="29248"]');
  assert.equal(qa(".body").length, 3);
  assert.equal(body.querySelector(".name").textContent, "manager-drives-feature-…");
  assert.equal(body.classList.contains("renamed"), true);
  assert.equal(body.querySelector("title").textContent, "manager-drives-feature-work (manager) in path_finder, formerly path-finder-0d");
  assert.equal(body.style.transform, before);
  applyEvent(state, "message", fx.events[2].data, NOW);
  draw(state);
  const [x, y] = before.match(/[\d.]+/g);
  assert.ok(qa(".particle").at(-1).querySelector(".particle-path").getAttribute("d").startsWith(`M ${Number(x)} ${Number(y)} Q`));
});

test("selection toggles the selected class and onSelect fires on click, Enter, and Space only", () => {
  const selected = [];
  const { draw, q } = setup({ reducedMotion: true, lingerMs: 60000, onSelect: (message, index) => selected.push([index, message.text]) });
  const state = createState();
  applySnapshot(state, { sessions: [], messages: [] }, NOW);
  draw(state);
  applyEvent(state, "message", { ts: "2026-10-05T22:00:01Z", type: "message", from: "a", to: "b", text: "t", notify_on_idle: false }, NOW);
  draw(state);
  const particle = q(".particle");
  assert.equal(particle.getAttribute("role"), "button");
  const event = { preventDefault() {} };
  particle.dispatchEvent({ type: "click", ...event });
  particle.dispatchEvent({ type: "keydown", key: "Enter", ...event });
  particle.dispatchEvent({ type: "keydown", key: " ", ...event });
  particle.dispatchEvent({ type: "keydown", key: "x", ...event });
  assert.deepEqual(selected, [[0, "t"], [0, "t"], [0, "t"]]);
  draw.select(0);
  assert.equal(particle.classList.contains("selected"), true);
  draw.select(null);
  assert.equal(particle.classList.contains("selected"), false);
});
