import { readFileSync } from "node:fs";

const [htmlPath, inputPath] = process.argv.slice(2);
const html = readFileSync(htmlPath, "utf8");
const input = JSON.parse(readFileSync(inputPath, "utf8"));
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function makeElement(tag) {
  return { tag, children: [], className: "", textContent: "", title: "", id: "", dataset: {},
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren() { this.children = []; } };
}

const byId = { board: makeElement("main"), count: makeElement("span"), updated: makeElement("span"), link: makeElement("span") };
const document = { getElementById: (id) => byId[id], createElement: makeElement };
const sources = [];
class EventSource { constructor(url) { this.url = url; sources.push(this); } }
const fetch = async () => ({ ok: true, json: async () => input.snapshot });
const requestAnimationFrame = (callback) => callback();
const setInterval = () => 1;
const clearInterval = () => {};

new Function("document", "fetch", "EventSource", "requestAnimationFrame", "setInterval", "clearInterval", script)(
  document, fetch, EventSource, requestAnimationFrame, setInterval, clearInterval);
await new Promise((resolve) => setImmediate(resolve));

const source = sources[0];
if (input.open) source.onopen();
for (const frame of input.frames || []) source.onmessage({ data: JSON.stringify(frame) });
if (input.error) source.onerror();

function capsuleSummary(capsule) {
  const [top, meta, last, watching, badge] = capsule.children;
  const [label, pill] = top.children;
  return { id: capsule.id, pid: String(capsule.dataset.pid), className: capsule.className, label: label.textContent, pill: pill.textContent,
    pillClass: pill.className, meta: meta.textContent, last: last.textContent, lastTitle: last.title, watching: watching.textContent,
    badge: badge ? badge.textContent : null };
}

const rows = byId.board.children.map((row) => {
  if (row.className === "empty") return { empty: row.textContent };
  const [title, capsules] = row.children;
  return { folder: title.textContent, capsules: capsules.children.map(capsuleSummary) };
});
console.log(JSON.stringify({ count: byId.count.textContent, updated: byId.updated.textContent, link: byId.link.textContent,
  linkClass: byId.link.className, eventsUrl: source.url, rows }));
