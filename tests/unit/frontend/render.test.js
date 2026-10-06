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

const setup = (options = {}) => {
  const svg = installDomStub(options.media);
  const draw = createRenderer(svg, { ghostMs: 100, lingerMs: 200, ...options });
  return { svg, draw, q: (s) => svg.querySelector(s), qa: (s) => svg.querySelectorAll(s) };
};
const loaded = (name) => {
  const state = createState();
  applySnapshot(state, fixture(name).snapshot, NOW);
  return state;
};
const stepThrough = (draw, state, name, from = 0, to = Infinity) => {
  for (const step of fixture(name).events.slice(from, to)) {
    applyEvent(state, step.event, step.data, NOW);
    draw(state);
  }
};

test("empty state shows the empty board and label; capsules and row labels appear for sessions", () => {
  const { svg, draw, q, qa } = setup({ reducedMotion: true });
  assert.equal(svg.getAttribute("viewBox"), "0 0 1360 1000");
  draw(createState());
  assert.equal(q(".empty-label").textContent, "No sessions running");
  assert.equal(q(".empty-label").classList.contains("hidden"), false);
  assert.equal(q(".board").classList.contains("empty"), true);
  const state = loaded("few");
  draw(state);
  assert.equal(qa(".capsule").length, 5);
  assert.equal(qa(".row-label").length, 4);
  assert.deepEqual(qa(".row-label").map((t) => t.getAttribute("data-folder")), ["listings", "path_finder", "scratch", "tag-analyzer"]);
  assert.equal(q(".empty-label").classList.contains("hidden"), true);
  assert.equal(q(".board").classList.contains("empty"), false);
});

test("capsules carry state, folder, position, labels, roles, tooltips, accessibility, and power-on", () => {
  const { draw, q } = setup({ reducedMotion: true });
  draw(loaded("few"));
  const capsule = q('.capsule[data-pid="30111"]');
  assert.equal(capsule.dataset.state, "busy");
  assert.equal(capsule.dataset.folder, "tag-analyzer");
  assert.equal(capsule.querySelector(".role").textContent, "validator");
  assert.equal(capsule.querySelector("title").textContent, "tag-analyzer-63 (validator) in tag-analyzer");
  assert.equal(capsule.getAttribute("aria-label"), "tag-analyzer-63, busy, validator, folder tag-analyzer");
  assert.equal(capsule.getAttribute("tabindex"), "0");
  assert.equal(capsule.getAttribute("role"), "img");
  assert.equal(capsule.querySelector(".shell").getAttribute("rx"), "14");
  assert.equal(q('.capsule[data-pid="30222"]').style.transform, "translate(230.0px, 412.0px)");
  assert.equal(q('.capsule[data-pid="29904"] .role').classList.contains("hidden"), true);
  assert.equal(q('.capsule[data-pid="30444"] .name').textContent, "pid 30444");
  assert.equal(q('.capsule[data-pid="30444"]').classList.contains("powering"), true);
  assert.equal(q('.capsule[data-pid="30111"]').classList.contains("powering"), false);
});

test("footprints linger for ghostMs, revive when the pid returns, and vanish at once under instant draws", async () => {
  const { draw, q, qa } = setup({ reducedMotion: true, ghostMs: 10 });
  const state = loaded("few");
  draw(state);
  draw(createState());
  assert.equal(qa(".capsule").length, 5);
  assert.equal(q('.capsule[data-pid="30111"]').dataset.state, "ended");
  assert.equal(q('.capsule[data-pid="30111"]').classList.contains("leaving"), true);
  assert.equal(qa(".row-label").length, 0);
  draw(state);
  assert.equal(qa(".leaving").length, 0);
  assert.equal(q('.capsule[data-pid="30111"]').dataset.state, "busy");
  draw(createState(), { instant: true });
  assert.equal(qa(".capsule").length, 0);
  draw(state);
  draw(createState());
  await sleep(30);
  assert.equal(qa(".capsule").length, 0);
});

test("removed sessions disappear at once with no footprint and come back on a later event", () => {
  const { draw, q, qa } = setup({ reducedMotion: true, ghostMs: 2000, lingerMs: 200 });
  const state = loaded("removed");
  draw(state);
  assert.equal(qa(".capsule").length, 4);
  assert.deepEqual(qa(".trace").map((t) => t.getAttribute("data-trace")), ["30111|30222"]);
  assert.equal(qa(".pulse").length, 0);
  stepThrough(draw, state, "removed", 0, 1);
  assert.equal(qa(".capsule").length, 4);
  assert.equal(q('.capsule[data-pid="29904"]').dataset.state, "ended");
  stepThrough(draw, state, "removed", 1, 2);
  assert.equal(q('.capsule[data-pid="40707"]'), null);
  assert.equal(q('.capsule[data-pid="29904"]').dataset.state, "ended");
  assert.equal(qa(".capsule").length, 3);
  stepThrough(draw, state, "removed", 2, 3);
  assert.equal(q('.capsule[data-pid="40707"]').dataset.state, "busy");
  assert.equal(qa(".capsule").length, 4);
  stepThrough(draw, state, "removed", 3, 4);
  assert.equal(qa(".pulse").length, 1);
  assert.equal(qa(".trace").length, 2);
  draw(createState(), { instant: true });
  assert.equal(qa(".capsule").length, 0);
});

test("reduced motion: pulses rest at the recipient, charges are fully drawn, and a charge drains on idle", async () => {
  const { draw, q, qa } = setup({ reducedMotion: true, lingerMs: 200 });
  const state = loaded("messages");
  draw(state);
  assert.equal(qa(".pulse").length, 0);
  assert.equal(qa(".trace").length, 1);
  assert.equal(qa(".charge").length, 0);
  stepThrough(draw, state, "messages", 0, 1);
  const pulse = q(".pulse");
  assert.equal(pulse.dataset.messageIndex, "1");
  assert.equal(pulse.classList.contains("notify"), true);
  assert.equal(pulse.classList.contains("arrived"), true);
  assert.equal(pulse.getAttribute("role"), "button");
  assert.equal(pulse.querySelector("animateMotion"), null);
  assert.equal(qa(".trace").length, 2);
  assert.equal(q(".charge").getAttribute("data-thread-id"), "1");
  assert.equal(q(".charge").getAttribute("stroke-dashoffset"), "0");
  stepThrough(draw, state, "messages", 1, 2);
  assert.equal(qa(".charge").length, 1);
  stepThrough(draw, state, "messages", 2, 5);
  assert.equal(q(".charge").classList.contains("draining"), true);
  await sleep(5);
  assert.equal(qa(".charge").length, 0);
  stepThrough(draw, state, "messages", 5);
  assert.equal(qa(".pulse").length, 6);
  assert.equal(q('.capsule[data-pid="placeholder:nobody-99"]').dataset.state, "placeholder");
  assert.ok(qa(".pulse").at(-1).querySelector(".pulse-path").getAttribute("d").startsWith("M 194 "));
  assert.equal(qa(".pulse").at(-1).querySelector("title").textContent.startsWith("unknown sender → path-finder-18"), true);
});

test("full motion: pulses animate along their own route and charges draw on; matchMedia sets the default", async () => {
  const { draw, q } = setup({ reducedMotion: false, travelMs: 5, lingerMs: 200 });
  const state = loaded("messages");
  draw(state);
  stepThrough(draw, state, "messages", 0, 1);
  const motion = q(".pulse-dot").children[0];
  assert.equal(motion.tagName, "animateMotion");
  assert.equal(motion.getAttribute("dur"), "5ms");
  assert.equal(motion.children[0].getAttribute("href"), `#${q(".pulse-path").getAttribute("id")}`);
  assert.equal(q(".pulse").classList.contains("arrived"), false);
  assert.ok(Number(q(".charge").getAttribute("stroke-dasharray")) > 0);
  assert.equal(q(".charge").getAttribute("stroke-dashoffset"), "0");
  await sleep(40);
  assert.equal(q(".pulse").classList.contains("arrived"), true);
  const viaMedia = setup({ media: { reducedMotion: true }, lingerMs: 200 });
  const other = loaded("messages");
  viaMedia.draw(other);
  stepThrough(viaMedia.draw, other, "messages", 0, 1);
  assert.equal(viaMedia.q(".pulse").classList.contains("arrived"), true);
});

test("instant draws skip power-on and fade-in and never spawn pulses; a new snapshot rebuilds traces without pulses", () => {
  const { draw, qa } = setup({ reducedMotion: true, lingerMs: 200 });
  const state = loaded("messages");
  draw(state);
  stepThrough(draw, state, "messages");
  assert.ok(qa(".pulse").length > 0);
  const replayed = loaded("few");
  replayed.snapshotSeq = -1;
  draw(replayed, { instant: true });
  assert.equal(qa(".pulse").length, 0);
  assert.equal(qa(".capsule").every((c) => !c.classList.contains("entering") && !c.classList.contains("powering")), true);
  applySnapshot(state, { sessions: fixture("messages").snapshot.sessions, messages: [fixture("messages").events[0].data] }, NOW);
  draw(state);
  assert.equal(qa(".pulse").length, 0);
  assert.equal(qa(".trace").length, 1);
  assert.equal(qa(".charge").length, 1);
});

test("renames update the label in place with a flash and tooltip, and route former names to the capsule", () => {
  const { draw, q, qa } = setup({ reducedMotion: true, lingerMs: 200 });
  const state = loaded("rename");
  draw(state);
  const before = q('.capsule[data-pid="29248"]').style.transform;
  stepThrough(draw, state, "rename", 0, 2);
  const capsule = q('.capsule[data-pid="29248"]');
  assert.equal(qa(".capsule").length, 3);
  assert.equal(capsule.querySelector(".name").textContent, "manager-drives-featu…");
  assert.equal(capsule.classList.contains("renamed"), true);
  assert.equal(capsule.querySelector("title").textContent, "manager-drives-feature-work (manager) in path_finder, formerly path-finder-0d");
  assert.equal(capsule.style.transform, before);
  assert.equal(q('.capsule[data-pid="placeholder:path-finder-0d"]'), null);
  stepThrough(draw, state, "rename", 2, 3);
  const [x, y] = before.match(/[\d.]+/g).map(Number);
  assert.ok(qa(".pulse").at(-1).querySelector(".pulse-path").getAttribute("d").startsWith(`M ${x + 110} ${y + 56}`));
});

test("selection toggles the selected class and onSelect fires on click, Enter, and Space only", () => {
  const selected = [];
  const { draw, q } = setup({ reducedMotion: true, lingerMs: 200, onSelect: (message, index) => selected.push([index, message.text]) });
  const state = createState();
  applySnapshot(state, { sessions: [], messages: [] }, NOW);
  draw(state);
  applyEvent(state, "message", { ts: "2026-10-05T22:00:01Z", type: "message", from: "a-1", to: "b-2", text: "t", notify_on_idle: false }, NOW);
  draw(state);
  const pulse = q(".pulse");
  const event = { preventDefault() {} };
  pulse.dispatchEvent({ type: "click", ...event });
  pulse.dispatchEvent({ type: "keydown", key: "Enter", ...event });
  pulse.dispatchEvent({ type: "keydown", key: " ", ...event });
  pulse.dispatchEvent({ type: "keydown", key: "x", ...event });
  assert.deepEqual(selected, [[0, "t"], [0, "t"], [0, "t"]]);
  draw.select(0);
  assert.equal(pulse.classList.contains("selected"), true);
  draw.select(null);
  assert.equal(pulse.classList.contains("selected"), false);
});

test("edit mode adds a remove control per real capsule, focusable only while editing, reporting footprints as ended", () => {
  const removed = [];
  const { svg, draw, q, qa } = setup({ reducedMotion: true, ghostMs: 2000, lingerMs: 200, onRemove: (session) => removed.push([session.pid, session.state]) });
  const state = loaded("messages");
  draw(state);
  stepThrough(draw, state, "messages", 0, 7);
  assert.equal(qa(".capsule .remove").length, qa(".capsule").length - 1);
  assert.equal(q('.capsule[data-pid="placeholder:nobody-99"] .remove'), null);
  const control = q('.capsule[data-pid="30111"] .remove');
  assert.equal(control.getAttribute("role"), "button");
  assert.equal(control.getAttribute("aria-label"), "Remove tag-analyzer-63");
  assert.equal(svg.classList.contains("editing"), false);
  assert.notEqual(control.getAttribute("tabindex"), "0");
  draw.setEditing(true);
  assert.equal(svg.classList.contains("editing"), true);
  assert.equal(control.getAttribute("tabindex"), "0");
  control.dispatchEvent({ type: "click" });
  control.dispatchEvent({ type: "keydown", key: "Enter" });
  control.dispatchEvent({ type: "keydown", key: "x" });
  assert.deepEqual(removed, [[30111, "busy"], [30111, "busy"]]);
  draw(createState());
  q('.capsule[data-pid="30111"] .remove').dispatchEvent({ type: "click" });
  assert.deepEqual(removed.at(-1), [30111, "ended"]);
  draw.setEditing(false);
  assert.equal(svg.classList.contains("editing"), false);
  assert.notEqual(control.getAttribute("tabindex"), "0");
  draw(createState(), { instant: true });
});

test("without onRemove no controls are added, and setPortrait switches the board and re-lays out two per line", () => {
  const { svg, draw, q, qa } = setup({ reducedMotion: true, lingerMs: 200 });
  const state = loaded("many");
  draw(state);
  assert.equal(qa(".remove").length, 0);
  assert.equal(svg.getAttribute("viewBox"), "0 0 1360 1000");
  draw.setPortrait(true);
  draw(state, { instant: true });
  assert.equal(svg.getAttribute("viewBox"), "0 0 760 1100");
  const xs = new Set(qa(".capsule").map((c) => c.style.transform.match(/translate\(([\d.]+)px/)[1]));
  assert.equal(xs.size, 2);
  assert.equal(qa(".row-label").length, 8);
  assert.equal(q(".row-label").getAttribute("text-anchor") ?? "start", "start");
  draw.setPortrait(false);
  draw(state, { instant: true });
  assert.equal(svg.getAttribute("viewBox"), "0 0 1360 1000");
});

