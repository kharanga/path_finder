import { boardLayout, tracePath, traceKey, edgeBox, truncateLabel, boardFor, CAPSULE } from "./layout.js";
import { liveSessions, sessionLabel, sessionByName } from "./state.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const MAX_LABEL_CHARS = 21;
const PULSE_RADIUS = 6;
const PULSE_HIT_RADIUS = 18;
const DEFAULT_GHOST_MS = 8000;
const DEFAULT_TRAVEL_MS = 1200;
const DEFAULT_LINGER_MS = 15000;
const DRAIN_MS = 600;
const POWER_ON_MS = 1000;
const RENAME_HIGHLIGHT_MS = 1800;

// Builds the Circuit renderer bound to an <svg> element and returns its draw function.
export function createRenderer(svg, { ghostMs = DEFAULT_GHOST_MS, travelMs = DEFAULT_TRAVEL_MS, lingerMs = DEFAULT_LINGER_MS, reducedMotion = detectReducedMotion(), onSelect = null, onRemove = null, portrait = false } = {}) {
  let activeBoard = boardFor(portrait);
  svg.setAttribute("viewBox", `0 0 ${activeBoard.width} ${activeBoard.height}`);
  const board = appendTo(svg, "rect", { class: "board", x: 0, y: 0, width: activeBoard.width, height: activeBoard.height });
  const emptyLabel = appendTo(svg, "text", { class: "empty-label", x: activeBoard.width / 2, y: activeBoard.height / 2, "text-anchor": "middle" });
  emptyLabel.textContent = "No sessions running";
  const rowsLayer = appendTo(svg, "g", { class: "rows" });
  const tracesLayer = appendTo(svg, "g", { class: "traces" });
  const chargesLayer = appendTo(svg, "g", { class: "charges" });
  const capsulesLayer = appendTo(svg, "g", { class: "capsules" });
  const pulsesLayer = appendTo(svg, "g", { class: "pulses" });
  const capsuleNodes = new Map();
  const traceNodes = new Map();
  const chargeNodes = new Map();
  const lastBoxes = new Map();
  const rowLabelNodes = new Map();
  const options = { ghostMs, travelMs, lingerMs, reducedMotion, onSelect, onRemove, portrait, editing: false };
  watchReducedMotion((reduce) => { options.reducedMotion = reduce; });
  let drawnMessageCount = 0;
  let drawnSnapshotSeq = null;
  let pulseSerial = 0;

  function boxForName(state, name) {
    const session = sessionByName(state, name);
    return (session && lastBoxes.get(session.pid)) || null;
  }

  function endpoints(state, message) {
    const to = boxForName(state, message.to);
    const from = boxForName(state, message.from);
    if (to && from) return { from, to, real: true };
    if (to) return { from: edgeBox(to), to, real: false };
    if (from) return { from, to: edgeBox(from), real: false };
    const fallback = { pid: null, folder: "", x: activeBoard.width / 2, y: activeBoard.height / 2 - CAPSULE.height / 2, width: 0, height: CAPSULE.height, cx: activeBoard.width / 2, cy: activeBoard.height / 2, line: -1, index: -1 };
    return { from: fallback, to: fallback, real: false };
  }

  function ensureTrace(from, to) {
    const key = traceKey(from.pid, to.pid);
    let node = traceNodes.get(key);
    if (!node) {
      const path = appendTo(tracesLayer, "path", { class: "trace", "data-trace": key, d: tracePath(from, to).d });
      node = { path, a: from.pid, b: to.pid };
      traceNodes.set(key, node);
    }
    return node;
  }

  function rerouteTraces() {
    for (const [key, node] of traceNodes) {
      const a = lastBoxes.get(node.a);
      const b = lastBoxes.get(node.b);
      if (!a || !b) {
        node.path.remove();
        traceNodes.delete(key);
        continue;
      }
      node.path.setAttribute("d", tracePath(a, b).d);
    }
  }

  function draw(state, { instant = false } = {}) {
    const sessions = liveSessions(state);
    emptyLabel.classList.toggle("hidden", sessions.length > 0);
    board.classList.toggle("empty", sessions.length === 0);
    const layout = boardLayout(sessions, { portrait: options.portrait });
    drawRowLabels(rowsLayer, rowLabelNodes, layout.rows);
    const seen = new Set();
    for (const session of sessions) {
      seen.add(session.pid);
      const box = layout.capsules.get(session.pid);
      lastBoxes.set(session.pid, box);
      const node = capsuleNodes.get(session.pid) ?? createCapsuleNode(capsulesLayer, capsuleNodes, session, box, instant, options);
      updateCapsuleNode(node, session, box, options);
    }
    for (const [pid, node] of capsuleNodes) {
      if (seen.has(pid)) continue;
      const removed = state.sessions.get(pid)?.state === "removed";
      const slotReused = node.box && sessions.some((session) => boxesOverlap(node.box, layout.capsules.get(session.pid)));
      if (instant || removed || slotReused) removeCapsule(node, capsuleNodes, lastBoxes, pid);
      else if (!node.ghostTimer) startFootprint(node, capsuleNodes, lastBoxes, pid, ghostMs);
    }

    if (state.snapshotSeq !== drawnSnapshotSeq) {
      drawnSnapshotSeq = state.snapshotSeq;
      drawnMessageCount = state.messages.length;
      clearLayer(pulsesLayer);
      clearLayer(chargesLayer);
      clearLayer(tracesLayer);
      traceNodes.clear();
      chargeNodes.clear();
      for (const message of state.messages) {
        const ends = endpoints(state, message);
        if (ends.real) ensureTrace(ends.from, ends.to);
      }
    }
    for (let index = drawnMessageCount; index < state.messages.length; index++) {
      const message = state.messages[index];
      const ends = endpoints(state, message);
      if (ends.real) ensureTrace(ends.from, ends.to);
      spawnPulse(pulsesLayer, message, index, ends.from, ends.to, options, `pulse-path-${pulseSerial++}`);
    }
    drawnMessageCount = state.messages.length;
    rerouteTraces();

    const chargeOptions = instant ? { ...options, reducedMotion: true } : options;
    for (const thread of state.threads) {
      const ends = endpoints(state, thread);
      updateChargeNode(chargesLayer, chargeNodes, thread, ends.from, ends.to, chargeOptions);
    }
  }

  // Switches between the landscape and the portrait board; the next draw re-lays everything out.
  draw.setPortrait = function setPortrait(portrait) {
    if (options.portrait === portrait) return;
    options.portrait = portrait;
    activeBoard = boardFor(portrait);
    svg.setAttribute("viewBox", `0 0 ${activeBoard.width} ${activeBoard.height}`);
    board.setAttribute("width", activeBoard.width);
    board.setAttribute("height", activeBoard.height);
    emptyLabel.setAttribute("x", activeBoard.width / 2);
    emptyLabel.setAttribute("y", activeBoard.height / 2);
  };

  // Shows or hides the per-capsule remove controls.
  draw.setEditing = function setEditing(editing) {
    options.editing = editing;
    svg.classList.toggle("editing", editing);
    for (const node of capsuleNodes.values()) syncRemoveControl(node, editing);
  };

  // Marks the pulse for one message index as selected, or clears the selection with null.
  draw.select = function select(index) {
    for (const pulse of pulsesLayer.querySelectorAll(".pulse")) {
      pulse.classList.toggle("selected", index !== null && pulse.dataset.messageIndex === String(index));
    }
  };

  return draw;
}

function drawRowLabels(layer, rowLabelNodes, rows) {
  const seen = new Set();
  for (const row of rows) {
    seen.add(row.folder);
    let text = rowLabelNodes.get(row.folder);
    if (!text) {
      text = appendTo(layer, "text", { class: "row-label", x: 0, y: 0, dy: "0.35em", "data-folder": row.folder });
      text.textContent = truncateLabel(row.label, 14);
      text.style.transform = `translate(${row.labelX}px, ${row.labelY.toFixed(1)}px)`;
      flushStyles(text);
      rowLabelNodes.set(row.folder, text);
    }
    text.setAttribute("text-anchor", row.anchor);
    text.style.transform = `translate(${row.labelX}px, ${row.labelY.toFixed(1)}px)`;
  }
  for (const [folder, text] of rowLabelNodes) {
    if (seen.has(folder)) continue;
    text.remove();
    rowLabelNodes.delete(folder);
  }
}

function spawnPulse(layer, message, index, from, to, { travelMs, lingerMs, reducedMotion, onSelect }, pathId) {
  const route = tracePath(from, to);
  const group = appendTo(layer, "g", { class: message.notify_on_idle ? "pulse notify" : "pulse", "data-message-index": index, role: "button", tabindex: "0" });
  appendTo(group, "path", { id: pathId, class: "pulse-path", d: route.d });
  const hit = appendTo(group, "circle", { class: "pulse-hit", r: PULSE_HIT_RADIUS, cx: to.cx, cy: to.cy });
  const dot = appendTo(group, "circle", { class: "pulse-dot", r: PULSE_RADIUS });
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
    dot.setAttribute("cx", to.cx);
    dot.setAttribute("cy", to.cy);
    settle();
    return group;
  }
  const motion = appendTo(dot, "animateMotion", { dur: `${travelMs}ms`, fill: "freeze", calcMode: "spline", keySplines: "0.4 0 0.2 1", keyTimes: "0;1" });
  const mpath = appendTo(motion, "mpath", {});
  mpath.setAttribute("href", `#${pathId}`);
  mpath.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", `#${pathId}`);
  hit.classList.add("hidden");
  setTimeout(() => hit.classList.remove("hidden"), travelMs);
  setTimeout(settle, travelMs);
  return group;
}

function updateChargeNode(layer, chargeNodes, thread, from, to, { travelMs, reducedMotion }) {
  let node = chargeNodes.get(thread.id);
  if (thread.status === "waiting") {
    const route = tracePath(from, to);
    if (!node) {
      const path = appendTo(layer, "path", { class: "charge drawing", "data-thread-id": thread.id, d: route.d });
      path.setAttribute("stroke-dasharray", route.length);
      path.setAttribute("stroke-dashoffset", reducedMotion ? 0 : route.length);
      path.style.setProperty("--draw-ms", `${travelMs}ms`);
      node = { path, length: route.length, finishing: false };
      chargeNodes.set(thread.id, node);
      flushStyles(path);
      path.setAttribute("stroke-dashoffset", 0);
      path.classList.remove("drawing");
      return;
    }
    node.path.setAttribute("d", route.d);
    node.path.setAttribute("stroke-dasharray", route.length);
    node.length = route.length;
    return;
  }
  if (!node || node.finishing) return;
  node.finishing = true;
  node.path.classList.add(thread.status === "snapped" ? "draining" : "dropping");
  if (thread.status === "snapped") node.path.setAttribute("stroke-dashoffset", node.length);
  setTimeout(() => {
    node.path.remove();
    chargeNodes.delete(thread.id);
  }, reducedMotion ? 0 : DRAIN_MS);
}

function startFootprint(node, capsuleNodes, lastBoxes, pid, ghostMs) {
  node.session = { ...node.session, state: "ended" };
  node.group.dataset.state = "ended";
  node.group.classList.add("leaving");
  node.ghostTimer = setTimeout(() => removeCapsule(node, capsuleNodes, lastBoxes, pid), ghostMs);
}

function removeCapsule(node, capsuleNodes, lastBoxes, pid) {
  if (node.ghostTimer) clearTimeout(node.ghostTimer);
  if (node.powerTimer) clearTimeout(node.powerTimer);
  if (node.renameTimer) clearTimeout(node.renameTimer);
  node.group.remove();
  capsuleNodes.delete(pid);
  lastBoxes.delete(pid);
}

function createCapsuleNode(layer, capsuleNodes, session, box, instant = false, options = {}) {
  const group = appendTo(layer, "g", { class: instant ? "capsule" : "capsule entering", "data-pid": session.pid, tabindex: "0", role: "img" });
  group.style.transform = translateTo(box);
  const shell = appendTo(group, "rect", { class: "shell", x: 0, y: 0, width: box.width, height: box.height, rx: CAPSULE.cornerRadius, ry: CAPSULE.cornerRadius });
  const title = appendTo(group, "title", {});
  const name = appendTo(group, "text", { class: "name", x: box.width / 2, "text-anchor": "middle" });
  const role = appendTo(group, "text", { class: "role", x: box.width / 2, "text-anchor": "middle" });
  const node = { group, shell, title, name, role, remove: null, session, box, ghostTimer: null, powerTimer: null, lastLabel: null, renameTimer: null };
  if (options.onRemove && session.state !== "placeholder") {
    const remove = appendTo(group, "g", { class: "remove", role: "button", tabindex: "-1" });
    appendTo(remove, "circle", { cx: box.width, cy: 0, r: 13 });
    const cross = appendTo(remove, "text", { x: box.width, y: 0, dy: "0.35em", "text-anchor": "middle" });
    cross.textContent = "×";
    const activate = (event) => {
      event.preventDefault();
      event.stopPropagation?.();
      options.onRemove(node.session);
    };
    remove.addEventListener("click", activate);
    remove.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") activate(event);
    });
    node.remove = remove;
    syncRemoveControl(node, options.editing);
  }
  capsuleNodes.set(session.pid, node);
  flushStyles(group);
  group.classList.remove("entering");
  if (session.state === "started" && !instant) powerOn(node);
  return node;
}

function boxesOverlap(a, b) {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

function updateCapsuleNode(node, session, box, options = {}) {
  node.session = session;
  node.box = box;
  if (node.ghostTimer) {
    clearTimeout(node.ghostTimer);
    node.ghostTimer = null;
    node.group.classList.remove("leaving");
  }
  node.group.style.transform = translateTo(box);
  node.group.dataset.state = session.state;
  node.group.dataset.folder = session.folder;
  const label = sessionLabel(session);
  const hasRole = Boolean(session.role);
  node.name.setAttribute("y", hasRole ? box.height / 2 - 4 : box.height / 2 + 7);
  node.role.setAttribute("y", box.height / 2 + 18);
  node.name.textContent = truncateLabel(label, MAX_LABEL_CHARS);
  if (node.lastLabel !== null && node.lastLabel !== label) highlightRename(node);
  node.lastLabel = label;
  node.role.textContent = session.role ?? "";
  node.role.classList.toggle("hidden", !hasRole);
  const formerly = session.formerNames?.length ? `, formerly ${session.formerNames.join(", ")}` : "";
  if (session.state === "placeholder") node.title.textContent = `${label}, no session event yet (folder guessed: ${session.folder})`;
  else node.title.textContent = `${hasRole ? `${label} (${session.role})` : label} in ${session.folder}${formerly}`;
  node.group.setAttribute("aria-label", `${label}, ${session.state}${hasRole ? `, ${session.role}` : ""}, folder ${session.folder}`);
  if (node.remove) node.remove.setAttribute("aria-label", `Remove ${label}`);
}

function syncRemoveControl(node, editing) {
  if (!node.remove) return;
  node.remove.setAttribute("tabindex", editing ? "0" : "-1");
  node.remove.setAttribute("aria-hidden", editing ? "false" : "true");
}

function powerOn(node) {
  node.group.classList.add("powering");
  node.powerTimer = setTimeout(() => {
    node.group.classList.remove("powering");
    node.powerTimer = null;
  }, POWER_ON_MS);
}

function highlightRename(node) {
  if (node.renameTimer) clearTimeout(node.renameTimer);
  node.group.classList.remove("renamed");
  flushStyles(node.group);
  node.group.classList.add("renamed");
  node.renameTimer = setTimeout(() => {
    node.group.classList.remove("renamed");
    node.renameTimer = null;
  }, RENAME_HIGHLIGHT_MS);
}

function translateTo(box) {
  return `translate(${box.x.toFixed(1)}px, ${box.y.toFixed(1)}px)`;
}

function flushStyles(element) {
  if (typeof element.getBoundingClientRect === "function") element.getBoundingClientRect();
}

function detectReducedMotion() {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function watchReducedMotion(onChange) {
  if (typeof matchMedia !== "function") return;
  const query = matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener?.("change", (event) => onChange(event.matches));
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
