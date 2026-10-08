import { readFileSync } from "node:fs";

const [htmlPath, inputPath] = process.argv.slice(2);
const html = readFileSync(htmlPath, "utf8");
const input = JSON.parse(readFileSync(inputPath, "utf8"));
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function makeClassList(element) {
  const names = () => element.className.split(/\s+/).filter(Boolean);
  return {
    add: (name) => { if (!names().includes(name)) element.className = [...names(), name].join(" "); },
    remove: (name) => { element.className = names().filter((n) => n !== name).join(" "); },
    contains: (name) => names().includes(name),
  };
}

function makeElement(tag) {
  const element = { tag, children: [], className: "", textContent: "", title: "", id: "", dataset: {}, attrs: {}, listeners: {},
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren() { this.children = []; },
    setAttribute(name, value) { this.attrs[name] = String(value); },
    addEventListener(type, handler) { this.listeners[type] = handler; },
    getBoundingClientRect() { return rectFor(this); } };
  element.classList = makeClassList(element);
  return element;
}

function rectFor(element) {
  const match = /^session-(\d+)$/.exec(element.id);
  if (!match) return { left: 0, top: 0, width: 1000, height: 400 };
  const order = sessionOrder.indexOf(Number(match[1]));
  return { left: 40 + order * 320, top: 80, width: 240, height: 90 };
}

const fixed = {};
for (const id of ["board", "count", "updated", "link", "wires", "tags", "panel", "panel-title", "panel-list", "panel-close", "legend"]) fixed[id] = makeElement("div");

function findById(node, id) {
  if (node.id === id) return node;
  for (const child of node.children || []) {
    const found = child.children ? findById(child, id) : null;
    if (found) return found;
  }
  return null;
}

const sessionOrder = [];
const document = {
  getElementById: (id) => fixed[id] || findById(fixed.board, id),
  createElement: makeElement,
  createElementNS: (_ns, name) => makeElement(name),
  createTextNode: (text) => ({ text: String(text) }),
};
const window = { addEventListener() {} };
const sources = [];
class EventSource { constructor(url) { this.url = url; sources.push(this); } }
const fetch = async () => ({ ok: true, json: async () => input.snapshot });
const timers = [];
let timerId = 0;
const setTimeout = (callback, delay) => { timers.push({ id: ++timerId, callback, delay: delay || 0 }); return timerId; };
const setInterval = () => 1;
const clearInterval = () => {};
const requestAnimationFrame = (callback) => setTimeout(callback, 0);

function runTimers(maxDelay) {
  let ran = true;
  while (ran) {
    ran = false;
    const due = timers.filter((t) => t.delay <= maxDelay);
    for (const timer of due) {
      timers.splice(timers.indexOf(timer), 1);
      timer.callback();
      ran = true;
    }
  }
}

function noteSessionOrder() {
  for (const session of input.snapshot.sessions || []) if (!sessionOrder.includes(session.pid)) sessionOrder.push(session.pid);
  for (const frame of input.frames || []) {
    for (const session of frame.sessions || []) if (!sessionOrder.includes(session.pid)) sessionOrder.push(session.pid);
    if (frame.event === "session" && !sessionOrder.includes(frame.pid)) sessionOrder.push(frame.pid);
  }
  sessionOrder.sort((a, b) => a - b);
}

noteSessionOrder();
new Function("document", "window", "fetch", "EventSource", "requestAnimationFrame", "setTimeout", "setInterval", "clearInterval", script)(
  document, window, fetch, EventSource, requestAnimationFrame, setTimeout, setInterval, clearInterval);
await new Promise((resolve) => setImmediate(resolve));
runTimers(0);

const source = sources[0];
if (input.open) source.onopen();
for (const frame of input.frames || []) source.onmessage({ data: JSON.stringify(frame) });
if (input.error) source.onerror();
runTimers(0);
if (input.clickTag !== undefined) {
  fixed.tags.children[input.clickTag].listeners.click();
  runTimers(0);
}
if (input.advanceMs) runTimers(input.advanceMs);

function textOf(node) {
  if (node.text !== undefined) return node.text;
  return (node.textContent || "") + (node.children || []).map(textOf).join("");
}

function capsuleSummary(capsule) {
  const [top, meta, last, watching, badge] = capsule.children;
  const [label, pill] = top.children;
  return { id: capsule.id, pid: String(capsule.dataset.pid), className: capsule.className, label: label.textContent, pill: pill.textContent,
    pillClass: pill.className, meta: meta.textContent, last: last.textContent, lastTitle: last.title, watching: watching.textContent,
    badge: badge ? badge.textContent : null };
}

const rows = fixed.board.children.map((row) => {
  if (row.className === "empty") return { empty: row.textContent };
  const [title, capsules] = row.children;
  return { folder: title.textContent, capsules: capsules.children.map(capsuleSummary) };
});
const lines = fixed.wires.children.map((line) => ({ class: line.attrs.class, x1: Number(line.attrs.x1), y1: Number(line.attrs.y1), x2: Number(line.attrs.x2), y2: Number(line.attrs.y2) }));
const tagSummaries = fixed.tags.children.map((group) => {
  const text = group.children.find((c) => c.tag === "text");
  const title = group.children.find((c) => c.tag === "title");
  return { class: group.attrs.class, text: textOf(text), title: title ? title.textContent : "", clickable: Boolean(group.listeners.click) };
});
const panel = { open: fixed.panel.classList.contains("open"), title: fixed["panel-title"].textContent,
  entries: fixed["panel-list"].children.map((entry) => entry.children.map((c) => c.textContent)) };
console.log(JSON.stringify({ count: fixed.count.textContent, updated: fixed.updated.textContent, link: fixed.link.textContent,
  linkClass: fixed.link.className, eventsUrl: source.url, rows, lines, tags: tagSummaries, panel }));
