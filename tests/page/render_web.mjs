import { readFileSync } from "node:fs";

const [htmlPath, inputPath] = process.argv.slice(2);
const html = readFileSync(htmlPath, "utf8");
const input = JSON.parse(readFileSync(inputPath, "utf8"));
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

let wallMs = Date.parse(input.wallStart || "2026-10-08T04:31:00.000Z");
const FakeDate = { now: () => wallMs, parse: (text) => Date.parse(text) };
const GRAPH_WIDTH = input.graphWidth || 356;

function makeClassList(element) {
  const names = () => element.className.split(/\s+/).filter(Boolean);
  const set = (list) => { element.className = list.join(" "); };
  return {
    add: (name) => { if (!names().includes(name)) set([...names(), name]); },
    remove: (name) => set(names().filter((n) => n !== name)),
    toggle: (name, force) => {
      const has = names().includes(name);
      const want = force === undefined ? !has : force;
      if (want && !has) set([...names(), name]);
      if (!want && has) set(names().filter((n) => n !== name));
    },
    contains: (name) => names().includes(name),
  };
}

function makeElement(tag) {
  const element = { tag, children: [], parent: null, className: "", textContent: "", title: "", id: "", dataset: {}, style: {}, attrs: {}, listeners: {},
    get clientWidth() { return GRAPH_WIDTH; },
    append(...nodes) { for (const node of nodes) { if (node.parent) node.remove(); node.parent = this; this.children.push(node); } },
    replaceChildren(...nodes) { this.children = []; this.append(...nodes); },
    remove() { if (this.parent) { this.parent.children = this.parent.children.filter((c) => c !== this); this.parent = null; } },
    setAttribute(name, value) { this.attrs[name] = String(value); },
    getBoundingClientRect() { return { top: 0, left: 0, right: GRAPH_WIDTH, bottom: 0, width: GRAPH_WIDTH, height: 0 }; },
    setPointerCapture() { this.captured = true; }, releasePointerCapture() { this.captured = false; },
    addEventListener(type, handler) { this.listeners[type] = handler; },
    querySelector(selector) { const name = selector.slice(1); return this.children.find((c) => c.className && c.className.split(" ").includes(name)) || null; } };
  element.classList = makeClassList(element);
  return element;
}

const fixed = {};
for (const id of ["graph", "svg", "arrows", "title", "link", "cap-entry", "cap-pair", "strip", "rows", "panel", "ptab", "plist", "reset-layout"]) fixed[id] = makeElement("div");
fixed["reset-layout"].hidden = true;
const WINDOW_HEIGHT = input.windowHeight || 1000;
const document = { getElementById: (id) => fixed[id], createElement: makeElement, createElementNS: (_ns, name) => makeElement(name), createTextNode: (text) => ({ text: String(text), parent: null, remove() {} }) };
const windowListeners = {};
const storage = { ...(input.localStorage || {}) };
const localStorage = {
  getItem(key) { if (input.storageThrows) throw new Error("blocked"); return storage[key] === undefined ? null : storage[key]; },
  setItem(key, value) { if (input.storageThrows) throw new Error("blocked"); storage[key] = String(value); },
  removeItem(key) { if (input.storageThrows) throw new Error("blocked"); delete storage[key]; },
  key(index) { if (input.storageThrows) throw new Error("blocked"); return Object.keys(storage)[index] === undefined ? null : Object.keys(storage)[index]; },
  get length() { if (input.storageThrows) throw new Error("blocked"); return Object.keys(storage).length; },
};
const window = { innerHeight: WINDOW_HEIGHT, addEventListener(type, handler) { windowListeners[type] = handler; } };
const requestAnimationFrame = (callback) => setTimeout(callback, 0);
const sources = [];
class EventSource { constructor(url) { this.url = url; sources.push(this); } }
const fetch = async () => ({ ok: true, json: async () => input.snapshot });
const timers = [];
const setTimeout = (callback, delay) => { timers.push({ callback, delay: delay || 0 }); return timers.length; };
const intervals = [];
const setInterval = (callback, delay) => { intervals.push({ callback, delay }); return intervals.length; };
const clearInterval = () => {};

function runTimers() {
  while (timers.length) timers.splice(0).forEach((t) => t.callback());
}

function tick() {
  for (const interval of intervals) interval.callback();
}

new Function("document", "window", "fetch", "EventSource", "setTimeout", "setInterval", "clearInterval", "Date", "localStorage", "requestAnimationFrame", script)(
  document, window, fetch, EventSource, setTimeout, setInterval, clearInterval, FakeDate, localStorage, requestAnimationFrame);
await new Promise((resolve) => setImmediate(resolve));
runTimers();
const source = sources[0];
if (input.open !== false) source.onopen();

function textOf(node) {
  if (node.text !== undefined) return node.text;
  return (node.textContent || "") + (node.children || []).map(textOf).join("");
}

function findByClass(node, name) {
  return (node.children || []).find((c) => c.className && c.className.split(" ").includes(name)) || null;
}

function nodeView(node) {
  const hd = findByClass(node, "hd"), row2 = findByClass(node, "row2"), last = findByClass(node, "last");
  const eye = last ? findByClass(last, "eye") : null;
  const headEye = hd ? findByClass(hd, "eye") : null;
  const headMail = hd ? findByClass(hd, "mail") : null;
  const badge = hd ? findByClass(hd, "task-badge") : null;
  const rowMail = row2 ? findByClass(row2, "mail") : null;
  return { pid: Number(node.dataset.pid), className: node.className, left: node.style.left, top: node.style.top, width: node.style.width, height: node.style.height, title: node.title, line: node.dataset.line, captured: Boolean(node.captured), draggable: Boolean(node.listeners.pointerdown && node.listeners.pointermove && node.listeners.pointerup && node.listeners.pointercancel),
    name: hd ? textOf(findByClass(hd, "name")) : "", dotClass: hd ? findByClass(hd, "dot").className : "", dot: hd ? findByClass(hd, "dot").style.background : "",
    headMail: headMail ? textOf(headMail) : null, headEye: headEye ? headEye.className : null, badge: badge ? textOf(badge) : null, badgeTitle: badge ? badge.title : null,
    pills: row2 ? row2.children.map((p) => [p.className, textOf(p)]) : [], mail: rowMail ? textOf(rowMail) : null, mailTitle: rowMail ? rowMail.title : null,
    last: last ? textOf(last) : "", lastTitle: last ? last.title : "", eye: eye ? eye.className : null };
}

function labelView(label) {
  const summary = findByClass(label, "esum");
  const stage = label.children.find((c) => c !== summary);
  return { key: label.dataset.key, clear: label.dataset.clear, text: textOf(label), summary: summary ? textOf(summary) : "", stage: stage ? [stage.className, textOf(stage)] : null,
    opacity: label.style.opacity, left: parseFloat(label.style.left), top: parseFloat(label.style.top), zIndex: label.style.zIndex, title: label.title };
}

function pathView(path) {
  return { key: path.attrs["data-key"], stage: path.attrs["data-stage"], stroke: path.attrs.stroke, marker: path.attrs["marker-end"], width: path.attrs["stroke-width"], opacity: path.style.opacity, className: path.className, d: path.attrs.d, hoverable: Boolean(path.listeners.mouseenter) };
}

function chipView(chip) {
  const count = findByClass(chip, "n");
  return { pid: Number(chip.dataset.pid), className: chip.className, dotClass: findByClass(chip, "dot").className, text: textOf(chip), count: count ? textOf(count) : null, title: chip.title, clickable: Boolean(chip.listeners.click) };
}

function rowView(row) {
  if (row.className === "quiet-rows") return { className: row.className, text: textOf(row) };
  const name = findByClass(row, "name"), pill = findByClass(row, "pill"), act = findByClass(row, "act");
  const badge = findByClass(name, "task-badge");
  return { pid: Number(row.dataset.pid), status: row.dataset.status, className: row.className, dotClass: findByClass(row, "dot").className, name: textOf(name), nameTitle: name.title, badge: badge ? textOf(badge) : null,
    pill: [pill.className, textOf(pill)], activity: textOf(act), activityTitle: act.title, clickable: Boolean(row.listeners.click) };
}

function taskView(item) {
  if (item.className === "quiet-rows") return { className: item.className, text: textOf(item) };
  const owner = findByClass(item, "towner"), full = findByClass(item, "tfull");
  const ownerDot = owner ? findByClass(owner, "dot") : null;
  return { id: item.dataset.id, state: item.dataset.state, className: item.className, title: item.title, tid: textOf(findByClass(item, "tid")), ttitle: textOf(findByClass(item, "ttitle")), tstate: textOf(findByClass(item, "tstate")),
    owner: owner ? textOf(owner) : null, ownerDot: ownerDot ? ownerDot.style.background : null, full: full ? textOf(full) : null, clickable: Boolean(item.listeners.click), hoverable: Boolean(item.listeners.mouseenter && item.listeners.mouseleave) };
}

function folderView(folder) {
  const head = findByClass(folder, "fhead"), body = findByClass(folder, "fbody");
  const name = head.children.find((c) => c.tag === "b");
  return { area: folder.dataset.area, closed: folder.dataset.closed, className: folder.className, name: name ? textOf(name) : "", counts: textOf(findByClass(head, "fcounts") || { text: "" }),
    chevron: textOf(findByClass(head, "chev") || { text: "" }), title: head.title, clickable: Boolean(head.listeners.click), tasks: body.children.map(taskView) };
}

function folders() {
  return fixed.plist.children.filter((c) => c.className.split(" ").includes("folder"));
}

function taskCards() {
  return folders().flatMap((folder) => findByClass(folder, "fbody").children);
}

function panelView() {
  const tab = fixed.ptab;
  const items = folders().length ? taskCards() : fixed.plist.children;
  return { collapsed: fixed.panel.classList.contains("collapsed"), tab: textOf(tab), tabTitle: tab.title, counts: textOf(findByClass(tab, "counts") || { text: "" }), chevron: textOf(findByClass(tab, "chev") || { text: "" }),
    folders: folders().map(folderView), tasks: items.map(taskView), storage: { ...storage } };
}

function view() {
  const quiet = fixed.graph.querySelector(".quiet");
  return { panel: panelView(), graphHeight: fixed.graph.style.height, graphClass: fixed.graph.className, resetHidden: fixed["reset-layout"].hidden, storage: { ...storage }, title: fixed.title.textContent, link: fixed.link.textContent, linkClass: fixed.link.className, eventsUrl: source.url, intervals: intervals.map((i) => i.delay),
    caption: [fixed["cap-entry"].textContent, fixed["cap-pair"].textContent], pod: fixed.graph.classList.contains("pod"), viewBox: fixed.svg.attrs.viewBox, quiet: quiet ? textOf(quiet) : null,
    nodes: fixed.graph.children.filter((c) => c.className.startsWith("node")).map(nodeView), labels: fixed.graph.children.filter((c) => c.className.startsWith("elab")).map(labelView),
    paths: fixed.arrows.children.map(pathView), chips: fixed.strip.children.map(chipView), rows: fixed.rows.children.map(rowView) };
}

const out = [];
for (const step of input.steps || []) {
  for (const frame of step.frames || []) source.onmessage({ data: JSON.stringify(frame) });
  if (step.error) source.onerror();
  if (step.reopen) source.onopen();
  if (step.advanceMs) wallMs += step.advanceMs;
  if (step.clickChip !== undefined) fixed.strip.children.find((c) => Number(c.dataset.pid) === Number(step.clickChip)).listeners.click();
  if (step.clickNode !== undefined) fixed.graph.children.find((c) => c.className.startsWith("node") && Number(c.dataset.pid) === Number(step.clickNode)).listeners.click();
  if (step.clickRow !== undefined) fixed.rows.children.find((r) => Number(r.dataset.pid) === Number(step.clickRow)).listeners.click();
  if (step.clickTab) fixed.ptab.listeners.click();
  if (step.clickTask !== undefined) taskCards().find((t) => t.dataset.id === step.clickTask).listeners.click();
  if (step.hoverTask !== undefined) taskCards().find((t) => t.dataset.id === step.hoverTask).listeners.mouseenter();
  if (step.leaveTask !== undefined) taskCards().find((t) => t.dataset.id === step.leaveTask).listeners.mouseleave();
  if (step.clickFolder !== undefined) findByClass(folders().find((f) => f.dataset.area === step.clickFolder), "fhead").listeners.click();
  if (step.hoverPath !== undefined) fixed.arrows.children.find((p) => p.attrs["data-key"] === step.hoverPath).listeners.mouseenter();
  if (step.leavePath !== undefined) fixed.arrows.children.find((p) => p.attrs["data-key"] === step.leavePath).listeners.mouseleave();
  if (step.resize) windowListeners.resize();
  if (step.pointer) {
    const node = fixed.graph.children.find((c) => c.className.startsWith("node") && Number(c.dataset.pid) === Number(step.pointer.pid));
    const x0 = parseFloat(node.style.left) + 10, y0 = parseFloat(node.style.top) + 10;
    const at = (x, y) => ({ pointerId: 7, button: 0, clientX: x, clientY: y });
    node.listeners.pointerdown(at(x0, y0));
    runTimers();
    const moves = step.pointer.moves || [[step.pointer.dx, step.pointer.dy]];
    for (const [dx, dy] of moves) { node.listeners.pointermove(at(x0 + dx, y0 + dy)); runTimers(); }
    if (step.pointer.cancel) node.listeners.pointercancel(at(x0 + moves[moves.length - 1][0], y0 + moves[moves.length - 1][1]));
    else if (!step.pointer.hold) node.listeners.pointerup(at(x0 + moves[moves.length - 1][0], y0 + moves[moves.length - 1][1]));
    runTimers();
    if (step.pointer.thenClick) node.listeners.click();
  }
  if (step.clickReset) fixed["reset-layout"].listeners.click();
  if (step.releaseNode !== undefined) {
    const node = fixed.graph.children.find((c) => c.className.startsWith("node") && Number(c.dataset.pid) === Number(step.releaseNode));
    node.listeners.pointerup({ pointerId: 7, button: 0, clientX: parseFloat(node.style.left) + 10, clientY: parseFloat(node.style.top) + 10 });
  }
  runTimers();
  tick();
  out.push({ name: step.name, view: view() });
}
console.log(JSON.stringify(out));
