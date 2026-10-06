import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { installGlobals, Element, document } from "./frontend-dom-stub.js";
installGlobals();
const scheduleTimeout = globalThis.setTimeout;
globalThis.setTimeout = (callback, delay, ...args) => {
  const timer = scheduleTimeout(callback, delay, ...args);
  timer.unref?.();
  return timer;
};
const root = fileURLToPath(new URL("../..", import.meta.url));
const F = (p) => path.join(root, "frontend", p);
const fixture = (n) => JSON.parse(fs.readFileSync(F(`fixtures/${n}.json`), "utf8"));
const { createState, applySnapshot, applyEvent, applySessionEvent, applyMessageEvent, prunePlaceholders, folderFromName, waitingThreads, liveSessions, sessionByName, sessionLabel } = await import(F("state.js"));
const { boardLayout, tracePath, traceKey, edgeBox, truncateLabel } = await import(F("layout.js"));
const { createTimeline, mountTimelineStrip, formatClock } = await import(F("timeline.js"));
const { describeMessage, formatTimestamp, createPanel } = await import(F("panel.js"));
const { createRenderer } = await import(F("render.js"));

function check(name, actual, expected, tol) {
  const actualText = JSON.stringify(actual);
  const expectedText = JSON.stringify(expected);
  const ok = tol !== undefined ? Math.abs(actual - expected) <= tol : actualText === expectedText;
  test(name, () => assert.ok(ok, `expected ${expectedText}, actual ${actualText}`));
}
const pad = (n) => String(n).padStart(2, "0");
const localDateTime = (iso) => { const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
const localClock = (iso) => { const d = new Date(iso); return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
const sleep = (ms) => new Promise((r) => scheduleTimeout(r, ms));

// ---------- state.md ----------
check("createState size", createState().sessions.size, 0);
check("createState shape", Object.keys(createState()), ["sessions", "placeholders", "messages", "threads", "lastEventTs", "snapshotSeq"]);
{
  const state = createState();
  applySnapshot(state, { sessions: [{ ts: "2026-10-05T21:40:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: null }], messages: [{ ts: "2026-10-05T21:40:05Z", type: "message", from: "listings-bc", to: "tag-analyzer-63", text: "L16 is ready", notify_on_idle: true }] });
  check("applySnapshot state", state.sessions.get(29904).state, "idle");
  check("applySnapshot messages", state.messages.length, 1);
  check("applySnapshot threads", state.threads, [{ id: 0, from: "listings-bc", to: "tag-analyzer-63", ts: "2026-10-05T21:40:05Z", status: "waiting", resolvedTs: null }]);
  check("applySnapshot seq", state.snapshotSeq, 1);
  check("applySnapshot lastTs", state.lastEventTs, "2026-10-05T21:40:05Z");
  applyEvent(state, "liveness", { ts: "2026-10-05T21:46:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "ended", role: null });
  check("applyEvent liveness", state.sessions.get(29904).state, "ended");
  applySessionEvent(state, { ts: "2026-10-05T21:43:00Z", type: "session", session: null, folder: "scratch", pid: 30444, state: "started", role: null });
  applySessionEvent(state, { ts: "2026-10-05T21:45:00Z", type: "session", session: "scratch-7a", folder: "scratch", pid: 30444, state: "idle", role: null });
  check("applySessionEvent merge", state.sessions.get(30444), { pid: 30444, session: "scratch-7a", folder: "scratch", role: null, state: "idle", ts: "2026-10-05T21:45:00Z", firstSeen: "2026-10-05T21:43:00Z", formerNames: [] });
  applyMessageEvent(state, { ts: "2026-10-05T21:44:05Z", type: "message", from: "path-finder-e5", to: "path-finder-18", text: "F1 spec updated" });
  check("applyMessageEvent defaults", state.messages.at(-1), { ts: "2026-10-05T21:44:05Z", from: "path-finder-e5", to: "path-finder-18", text: "F1 spec updated", notify_on_idle: false });
  applyMessageEvent(state, { ts: "2026-10-05T22:00:29Z", type: "message", from: null, to: "path-finder-18", text: "sender unknown" });
  check("applyMessageEvent null from", state.messages.at(-1).from, null);
  const before = state.messages.length;
  check("applyMessageEvent numeric from dropped", applyMessageEvent(state, { from: 5, to: "x", text: "t" }).messages.length, before);
  check("applySnapshot null", applySnapshot(createState(), null).sessions.size, 0);
}
{
  const fx = fixture("messages"); const state = applySnapshot(createState(), fx.snapshot, Date.parse("2026-10-05T22:01:00Z"));
  const now = Date.parse("2026-10-05T22:01:00Z");
  const t = (s) => s.threads.map((x) => `${x.id}:${x.to}:${x.status}`);
  applyEvent(state, fx.events[0].event, fx.events[0].data, now); check("threads after e1", t(state), ["1:path-finder-e5:waiting"]);
  applyEvent(state, fx.events[1].event, fx.events[1].data, now); check("threads after e2", t(state), ["1:path-finder-e5:waiting"]);
  for (let i = 2; i <= 4; i++) applyEvent(state, fx.events[i].event, fx.events[i].data, now);
  check("threads after e5", t(state), ["1:path-finder-e5:snapped"]);
  for (let i = 5; i < fx.events.length; i++) applyEvent(state, fx.events[i].event, fx.events[i].data, now);
  check("events count", fx.events.length, 10);
  check("threads after all", t(state), ["1:path-finder-e5:snapped", "4:nobody-99:waiting", "5:listings-bc:dropped"]);
  check("messages after all", state.messages.length, 7);
  check("last from null", state.messages.at(-1).from, null);
  check("waitingThreads", waitingThreads(state).map((x) => x.to), ["nobody-99"]);
}
{
  const now = Date.parse("2026-10-05T22:01:00Z");
  const state = applySnapshot(createState(), { sessions: [], messages: [{ ts: "2026-10-05T22:00:00Z", type: "message", from: "a-11", to: "b-22", text: "x", notify_on_idle: false }] }, now);
  check("placeholders created", [...state.placeholders.keys()], ["a-11", "b-22"]);
  applyEvent(state, "session", { ts: "2026-10-05T22:00:01Z", type: "session", session: "b-22", folder: "b", pid: 1, state: "started", role: null }, now);
  check("placeholder merged", [...state.placeholders.keys()], ["a-11"]);
  check("liveSessions with placeholder", liveSessions(state).map((s) => s.pid), ["placeholder:a-11", 1]);
  check("prune +59s", prunePlaceholders(state, now + 59000), 0);
  check("prune +60s", prunePlaceholders(state, now + 60000), 1);
  check("prune size", state.placeholders.size, 0);
}
check("folderFromName 1", folderFromName("path-finder-18"), "path-finder");
check("folderFromName 2", folderFromName("listings-bc"), "listings");
check("folderFromName 3", folderFromName("add-semantic-similarity-scores"), "add-semantic-similarity-scores");
let threw = false; try { folderFromName(null); } catch (e) { threw = e instanceof TypeError; } check("folderFromName throws TypeError", threw, true);
{
  const state = applySnapshot(createState(), fixture("few").snapshot);
  check("liveSessions few", liveSessions(state).map(sessionLabel), ["listings-bc", "path-finder-18", "path-finder-e5", "pid 30444", "tag-analyzer-63"]);
  for (const step of fixture("few").events) applyEvent(state, step.event, step.data);
  check("sessionByName", sessionByName(state, "scratch-7a")?.pid, 30444);
  check("sessionByName missing", sessionByName(state, "nobody"), undefined);
  check("sessionByName null", sessionByName(state, null), undefined);
}
{
  const fx = fixture("rename"); const now = Date.parse("2026-10-05T23:01:00Z"); const state = applySnapshot(createState(), fx.snapshot, now);
  const ev = (i) => applyEvent(state, fx.events[i].event, fx.events[i].data, now);
  ev(0); ev(1);
  check("rename formerNames", state.sessions.get(29248).formerNames, ["path-finder-0d"]);
  check("rename byName former", sessionByName(state, "path-finder-0d").pid, 29248);
  ev(2); ev(3);
  check("rename no placeholder", state.placeholders.size, 0);
  check("rename thread waiting", state.threads.map((t) => `${t.to}:${t.status}`), ["path-finder-0d:waiting"]);
  ev(4);
  check("rename thread snapped", state.threads.map((t) => `${t.to}:${t.status}`), ["path-finder-0d:snapped"]);
  ev(5);
  check("rename placeholder unknown", [...state.placeholders.keys()], ["nobody-99"]);
  check("rename live labels", liveSessions(state).map(sessionLabel), ["listings-bc", "nobody-99", "manager-drives-feature-work", "path-finder-18"]);
  check("rename byName current", sessionByName(state, "manager-drives-feature-work")?.pid, 29248);
  check("rename byName placeholder", sessionByName(state, "nobody-99")?.pid, "placeholder:nobody-99");
  const t = createState(); for (const n of ["a", "b", "a", "c"]) applyEvent(t, "session", { pid: 1, session: n, folder: "f", state: "idle" });
  check("rename a b a c", t.sessions.get(1).formerNames, ["a", "b"]);
  check("placeholder formerNames", liveSessions(state).find((x) => x.state === "placeholder").formerNames, []);
  // render
  const svg = new Element("svg"); const r = applySnapshot(createState(), fx.snapshot, now); const draw = createRenderer(svg, { reducedMotion: true, lingerMs: 60000 }); draw(r);
  applyEvent(r, fx.events[0].event, fx.events[0].data, now); draw(r); applyEvent(r, fx.events[1].event, fx.events[1].data, now); draw(r);
  const body = svg.querySelector('.capsule[data-pid="29248"]');
  check("render rename name", body.querySelector(".name").textContent, "manager-drives-featu…");
  check("render rename class", body.classList.contains("renamed"), true);
  check("render rename title", body.querySelector("title").textContent, "manager-drives-feature-work (manager) in path_finder, formerly path-finder-0d");
  check("render rename no placeholder capsule", svg.querySelector('.capsule[data-pid="placeholder:path-finder-0d"]'), null);
  check("render rename capsule count", svg.querySelectorAll(".capsule").length, 3);
  applyEvent(r, fx.events[2].event, fx.events[2].data, now); draw(r);
  const pulsePath = svg.querySelector('.pulse[data-message-index="1"] .pulse-path').getAttribute("d");
  const [, bx, by] = body.style.transform.match(/translate\(([\d.]+)px, ([\d.]+)px\)/);
  check("render former-name pulse starts at capsule", pulsePath.startsWith(`M ${+bx + 110} ${+by + 56}`), true);
}
check("sessionLabel pid", sessionLabel({ pid: 30444, session: null }), "pid 30444");
check("sessionLabel name", sessionLabel({ pid: 30444, session: "scratch-7a" }), "scratch-7a");

// ---------- layout.md ----------
{
  const state = applySnapshot(createState(), fixture("few").snapshot);
  const layout = boardLayout(liveSessions(state));
  check("board size", layout.capsules.size, 5);
  check("board rows", layout.rows.map((r) => r.folder), ["listings", "path_finder", "scratch", "tag-analyzer"]);
  check("board lines", layout.lineCount, 4);
  check("board perLine", layout.perLine, 4);
  const a = layout.capsules.get(30222), b = layout.capsules.get(30333), c = layout.capsules.get(29904), d = layout.capsules.get(30111);
  check("board a", [a.x, a.y, a.cx, a.cy, a.line, a.index], [230, 412, 340, 440, 1, 0]);
  check("board b index", b.index, 1);
  check("board empty", boardLayout([]).capsules.size, 0);
  const many = boardLayout(liveSessions(applySnapshot(createState(), fixture("many").snapshot)));
  check("board many lines", many.lineCount, 8);
  check("board many first row", many.rows[0].folder, "add-semantic-similarity-scores");
  check("trace same line d", tracePath(a, b).d, "M 340 468 L 340 479 Q 340 490 351 490 L 585 490 Q 596 490 596 479 L 596 468");
  check("trace same line points", tracePath(a, b).points, [{ x: 340, y: 468 }, { x: 340, y: 490 }, { x: 596, y: 490 }, { x: 596, y: 468 }]);
  check("trace same line length", Math.round(tracePath(a, b).length), 290);
  check("trace adjacent straight", tracePath(c, a).d, "M 340 348 L 340 412");
  check("trace adjacent length", Math.round(tracePath(c, a).length), 64);
  check("trace far points", tracePath(c, d).points.length, 6);
  check("trace far bus x", tracePath(c, d).points[2].x, 468);
  let threw = false; try { tracePath(a, undefined); } catch (e) { threw = e instanceof TypeError; } check("trace throws", threw, true);
  check("traceKey", [traceKey(30333, 30222), traceKey(30222, 30333)], ["30222|30333", "30222|30333"]);
  check("edgeBox", [edgeBox(a).cx, edgeBox(a).line, edgeBox(a).width], [194, 1, 0]);
}
check("truncate long", truncateLabel("add-semantic-similarity-scores-4a", 21), "add-semantic-similar…");
check("truncate short", truncateLabel("listings-bc", 21), "listings-bc");
check("truncate 5", truncateLabel("abcdefghij", 5), "abcd…");
check("truncate 1", truncateLabel("ab", 1), "a…");

// ---------- timeline.md ----------
{
  const fx = fixture("messages"); const now = Date.parse("2026-10-05T22:01:00Z");
  const timeline = createTimeline(); timeline.recordSnapshot(fx.snapshot, now); for (const step of fx.events) timeline.record(step.event, step.data, now);
  check("timeline size", timeline.size, 16);
  check("timeline range", timeline.range(), { startMs: Date.parse("2026-10-05T21:59:00Z"), endMs: Date.parse("2026-10-05T22:00:29Z") });
  check("timeline messageTimes", timeline.messageTimes().length, 7);
  check("timeline messages last from", timeline.messages().at(-1).data.from, null);
  const at13 = timeline.stateAt(Date.parse("2026-10-05T22:00:13Z"));
  check("stateAt 13 live", liveSessions(at13).map((s) => `${sessionLabel(s)}:${s.state}`), ["listings-bc:idle", "path-finder-0d:idle", "path-finder-18:busy", "path-finder-e5:busy", "tag-analyzer-63:waiting"]);
  check("stateAt 13 threads", at13.threads.map((t) => t.status), ["waiting"]);
  check("stateAt 13 seq", at13.snapshotSeq, -1);
  const atEnd = timeline.stateAt(timeline.range().endMs);
  check("stateAt end live", liveSessions(atEnd).map((s) => `${sessionLabel(s)}:${s.state}`), ["nobody-99:placeholder", "path-finder-0d:idle", "path-finder-18:busy", "path-finder-e5:idle", "tag-analyzer-63:busy"]);
  check("stateAt end threads", atEnd.threads.map((t) => t.status), ["snapped", "waiting", "dropped"]);
  check("stateAt end seq", atEnd.snapshotSeq, -2);
  check("stateAt 0", liveSessions(timeline.stateAt(0)).length, 0);
  check("formatClock", formatClock(Date.parse("2026-10-05T22:00:13Z")), localClock("2026-10-05T22:00:13Z"));
  check("formatClock NaN", formatClock(NaN), "");
  // strip
  const footer = new Element("footer"); footer.setAttribute("data-mode", "live");
  const live = new Element("button"); live.setAttribute("data-role", "live"); footer.appendChild(live);
  const track = new Element("div"); const ticks = new Element("div"); ticks.setAttribute("data-role", "ticks"); const slider = new Element("input"); slider.setAttribute("data-role", "scrubber"); track.appendChild(ticks); track.appendChild(slider); footer.appendChild(track);
  const time = new Element("span"); time.setAttribute("data-role", "time"); footer.appendChild(time);
  let ticked = null; const strip = mountTimelineStrip(footer, timeline, { onScrub() {}, onLive() {}, onTick(m) { ticked = m; } });
  check("strip ticks", footer.querySelectorAll("button.tick").length, 7);
  check("strip first tick label", footer.querySelector("button.tick").getAttribute("aria-label").startsWith("Message from path-finder-0d to path-finder-18 at"), true);
  check("strip isLive", strip.isLive, true);
  footer.querySelectorAll("button.tick")[1].click();
  check("strip tick click", [ticked.from, ticked.to], ["path-finder-18", "path-finder-e5"]);
  check("strip label", time.textContent, "Live");
}

// ---------- panel.md ----------
check("describeMessage null", describeMessage({ ts: "2026-10-05T22:00:29Z", from: null, to: "path-finder-18", text: "sender unknown", notify_on_idle: false }), { from: "unknown sender", fromKnown: false, to: "path-finder-18", time: localDateTime("2026-10-05T22:00:29Z"), iso: "2026-10-05T22:00:29Z", text: "sender unknown", notify: false });
check("describeMessage known", describeMessage({ ts: "2026-10-05T22:00:10Z", from: "path-finder-18", to: "path-finder-e5", text: "F4 ready", notify_on_idle: true }), { from: "path-finder-18", fromKnown: true, to: "path-finder-e5", time: localDateTime("2026-10-05T22:00:10Z"), iso: "2026-10-05T22:00:10Z", text: "F4 ready", notify: true });
check("formatTimestamp null", formatTimestamp(null), "unknown time"); check("formatTimestamp bad", formatTimestamp("nope"), "unknown time");
{
  const aside = new Element("aside"); aside.hidden = true;
  const close = new Element("button"); close.setAttribute("data-role", "close"); aside.appendChild(close);
  for (const f of ["from", "to", "time", "text", "notify"]) { const el = new Element(f === "notify" ? "span" : "dd"); el.setAttribute("data-field", f); aside.appendChild(el); }
  let closed = 0; const panel = createPanel(aside, { onClose: () => closed++ });
  panel.show({ ts: "2026-10-05T22:00:29Z", from: null, to: "path-finder-18", text: "sender unknown", notify_on_idle: false }, 7);
  check("panel hidden false", aside.hidden, false);
  check("panel from", aside.querySelector("[data-field=from]").textContent, "unknown sender");
  check("panel from unknown class", aside.querySelector("[data-field=from]").classList.contains("unknown"), true);
  check("panel badge hidden", aside.querySelector("[data-field=notify]").hidden, true);
  check("panel time title", aside.querySelector("[data-field=time]").getAttribute("title"), "2026-10-05T22:00:29Z");
  check("panel selectedIndex", panel.selectedIndex, 7);
  close.click(); check("panel hide", [aside.hidden, panel.selectedIndex, closed], [true, null, 1]);
}

// ---------- render.md ----------
{
  const svg = new Element("svg"); const state = applySnapshot(createState(), fixture("few").snapshot);
  const draw = createRenderer(svg, { ghostMs: 10 }); draw(state);
  const q = (s) => svg.querySelector(s);
  check("render viewBox", svg.getAttribute("viewBox"), "0 0 1360 1000");
  check("render capsules", svg.querySelectorAll(".capsule").length, 5);
  check("render row labels", svg.querySelectorAll(".row-label").length, 4);
  check("render 30111 state", q('.capsule[data-pid="30111"]').dataset.state, "busy");
  check("render 30111 folder", q('.capsule[data-pid="30111"]').dataset.folder, "tag-analyzer");
  check("render 30111 role", q('.capsule[data-pid="30111"] .role').textContent, "validator");
  check("render 30111 title", q('.capsule[data-pid="30111"] title').textContent, "tag-analyzer-63 (validator) in tag-analyzer");
  check("render 30111 aria", q('.capsule[data-pid="30111"]').getAttribute("aria-label"), "tag-analyzer-63, busy, validator, folder tag-analyzer");
  check("render 30111 tabindex", q('.capsule[data-pid="30111"]').getAttribute("tabindex"), "0");
  check("render 30222 transform", q('.capsule[data-pid="30222"]').style.transform, "translate(230.0px, 412.0px)");
  check("render 29904 role hidden", q('.capsule[data-pid="29904"] .role').classList.contains("hidden"), true);
  check("render 30444 label", q('.capsule[data-pid="30444"] .name').textContent, "pid 30444");
  check("render 30444 powering", q('.capsule[data-pid="30444"]').classList.contains("powering"), true);
  check("render empty hidden", q(".empty-label").classList.contains("hidden"), true);
  draw(createState());
  check("render footprints", svg.querySelectorAll(".capsule").length, 5);
  check("render footprint state", q('.capsule[data-pid="30111"]').dataset.state, "ended");
  check("render footprint leaving", q('.capsule[data-pid="30111"]').classList.contains("leaving"), true);
  check("render empty shown", q(".empty-label").classList.contains("hidden"), false);
  check("render board empty", q(".board").classList.contains("empty"), true);
  await sleep(30);
  check("render footprints removed", svg.querySelectorAll(".capsule").length, 0);
  check("render row labels removed", svg.querySelectorAll(".row-label").length, 0);
}
{
  const svg = new Element("svg"); const state = applySnapshot(createState(), fixture("few").snapshot);
  const draw = createRenderer(svg, { ghostMs: 10000 }); draw(state); draw(createState()); draw(state);
  check("revive capsules", svg.querySelectorAll(".capsule").length, 5);
  check("revive none leaving", svg.querySelectorAll(".capsule.leaving").length, 0);
  check("revive busy", svg.querySelector('.capsule[data-pid="30111"]').dataset.state, "busy");
}
{
  const fx = fixture("removed"); const svg = new Element("svg"); const state = applySnapshot(createState(), fx.snapshot); const draw = createRenderer(svg, { ghostMs: 10000 }); draw(state);
  check("removed trace from snapshot", svg.querySelector(".trace")?.dataset.trace, "30111|30222");
  applyEvent(state, "session", fx.events[0].data); draw(state);
  check("removed after ended", [svg.querySelectorAll(".capsule").length, svg.querySelector('.capsule[data-pid="29904"]').dataset.state, svg.querySelector('.capsule[data-pid="29904"]').classList.contains("leaving")], [4, "ended", true]);
  applyEvent(state, "session", fx.events[1].data); draw(state);
  check("removed gone", svg.querySelector('.capsule[data-pid="40707"]'), null);
  check("removed footprint kept", svg.querySelector('.capsule[data-pid="29904"]').classList.contains("leaving"), true);
  applyEvent(state, "session", fx.events[2].data); draw(state);
  check("removed back", svg.querySelector('.capsule[data-pid="40707"]').dataset.state, "busy");
}
{
  const svg = new Element("svg"); const draw = createRenderer(svg, {}); draw(applySnapshot(createState(), fixture("many").snapshot));
  check("many 41008 name", svg.querySelector('.capsule[data-pid="41008"] .name').textContent, "add-semantic-similar…");
  check("many 41008 title", svg.querySelector('.capsule[data-pid="41008"] title').textContent, "add-semantic-similarity-scores-28 in add-semantic-similarity-scores");
}
{
  const fx = fixture("messages"); const svg = new Element("svg"); const state = createState();
  const selected = []; const draw = createRenderer(svg, { reducedMotion: true, lingerMs: 60000, onSelect: (m, i) => selected.push([m, i]) });
  draw(applySnapshot(state, fx.snapshot));
  check("msg pulses after snapshot", svg.querySelectorAll(".pulse").length, 0);
  check("msg traces after snapshot", svg.querySelectorAll(".trace").length, 1);
  check("msg charges after snapshot", svg.querySelectorAll(".charge").length, 0);
  applyEvent(state, "message", fx.events[0].data); draw(state);
  const p = svg.querySelector(".pulse");
  check("msg pulse count", svg.querySelectorAll(".pulse").length, 1);
  check("msg pulse index", p.dataset.messageIndex, "1");
  check("msg pulse notify", p.classList.contains("notify"), true);
  check("msg pulse arrived", p.classList.contains("arrived"), true);
  check("msg traces", svg.querySelectorAll(".trace").length, 2);
  check("msg charge count", svg.querySelectorAll(".charge").length, 1);
  check("msg charge id", svg.querySelector(".charge").dataset.threadId, "1");
  check("30111 waiting before e3", svg.querySelector('.capsule[data-pid="30111"]').dataset.state, "waiting");
  applyEvent(state, "session", fx.events[1].data); draw(state);
  check("msg charge still waiting", svg.querySelectorAll(".charge").length, 1);
  applyEvent(state, fx.events[2].event, fx.events[2].data); applyEvent(state, fx.events[3].event, fx.events[3].data); draw(state);
  check("30111 busy after e4", svg.querySelector('.capsule[data-pid="30111"]').dataset.state, "busy");
  applyEvent(state, "session", fx.events[4].data); draw(state);
  check("msg charge draining", svg.querySelector(".charge").classList.contains("draining"), true);
  await sleep(5);
  check("msg charge removed", svg.querySelectorAll(".charge").length, 0);
  for (let i = 5; i < fx.events.length; i++) applyEvent(state, fx.events[i].event, fx.events[i].data);
  draw(state);
  const pulse = svg.querySelector('.pulse[data-message-index="6"]');
  check("select title", pulse.querySelector("title").textContent, "unknown sender → path-finder-18: sender unknown: hook could not resolve the session name");
  check("select edge start", pulse.querySelector(".pulse-path").getAttribute("d").startsWith("M 194 "), true);
  pulse.dispatchEvent(new Event("click"));
  check("select onSelect", [selected.at(-1)[0] === state.messages[6], selected.at(-1)[1]], [true, 6]);
  draw.select(6); check("select on", pulse.classList.contains("selected"), true);
  draw.select(null); check("select off", pulse.classList.contains("selected"), false);
  const placeholder = svg.querySelector('.capsule[data-pid="placeholder:nobody-99"]');
  check("placeholder state", placeholder.dataset.state, "placeholder");
  check("placeholder title", placeholder.querySelector("title").textContent, "nobody-99, no session event yet (folder guessed: nobody)");
}
{
  const svg = new Element("svg"); const state = applySnapshot(createState(), fixture("few").snapshot); const draw = createRenderer(svg, {});
  draw(state); check("entering removed synchronously", svg.querySelectorAll(".capsule.entering").length, 0);
  const fx = fixture("messages"); const s2 = applySnapshot(createState(), fx.snapshot); draw(s2); applyEvent(s2, "message", fx.events[0].data); draw(s2);
  const dot = svg.querySelector(".pulse-dot"); check("animateMotion present", dot.querySelectorAll("animateMotion").length, 1);
  const mpath = svg.querySelector("mpath"); const pathId = svg.querySelector(".pulse-path").getAttribute("id");
  check("mpath href", mpath.getAttribute("href"), `#${pathId}`);
  const charge = svg.querySelector(".charge"); check("charge dashoffset 0 after flush", charge.getAttribute("stroke-dashoffset"), "0");
}
const appModule = await import(F("app.js")); check("app import", Object.keys(appModule), ["start"]);
