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
    addEventListener(type, handler) { this.listeners[type] = handler; },
    querySelector(selector) { const name = selector.slice(1); return this.children.find((c) => c.className && c.className.split(" ").includes(name)) || null; } };
  element.classList = makeClassList(element);
  return element;
}

const fixed = {};
for (const id of ["graph", "svg", "arrows", "title", "link", "cap-entry", "cap-pair", "strip", "toasts"]) fixed[id] = makeElement("div");
const document = { getElementById: (id) => fixed[id], createElement: makeElement, createElementNS: (_ns, name) => makeElement(name), createTextNode: (text) => ({ text: String(text), parent: null, remove() {} }) };
const windowListeners = {};
const window = { addEventListener(type, handler) { windowListeners[type] = handler; } };
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

new Function("document", "window", "fetch", "EventSource", "setTimeout", "setInterval", "clearInterval", "Date", script)(
  document, window, fetch, EventSource, setTimeout, setInterval, clearInterval, FakeDate);
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
  return { pid: Number(node.dataset.pid), className: node.className, left: node.style.left, top: node.style.top, width: node.style.width, height: node.style.height, title: node.title,
    name: hd ? textOf(findByClass(hd, "name")) : "", dotClass: hd ? findByClass(hd, "dot").className : "", dot: hd ? findByClass(hd, "dot").style.background : "",
    count: hd && findByClass(hd, "n") ? textOf(findByClass(hd, "n")) : null, headEye: headEye ? headEye.className : null,
    pills: row2 ? row2.children.map((p) => [p.className, textOf(p)]) : [], last: last ? textOf(last) : "", lastTitle: last ? last.title : "", eye: eye ? eye.className : null };
}

function labelView(label) {
  const summary = findByClass(label, "esum");
  const stage = label.children.find((c) => c !== summary);
  return { key: label.dataset.key, text: textOf(label), summary: summary ? textOf(summary) : "", stage: stage ? [stage.className, textOf(stage)] : null, opacity: label.style.opacity, left: label.style.left, top: label.style.top, title: label.title };
}

function pathView(path) {
  return { key: path.attrs["data-key"], stage: path.attrs["data-stage"], stroke: path.attrs.stroke, marker: path.attrs["marker-end"], width: path.attrs["stroke-width"], opacity: path.style.opacity, className: path.className, d: path.attrs.d, hoverable: Boolean(path.listeners.mouseenter) };
}

function chipView(chip) {
  const count = findByClass(chip, "n");
  return { pid: Number(chip.dataset.pid), className: chip.className, dotClass: findByClass(chip, "dot").className, text: textOf(chip), count: count ? textOf(count) : null, title: chip.title, clickable: Boolean(chip.listeners.click) };
}

function toastView(toast) {
  if (toast.className === "more" || toast.className === "quiet-toasts") return { className: toast.className, text: textOf(toast) };
  const from = findByClass(toast, "from"), stage = findByClass(toast, "st"), sum = findByClass(toast, "sum");
  return { className: toast.className, key: toast.dataset.key || null, msg: toast.dataset.msg || null, from: from ? textOf(from) : "", fromDots: from ? from.children.filter((c) => c.className && c.className.startsWith("dot")).map((c) => c.style.background) : [],
    stage: stage ? [stage.className, textOf(stage), stage.title] : null, sum: sum ? textOf(sum) : null, sumTitle: sum ? sum.title : null, hoverable: Boolean(toast.listeners.mouseenter) };
}

function view() {
  const quiet = fixed.graph.querySelector(".quiet");
  return { title: fixed.title.textContent, link: fixed.link.textContent, linkClass: fixed.link.className, eventsUrl: source.url, intervals: intervals.map((i) => i.delay),
    caption: [fixed["cap-entry"].textContent, fixed["cap-pair"].textContent], pod: fixed.graph.classList.contains("pod"), viewBox: fixed.svg.attrs.viewBox, quiet: quiet ? textOf(quiet) : null,
    nodes: fixed.graph.children.filter((c) => c.className.startsWith("node")).map(nodeView), labels: fixed.graph.children.filter((c) => c.className.startsWith("elab")).map(labelView),
    paths: fixed.arrows.children.map(pathView), chips: fixed.strip.children.map(chipView), toasts: fixed.toasts.children.map(toastView) };
}

const out = [];
for (const step of input.steps || []) {
  for (const frame of step.frames || []) source.onmessage({ data: JSON.stringify(frame) });
  if (step.error) source.onerror();
  if (step.reopen) source.onopen();
  if (step.advanceMs) wallMs += step.advanceMs;
  if (step.clickChip !== undefined) fixed.strip.children.find((c) => Number(c.dataset.pid) === Number(step.clickChip)).listeners.click();
  if (step.clickNode !== undefined) fixed.graph.children.find((c) => c.className.startsWith("node") && Number(c.dataset.pid) === Number(step.clickNode)).listeners.click();
  if (step.hoverToast !== undefined) fixed.toasts.children[step.hoverToast].listeners.mouseenter();
  if (step.hoverPath !== undefined) fixed.arrows.children.find((p) => p.attrs["data-key"] === step.hoverPath).listeners.mouseenter();
  if (step.leaveToast !== undefined) fixed.toasts.children[step.leaveToast].listeners.mouseleave();
  if (step.resize) windowListeners.resize();
  runTimers();
  tick();
  out.push({ name: step.name, view: view() });
}
console.log(JSON.stringify(out));
