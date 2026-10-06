import { ringPositions, labelPlacement, truncateLabel, messageCurve } from "./layout.js";
import { liveSessions, sessionLabel, sessionByName } from "./state.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const VIEW_WIDTH = 1360;
const VIEW_HEIGHT = 1000;
const CENTER = { x: VIEW_WIDTH / 2, y: VIEW_HEIGHT / 2 };
const RING_RADIUS = 340;
const BODY_RADIUS = 18;
const LINE_HEIGHT = 22;
const MAX_LABEL_CHARS = 24;
const HALO_RADIUS = BODY_RADIUS + 12;
const PARTICLE_RADIUS = 6;
const DEFAULT_GHOST_MS = 8000;
const DEFAULT_TRAVEL_MS = 1200;
const DEFAULT_LINGER_MS = 15000;
const PARTICLE_HIT_RADIUS = 16;
const SNAP_MS = 600;

// Builds the Orbit renderer bound to an <svg> element and returns its draw function.
export function createRenderer(svg, { ghostMs = DEFAULT_GHOST_MS, travelMs = DEFAULT_TRAVEL_MS, lingerMs = DEFAULT_LINGER_MS, reducedMotion = detectReducedMotion(), onSelect = null } = {}) {
  svg.setAttribute("viewBox", `0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`);
  const ring = appendTo(svg, "circle", { class: "ring", cx: CENTER.x, cy: CENTER.y, r: RING_RADIUS });
  const emptyLabel = appendTo(svg, "text", { class: "empty-label", x: CENTER.x, y: CENTER.y, "text-anchor": "middle" });
  emptyLabel.textContent = "No sessions running";
  const threadsLayer = appendTo(svg, "g", { class: "threads" });
  const bodiesLayer = appendTo(svg, "g", { class: "bodies" });
  const particlesLayer = appendTo(svg, "g", { class: "particles" });
  const bodyNodes = new Map();
  const threadNodes = new Map();
  const lastPositions = new Map();
  const options = { ghostMs, travelMs, lingerMs, reducedMotion, onSelect };
  let drawnMessageCount = 0;
  let drawnSnapshotSeq = null;
  let particleSerial = 0;

  function positionForName(state, name) {
    const session = sessionByName(state, name);
    return (session && lastPositions.get(session.pid)) || null;
  }

  function draw(state, { instant = false } = {}) {
    const sessions = liveSessions(state);
    emptyLabel.classList.toggle("hidden", sessions.length > 0);
    ring.classList.toggle("empty", sessions.length === 0);
    const positions = ringPositions(sessions, { cx: CENTER.x, cy: CENTER.y, radius: RING_RADIUS });
    const seen = new Set();
    for (const session of sessions) {
      seen.add(session.pid);
      const position = positions.get(session.pid);
      lastPositions.set(session.pid, { x: position.x, y: position.y });
      const node = bodyNodes.get(session.pid) ?? createBodyNode(bodiesLayer, bodyNodes, session.pid, instant);
      updateBodyNode(node, session, position);
    }
    for (const [pid, node] of bodyNodes) {
      if (seen.has(pid)) continue;
      if (instant) removeBody(node, bodyNodes, lastPositions, pid);
      else if (!node.ghostTimer) startGhost(node, bodyNodes, lastPositions, pid, ghostMs);
    }

    if (state.snapshotSeq !== drawnSnapshotSeq) {
      drawnSnapshotSeq = state.snapshotSeq;
      drawnMessageCount = state.messages.length;
      clearLayer(particlesLayer);
      clearLayer(threadsLayer);
      threadNodes.clear();
    }
    for (let index = drawnMessageCount; index < state.messages.length; index++) {
      const message = state.messages[index];
      const from = positionForName(state, message.from) ?? CENTER;
      const to = positionForName(state, message.to) ?? CENTER;
      spawnParticle(particlesLayer, message, index, from, to, options, `particle-path-${particleSerial++}`);
    }
    drawnMessageCount = state.messages.length;

    const threadOptions = instant ? { ...options, reducedMotion: true } : options;
    for (const thread of state.threads) {
      const from = positionForName(state, thread.from) ?? CENTER;
      const to = positionForName(state, thread.to) ?? CENTER;
      updateThreadNode(threadsLayer, threadNodes, thread, from, to, threadOptions);
    }
  }

  // Marks the particle for one message index as selected, or clears the selection with null.
  draw.select = function select(index) {
    for (const particle of particlesLayer.querySelectorAll(".particle")) {
      particle.classList.toggle("selected", index !== null && particle.dataset.messageIndex === String(index));
    }
  };

  return draw;
}

function removeBody(node, bodyNodes, lastPositions, pid) {
  if (node.ghostTimer) clearTimeout(node.ghostTimer);
  node.group.remove();
  bodyNodes.delete(pid);
  lastPositions.delete(pid);
}

function spawnParticle(layer, message, index, from, to, { travelMs, lingerMs, reducedMotion, onSelect }, pathId) {
  const curve = messageCurve(from, to, CENTER);
  const group = appendTo(layer, "g", { class: message.notify_on_idle ? "particle notify" : "particle", "data-message-index": index, role: "button", tabindex: "0" });
  const path = appendTo(group, "path", { id: pathId, class: "particle-path", d: curve.d });
  const hit = appendTo(group, "circle", { class: "particle-hit", r: PARTICLE_HIT_RADIUS, cx: to.x, cy: to.y });
  const dot = appendTo(group, "circle", { class: "particle-dot", r: PARTICLE_RADIUS });
  const title = appendTo(group, "title", {});
  const sender = typeof message.from === "string" ? message.from : "unknown sender";
  title.textContent = `${sender} → ${message.to}: ${message.text}`;
  group.setAttribute("aria-label", `Message from ${sender} to ${message.to}`);
  if (onSelect) {
    const select = (event) => {
      event.preventDefault();
      onSelect(message, index);
    };
    group.addEventListener("click", select);
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") select(event);
    });
  }
  const settle = () => {
    group.classList.add("arrived");
    setTimeout(() => group.remove(), lingerMs);
  };
  if (reducedMotion) {
    dot.setAttribute("cx", to.x);
    dot.setAttribute("cy", to.y);
    settle();
    return group;
  }
  hit.classList.add("hidden");
  setTimeout(() => hit.classList.remove("hidden"), travelMs);
  const motion = appendTo(dot, "animateMotion", { dur: `${travelMs}ms`, fill: "freeze", calcMode: "spline", keySplines: "0.4 0 0.2 1", keyTimes: "0;1" });
  const mpath = appendTo(motion, "mpath", {});
  mpath.setAttribute("href", `#${pathId}`);
  mpath.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", `#${pathId}`);
  setTimeout(settle, travelMs);
  return group;
}

function updateThreadNode(layer, threadNodes, thread, from, to, { travelMs, reducedMotion }) {
  let node = threadNodes.get(thread.id);
  if (thread.status === "waiting") {
    const curve = messageCurve(from, to, CENTER);
    if (!node) {
      const path = appendTo(layer, "path", { class: "thread drawing", "data-thread-id": thread.id, d: curve.d });
      path.setAttribute("stroke-dasharray", curve.length);
      path.setAttribute("stroke-dashoffset", reducedMotion ? 0 : curve.length);
      path.style.setProperty("--draw-ms", `${travelMs}ms`);
      node = { path, length: curve.length, finishing: false };
      threadNodes.set(thread.id, node);
      flushStyles(path);
      path.setAttribute("stroke-dashoffset", 0);
      path.classList.remove("drawing");
      return;
    }
    node.path.setAttribute("d", curve.d);
    node.path.setAttribute("stroke-dasharray", curve.length);
    node.length = curve.length;
    return;
  }
  if (!node || node.finishing) return;
  node.finishing = true;
  node.path.classList.add(thread.status === "snapped" ? "snapping" : "dropping");
  if (thread.status === "snapped") node.path.setAttribute("stroke-dashoffset", node.length);
  setTimeout(() => {
    node.path.remove();
    threadNodes.delete(thread.id);
  }, reducedMotion ? 0 : SNAP_MS);
}

function startGhost(node, bodyNodes, lastPositions, pid, ghostMs) {
  node.group.dataset.state = "ended";
  node.group.classList.add("leaving");
  node.ghostTimer = setTimeout(() => {
    node.group.remove();
    bodyNodes.delete(pid);
    lastPositions.delete(pid);
  }, ghostMs);
}

function createBodyNode(layer, bodyNodes, pid, instant = false) {
  const group = appendTo(layer, "g", { class: instant ? "body" : "body entering", "data-pid": pid });
  appendTo(group, "circle", { class: "halo", r: HALO_RADIUS });
  const circle = appendTo(group, "circle", { class: "core", r: BODY_RADIUS });
  const title = appendTo(group, "title", {});
  const name = appendTo(group, "text", { class: "name" });
  const role = appendTo(group, "text", { class: "role" });
  const node = { group, circle, title, name, role, ghostTimer: null };
  bodyNodes.set(pid, node);
  flushStyles(group);
  group.classList.remove("entering");
  return node;
}

function updateBodyNode(node, session, position) {
  if (node.ghostTimer) {
    clearTimeout(node.ghostTimer);
    node.ghostTimer = null;
    node.group.classList.remove("leaving");
  }
  node.group.style.transform = `translate(${position.x.toFixed(1)}px, ${position.y.toFixed(1)}px)`;
  node.group.dataset.state = session.state;
  node.group.dataset.folder = session.folder;
  const label = sessionLabel(session);
  const placement = labelPlacement(position.angle, { bodyRadius: BODY_RADIUS, lineHeight: LINE_HEIGHT, hasRole: Boolean(session.role) });
  for (const text of [node.name, node.role]) {
    text.setAttribute("x", placement.x);
    text.setAttribute("text-anchor", placement.anchor);
  }
  node.name.setAttribute("y", placement.nameY);
  node.role.setAttribute("y", placement.roleY);
  node.name.textContent = truncateLabel(label, MAX_LABEL_CHARS);
  node.role.textContent = session.role ?? "";
  node.role.classList.toggle("hidden", !session.role);
  if (session.state === "placeholder") node.title.textContent = `${label}, no session event yet (folder guessed: ${session.folder})`;
  else node.title.textContent = session.role ? `${label} (${session.role}) in ${session.folder}` : `${label} in ${session.folder}`;
}

function flushStyles(element) {
  if (typeof element.getBoundingClientRect === "function") element.getBoundingClientRect();
}

function detectReducedMotion() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function clearLayer(layer) {
  while (layer.firstChild) layer.removeChild(layer.firstChild);
}

function appendTo(parent, tag, attributes) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  parent.appendChild(element);
  return element;
}
