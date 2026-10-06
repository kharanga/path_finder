import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { installDomStub, uninstallDomStub } from "../../helpers/dom-stub.js";
import { createTimeline, formatClock, mountTimelineStrip } from "../../../frontend/timeline.js";
import { describeMessage, formatTimestamp, createPanel } from "../../../frontend/panel.js";
import { liveSessions, sessionLabel } from "../../../frontend/state.js";

const NOW = Date.parse("2026-10-05T22:01:00Z");
const fixture = JSON.parse(readFileSync(new URL("../../../frontend/fixtures/messages.json", import.meta.url), "utf8"));
const pad = (n) => String(n).padStart(2, "0");
const localClock = (iso) => { const d = new Date(iso); return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
const localDateTime = (iso) => { const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${localClock(iso)}`; };
const recorded = () => {
  const timeline = createTimeline();
  timeline.recordSnapshot(fixture.snapshot, NOW);
  for (const step of fixture.events) timeline.record(step.event, step.data, NOW);
  return timeline;
};
const element = (tag, attributes = {}) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
};

test.before(() => installDomStub());
test.after(() => uninstallDomStub());

test("createTimeline records entries sorted by event time, falling back to arrival time", () => {
  const timeline = recorded();
  assert.equal(timeline.size, 16);
  assert.deepEqual(timeline.range(), { startMs: Date.parse("2026-10-05T21:59:00Z"), endMs: Date.parse("2026-10-05T22:00:29Z") });
  assert.equal(timeline.messageTimes().length, 7);
  assert.equal(timeline.messages().at(-1).data.from, null);
  const fallback = createTimeline();
  fallback.record("message", { from: "a", to: "b" }, 5000);
  fallback.record("session", { ts: "garbage", pid: 1, state: "busy" }, 4000);
  assert.deepEqual(fallback.range(), { startMs: 4000, endMs: 5000 });
  assert.equal(createTimeline().range(), null);
});

test("stateAt rebuilds the state at an instant with a unique negative snapshotSeq", () => {
  const timeline = recorded();
  const at13 = timeline.stateAt(Date.parse("2026-10-05T22:00:13Z"));
  assert.deepEqual(liveSessions(at13).map((s) => `${sessionLabel(s)}:${s.state}`), ["listings-bc:idle", "path-finder-0d:idle", "path-finder-18:busy", "path-finder-e5:busy", "tag-analyzer-63:waiting"]);
  assert.deepEqual(at13.threads.map((t) => t.status), ["waiting"]);
  assert.equal(at13.snapshotSeq, -1);
  const atEnd = timeline.stateAt(timeline.range().endMs);
  assert.deepEqual(liveSessions(atEnd).map((s) => `${sessionLabel(s)}:${s.state}`), ["nobody-99:placeholder", "path-finder-0d:idle", "path-finder-18:busy", "path-finder-e5:idle", "tag-analyzer-63:busy"]);
  assert.deepEqual(atEnd.threads.map((t) => t.status), ["snapped", "waiting", "dropped"]);
  assert.equal(atEnd.snapshotSeq, -2);
  assert.equal(liveSessions(timeline.stateAt(0)).length, 0);
});

test("formatClock renders local HH:MM:SS and an empty string for invalid input", () => {
  assert.equal(formatClock(Date.parse("2026-10-05T22:00:13Z")), localClock("2026-10-05T22:00:13Z"));
  assert.equal(formatClock(NaN), "");
});

test("mountTimelineStrip follows live mode, scrubs, keeps the knob while scrubbed, and offers ticks that open messages", () => {
  const container = element("footer");
  const live = element("button", { "data-role": "live" });
  const slider = element("input", { "data-role": "scrubber" });
  const ticks = element("div", { "data-role": "ticks" });
  const time = element("span", { "data-role": "time" });
  for (const part of [live, slider, ticks, time]) container.appendChild(part);
  const calls = [];
  const timeline = createTimeline();
  const strip = mountTimelineStrip(container, timeline, { onScrub: (ts) => calls.push(["scrub", ts]), onLive: () => calls.push(["live"]), onTick: (m, ts) => calls.push(["tick", m.to, ts]) });
  assert.deepEqual([slider.disabled, live.disabled, time.textContent, container.dataset.mode, strip.isLive], [true, true, "Live", "live", true]);
  timeline.recordSnapshot(fixture.snapshot, NOW);
  for (const step of fixture.events) timeline.record(step.event, step.data, NOW);
  strip.refresh();
  const range = timeline.range();
  assert.deepEqual([slider.disabled, Number(slider.min), Number(slider.max), Number(slider.value)], [false, range.startMs, range.endMs, range.endMs]);
  const tickButtons = ticks.children.filter((node) => node.tagName === "button");
  assert.equal(tickButtons.length, 7);
  assert.ok(tickButtons[0].getAttribute("aria-label").startsWith("Message from path-finder-0d to path-finder-18 at"));
  assert.ok(tickButtons.at(-1).getAttribute("aria-label").startsWith("Message from unknown sender to path-finder-18 at"));
  tickButtons[1].dispatchEvent({ type: "click" });
  assert.deepEqual(calls.at(-1), ["tick", "path-finder-e5", Date.parse("2026-10-05T22:00:10Z")]);
  const t13 = Date.parse("2026-10-05T22:00:13Z");
  slider.value = String(t13);
  slider.dispatchEvent({ type: "input" });
  assert.deepEqual([strip.isLive, container.dataset.mode, time.textContent, live.disabled, calls.at(-1)], [false, "scrub", formatClock(t13), false, ["scrub", t13]]);
  timeline.record("session", { ts: "2026-10-05T22:05:00Z", type: "session", session: "z-1", folder: "z", pid: 9, state: "busy", role: null }, NOW);
  strip.refresh();
  assert.deepEqual([Number(slider.max), Number(slider.value)], [Date.parse("2026-10-05T22:05:00Z"), t13]);
  live.dispatchEvent({ type: "click" });
  assert.deepEqual([strip.isLive, time.textContent, Number(slider.value), calls.at(-1)], [true, "Live", Number(slider.max), ["live"]]);
  assert.throws(() => mountTimelineStrip(element("footer"), timeline, { onScrub() {}, onLive() {} }), TypeError);
});

test("describeMessage and formatTimestamp produce panel fields with unknown-sender and unknown-time fallbacks", () => {
  assert.deepEqual(describeMessage({ ts: "2026-10-05T22:00:29Z", from: null, to: "p-18", text: "s", notify_on_idle: false }), { from: "unknown sender", fromKnown: false, to: "p-18", time: localDateTime("2026-10-05T22:00:29Z"), iso: "2026-10-05T22:00:29Z", text: "s", notify: false });
  assert.deepEqual(describeMessage({ ts: "2026-10-05T22:00:10Z", from: "p-18", to: "p-e5", text: "F4", notify_on_idle: true }).notify, true);
  assert.equal(describeMessage({ to: "x" }).text, "");
  assert.equal(describeMessage({ to: "x" }).time, "unknown time");
  assert.equal(formatTimestamp(null), "unknown time");
  assert.equal(formatTimestamp("nope"), "unknown time");
});

test("createPanel shows, hides, toggles the badge and unknown class, and reports the selected index", () => {
  const aside = element("aside");
  aside.hidden = true;
  const fields = {};
  for (const name of ["from", "to", "time", "text", "notify"]) {
    fields[name] = element("dd", { "data-field": name });
    aside.appendChild(fields[name]);
  }
  fields.notify.hidden = true;
  const close = element("button", { "data-role": "close" });
  let focused = 0;
  close.focus = () => { focused += 1; };
  aside.appendChild(close);
  let closed = 0;
  const panel = createPanel(aside, { onClose: () => { closed += 1; } });
  panel.show({ ts: "2026-10-05T22:00:29Z", from: null, to: "p-18", text: "t", notify_on_idle: false }, 6);
  assert.deepEqual([aside.hidden, fields.from.textContent, fields.from.classList.contains("unknown"), fields.notify.hidden, fields.time.getAttribute("title"), panel.selectedIndex, focused], [false, "unknown sender", true, true, "2026-10-05T22:00:29Z", 6, 1]);
  panel.show({ ts: "2026-10-05T22:00:10Z", from: "p-18", to: "p-e5", text: "F4", notify_on_idle: true }, 1);
  assert.deepEqual([fields.from.classList.contains("unknown"), fields.notify.hidden, fields.text.textContent, panel.selectedIndex], [false, false, "F4", 1]);
  panel.hide();
  assert.deepEqual([aside.hidden, panel.selectedIndex, closed], [true, null, 1]);
  panel.show({ to: "x" }, 2);
  close.dispatchEvent({ type: "click" });
  assert.deepEqual([aside.hidden, closed], [true, 2]);
  assert.throws(() => createPanel(element("aside")), TypeError);
});
