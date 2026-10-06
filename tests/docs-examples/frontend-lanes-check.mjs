import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../..", import.meta.url));
const F = (p) => path.join(root, "frontend", p);
const { boardLayout, tracePath, traceKey, assignLanes, laneOptions, traceCorridors } = await import(F("layout.js"));
export const FIXTURES = ["fanin", "generated-many", "generated-mid", "generated-fast", "messages", "rename", "removed", "many"];
const { createState, applySnapshot, applyEvent, liveSessions, sessionByName } = await import(F("state.js"));
export function segments(points) { const out = []; for (let i = 1; i < points.length; i++) { const p = points[i-1], q = points[i]; if (Math.abs(p.x-q.x) < 0.01 && Math.abs(p.y-q.y) < 0.01) continue; out.push(Math.abs(p.x - q.x) < 0.01 ? { v: true, c: p.x, a: Math.min(p.y,q.y), b: Math.max(p.y,q.y) } : { v: false, c: p.y, a: Math.min(p.x,q.x), b: Math.max(p.x,q.x) }); } return out; }
export function sharedSegments(routes) { let shared = 0; for (let i = 0; i < routes.length; i++) for (let j = i+1; j < routes.length; j++) for (const s of segments(routes[i].points)) for (const t of segments(routes[j].points)) if (s.v === t.v && Math.abs(s.c - t.c) < 0.5 && Math.min(s.b, t.b) - Math.max(s.a, t.a) > 0.5) shared++; return shared; }
export function routesFor(fixtureName, { portrait = false, withLanes = true, upTo = Infinity, limitPairs = Infinity } = {}) {
  const fx = JSON.parse(fs.readFileSync(F(`fixtures/${fixtureName}.json`), "utf8")); const s = applySnapshot(createState(), fx.snapshot); for (const e of fx.events) applyEvent(s, e.event, e.data);
  const L = boardLayout(liveSessions(s), { portrait }); const keys = []; const pairs = new Map();
  for (const m of s.messages.slice(0, upTo)) { const f = sessionByName(s, m.from), t = sessionByName(s, m.to); if (!f || !t) continue; const bf = L.capsules.get(f.pid), bt = L.capsules.get(t.pid); if (!bf || !bt) continue; const k = traceKey(f.pid, t.pid); if (!pairs.has(k)) { keys.push(k); pairs.set(k, [bf, bt]); } }
  if (keys.length > limitPairs) keys.length = limitPairs;
  const boxOf = (pid) => L.capsules.get(Number(pid)) ?? L.capsules.get(pid);
  const lanes = assignLanes(keys, { columnOf: (pid) => boxOf(pid)?.index ?? pid, corridorsOf: (k) => { const [a, b] = k.split("|").map(boxOf); return a && b ? traceCorridors(a, b) : []; } });
  const routes = keys.map((k) => { const [bf, bt] = pairs.get(k); return { key: k, ...tracePath(bf, bt, withLanes ? laneOptions(lanes, k, bf, bt) : {}) }; });
  return { routes, keys, lanes, boxes: L.capsules };
}
if (false) {
  for (const f of ["fanin", "generated-many", "generated-mid", "generated-fast", "messages", "many", "rename", "removed"]) {
    for (const portrait of [false, true]) {
      const withL = routesFor(f, { portrait }); const without = routesFor(f, { portrait, withLanes: false });
      console.log(`${f}${portrait ? " (portrait)" : ""}: traces ${withL.routes.length}, shared without lanes ${sharedSegments(without.routes)}, with lanes ${sharedSegments(withL.routes)}`);
    }
  }
  const before = routesFor("fanin", { upTo: 4 }); const after = routesFor("fanin");
  const stable = before.routes.every((r) => after.routes.find((x) => x.key === r.key)?.d === r.d);
  console.log("fanin: adding the fifth pair leaves the first four routes unchanged:", stable);
}

export function crossings(fixtureName, { portrait = false, withLanes = true } = {}) {
  const fx = JSON.parse(fs.readFileSync(F(`fixtures/${fixtureName}.json`), "utf8")); const s = applySnapshot(createState(), fx.snapshot); for (const e of fx.events) applyEvent(s, e.event, e.data);
  const L = boardLayout(liveSessions(s), { portrait }); const { routes } = routesFor(fixtureName, { portrait, withLanes });
  const boxes = [...L.capsules.values()]; const hits = [];
  for (const r of routes) { const [a, b] = r.key.split("|"); for (const seg of segments(r.points)) for (const box of boxes) {
    if (String(box.pid) === a || String(box.pid) === b) continue;
    const inside = seg.v ? (seg.c > box.x + 0.5 && seg.c < box.x + box.width - 0.5 && Math.min(seg.b, box.y + box.height) - Math.max(seg.a, box.y) > 0.5) : (seg.c > box.y + 0.5 && seg.c < box.y + box.height - 0.5 && Math.min(seg.b, box.x + box.width) - Math.max(seg.a, box.x) > 0.5);
    if (inside) hits.push({ trace: r.key, through: box.pid, seg });
  } }
  return hits;
}
if (false) {
  for (const f of ["fanin", "generated-many", "generated-mid", "generated-fast", "messages", "rename", "removed", "many"]) for (const portrait of [false, true]) {
    const h = crossings(f, { portrait }); console.log(`${f}${portrait ? " (portrait)" : ""}: capsule crossings with lanes ${h.length}${h.length ? " " + JSON.stringify(h.slice(0, 3)) : ""}`);
  }
}

export function prefixStable(fixtureName, { portrait = false } = {}) {
  const full = routesFor(fixtureName, { portrait });
  let moved = 0;
  for (let n = 1; n < full.keys.length; n++) {
    const partial = routesFor(fixtureName, { portrait, upTo: Infinity, limitPairs: n });
    for (const r of partial.routes) if (full.routes.find((x) => x.key === r.key)?.d !== r.d) moved++;
  }
  return moved;
}
if (false) {
  for (const f of FIXTURES) for (const portrait of [false, true]) console.log(`${f}${portrait ? " (portrait)" : ""}: routes moved by later pairs ${prefixStable(f, { portrait })}`);
}
