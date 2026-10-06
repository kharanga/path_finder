import { createState, applySnapshot, applyEvent } from "./state.js";
import { createRenderer } from "./render.js";
import { connect } from "./connect.js";

// Boots the dashboard: wires the event source to the state reducer and the renderer.
export function start({ svg, statusElement }) {
  const state = createState();
  const draw = createRenderer(svg);
  draw(state);
  return connect({
    onSnapshot(snapshot) {
      applySnapshot(state, snapshot);
      draw(state);
    },
    onEvent(name, data) {
      applyEvent(state, name, data);
      draw(state);
    },
    onStatus(status) {
      statusElement.textContent = status;
      statusElement.dataset.status = status;
    },
  });
}

const orbitElement = typeof document === "undefined" ? null : document.getElementById("orbit");
if (orbitElement) start({ svg: orbitElement, statusElement: document.getElementById("status") });
