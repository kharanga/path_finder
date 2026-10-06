import { ringPositions, labelPlacement, truncateLabel } from "./layout.js";
import { liveSessions, sessionLabel } from "./state.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const VIEW_WIDTH = 1200;
const VIEW_HEIGHT = 1000;
const CENTER_X = VIEW_WIDTH / 2;
const CENTER_Y = VIEW_HEIGHT / 2;
const RING_RADIUS = 340;
const BODY_RADIUS = 18;
const LINE_HEIGHT = 22;
const MAX_LABEL_CHARS = 24;

// Builds the Orbit renderer bound to an <svg> element and returns its draw function.
export function createRenderer(svg) {
  svg.setAttribute("viewBox", `0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`);
  const ring = appendTo(svg, "circle", { class: "ring", cx: CENTER_X, cy: CENTER_Y, r: RING_RADIUS });
  const emptyLabel = appendTo(svg, "text", { class: "empty-label", x: CENTER_X, y: CENTER_Y, "text-anchor": "middle" });
  emptyLabel.textContent = "No sessions running";
  const bodiesLayer = appendTo(svg, "g", { class: "bodies" });
  const bodyNodes = new Map();

  return function draw(state) {
    const sessions = liveSessions(state);
    emptyLabel.classList.toggle("hidden", sessions.length > 0);
    ring.classList.toggle("empty", sessions.length === 0);
    const positions = ringPositions(sessions, { cx: CENTER_X, cy: CENTER_Y, radius: RING_RADIUS });
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
  const title = appendTo(group, "title", {});
  const name = appendTo(group, "text", { class: "name" });
  const role = appendTo(group, "text", { class: "role" });
  const node = { group, circle, title, name, role };
  bodyNodes.set(pid, node);
  return node;
}

function updateBodyNode(node, session, position) {
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
  node.title.textContent = session.role ? `${label} (${session.role}) in ${session.folder}` : `${label} in ${session.folder}`;
}

function appendTo(parent, tag, attributes) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  parent.appendChild(element);
  return element;
}
