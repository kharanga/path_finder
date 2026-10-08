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

const sessionOrder = [];
const CARD_WIDTH = 272;
const CARD_PITCH = 420;

function makeElement(tag) {
  const element = { tag, children: [], className: "", textContent: "", title: "", id: "", hidden: false, innerHTML: "", dataset: {}, style: {}, attrs: {}, listeners: {},
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren() { this.children = []; },
    setAttribute(name, value) { this.attrs[name] = String(value); },
    addEventListener(type, handler) { this.listeners[type] = handler; },
    get scrollWidth() { return 1200; },
    get scrollHeight() { return 300; },
    getBoundingClientRect() {
      const match = /^session-(\d+)$/.exec(this.id);
      if (!match) return { left: 0, top: 0, width: 1200, height: 300 };
      const order = sessionOrder.indexOf(Number(match[1]));
      return { left: 40 + order * CARD_PITCH, top: 80, width: CARD_WIDTH, height: 180 };
    } };
  element.classList = makeClassList(element);
  return element;
}

const fixed = {};
for (const id of ["board", "count", "updated", "link", "panel", "panel-title", "panel-list", "panel-close"]) fixed[id] = makeElement("div");

function findById(node, id) {
  if (node.id === id) return node;
  for (const child of node.children || []) {
    const found = child.children ? findById(child, id) : null;
    if (found) return found;
  }
  return null;
}

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
let intervalCalls = 0;
const setInterval = () => { intervalCalls += 1; return intervalCalls; };
const clearInterval = () => {};

function runTimers(maxDelay) {
  let ran = true;
  while (ran) {
    ran = false;
    for (const timer of timers.filter((t) => t.delay <= maxDelay)) {
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
new Function("document", "window", "fetch", "EventSource", "setTimeout", "setInterval", "clearInterval", script)(
  document, window, fetch, EventSource, setTimeout, setInterval, clearInterval);
await new Promise((resolve) => setImmediate(resolve));
runTimers(0);

const source = sources[0];
if (input.open) source.onopen();
for (const frame of input.frames || []) source.onmessage({ data: JSON.stringify(frame) });
if (input.error) source.onerror();
runTimers(0);

function strips() {
  return fixed.board.children.filter((row) => row.className === "row").map((row) => row.children[1]);
}

function linksOf(strip) {
  return strip.children.filter((c) => c.className && c.className.startsWith("link"));
}

function arcGroupsOf(strip) {
  return strip.children.filter((c) => c.tag === "svg").flatMap((svg) => svg.children);
}

if (input.clickPair !== undefined) {
  const link = strips().flatMap(linksOf).find((l) => l.dataset.pair === input.clickPair);
  link.listeners.click();
  runTimers(0);
}
if (input.clickArc !== undefined) {
  const group = strips().flatMap(arcGroupsOf)[input.clickArc];
  group.children.find((c) => c.tag === "text").listeners.click();
  runTimers(0);
}
if (input.closePanel) {
  fixed["panel-close"].listeners.click();
  runTimers(0);
}
if (input.advanceMs) runTimers(input.advanceMs);

function textOf(node) {
  if (node.text !== undefined) return node.text;
  return (node.textContent || "") + (node.children || []).map(textOf).join("");
}

function cardSummary(card) {
  const [top, pills, watching, last] = card.children;
  return { id: card.id, pid: card.dataset.pid, status: card.dataset.status, className: card.className, title: card.title,
    label: top.children[1].textContent, dot: top.children[0].style.background,
    pills: pills.children.map((p) => [p.className, p.textContent]),
    watching: textOf(watching), watchingTitle: watching.title, last: last.textContent, lastTitle: last.title };
}

function linkSummary(link) {
  const stage = link.children.find((c) => c.className && c.className.startsWith("stage"));
  return { pair: link.dataset.pair, stage: link.dataset.stage || null, className: link.className, clickable: Boolean(link.listeners.click),
    lines: link.children.map((c) => [c.className, textOf(c)]), stageTitle: stage ? stage.title : "" };
}

function arcSummary(group) {
  const path = group.children.find((c) => c.tag === "path");
  const text = group.children.find((c) => c.tag === "text");
  return { class: group.attrs.class, text: textOf(text), d: path.attrs.d, x: Number(text.attrs.x), y: Number(text.attrs.y), clickable: Boolean(text.listeners.click),
    spans: text.children.filter((c) => c.tag === "tspan").map((c) => [c.attrs.class, c.textContent]) };
}

const rows = fixed.board.children.map((row) => {
  if (row.className === "empty") return { empty: row.textContent };
  const [title, strip, caption] = row.children;
  return { folder: title.textContent, folderHidden: title.hidden, paddingTop: strip.style.paddingTop || "",
    cards: strip.children.filter((c) => c.className && c.className.startsWith("card")).map(cardSummary),
    links: linksOf(strip).map(linkSummary), arcs: arcGroupsOf(strip).map(arcSummary), caption: caption.textContent };
});
const panel = { open: fixed.panel.classList.contains("open"), title: fixed["panel-title"].textContent,
  entries: fixed["panel-list"].children.map((entry) => entry.children.map((c) => c.textContent)) };
console.log(JSON.stringify({ count: fixed.count.textContent, updated: fixed.updated.textContent, link: fixed.link.textContent, linkClass: fixed.link.className,
  eventsUrl: source.url, fallbackPolls: intervalCalls, rows, panel }));
