import { ringPositions, labelSide } from "./layout.js";
import { liveSessions, sessionLabel } from "./state.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const VIEW_SIZE = 1000;
const RING_RADIUS = 360;
const BODY_RADIUS = 18;

// Builds the Orbit renderer bound to an <svg> element and returns its draw function.
export function createRenderer(svg) {
  svg.setAttribute("viewBox", `0 0 ${VIEW_SIZE} ${VIEW_SIZE}`);
  const ring = appendTo(svg, "circle", { class: "ring", cx: VIEW_SIZE / 2, cy: VIEW_SIZE / 2, r: RING_RADIUS });
  const emptyLabel = appendTo(svg, "text", { class: "empty-label", x: VIEW_SIZE / 2, y: VIEW_SIZE / 2, "text-anchor": "middle" });
  emptyLabel.textContent = "No sessions running";
  const bodiesLayer = appendTo(svg, "g", { class: "bodies" });
  const bodyNodes = new Map();

  return function draw(state) {
    const sessions = liveSessions(state);
    emptyLabel.classList.toggle("hidden", sessions.length > 0);
    ring.classList.toggle("empty", sessions.length === 0);
    const positions = ringPositions(sessions, { cx: VIEW_SIZE / 2, cy: VIEW_SIZE / 2, radius: RING_RADIUS });
    const seen = new Set();
    for (const session of sessions) {
      seen.add(session.pid);
      const node = bodyNodes.get(session.pid) ?? createBodyNode(bodiesLayer, bodyNodes, session.pid);
      updateBodyNode(node, session, positions.get(session.pid));
    }
    for (const [pid, node] of bodyNodes) {
      if (!seen.has(pid)) {
        node.group.remove();
        bodyNodes.delete(pid);
      }
    }
  };
}

function createBodyNode(layer, bodyNodes, pid) {
  const group = appendTo(layer, "g", { class: "body", "data-pid": pid });
  const circle = appendTo(group, "circle", { r: BODY_RADIUS });
  const name = appendTo(group, "text", { class: "name", dy: "0.35em" });
  const role = appendTo(group, "text", { class: "role", dy: "1.6em" });
  const node = { group, circle, name, role };
  bodyNodes.set(pid, node);
  return node;
}

function updateBodyNode(node, session, position) {
  node.group.setAttribute("transform", `translate(${position.x.toFixed(1)} ${position.y.toFixed(1)})`);
  node.group.dataset.state = session.state;
  const side = labelSide(position.angle);
  const offset = BODY_RADIUS + 14;
  const labelX = side === "right" ? offset : side === "left" ? -offset : 0;
  const labelY = side === "center" ? (Math.sin(position.angle) < 0 ? -offset - 6 : offset + 10) : 0;
  const anchor = side === "right" ? "start" : side === "left" ? "end" : "middle";
  for (const text of [node.name, node.role]) {
    text.setAttribute("x", labelX);
    text.setAttribute("y", labelY);
    text.setAttribute("text-anchor", anchor);
  }
  node.name.textContent = sessionLabel(session);
  node.role.textContent = session.role ?? "";
  node.role.classList.toggle("hidden", !session.role);
}

function appendTo(parent, tag, attributes) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  parent.appendChild(element);
  return element;
}
