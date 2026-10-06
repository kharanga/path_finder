import { createState, applySnapshot, applyEvent, prunePlaceholders } from "./state.js";
import { createRenderer } from "./render.js";
import { connect } from "./connect.js";
import { createTimeline, mountTimelineStrip } from "./timeline.js";
import { createPanel } from "./panel.js";

const PLACEHOLDER_SWEEP_MS = 5000;

// Boots the dashboard: wires the event source to the live state, the timeline, and the renderer.
export function start({ svg, statusElement, timelineElement, panelElement }) {
  const liveState = createState();
  const timeline = createTimeline();
  const panel = createPanel(panelElement, { onClose: () => draw.select(null) });
  const draw = createRenderer(svg, {
    onSelect(message, index) {
      panel.show(message, index);
      draw.select(index);
    },
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panelElement.hidden) panel.hide();
  });
  const strip = mountTimelineStrip(timelineElement, timeline, {
    onScrub(tsMs) {
      draw(timeline.stateAt(tsMs), { instant: true });
    },
    onLive() {
      draw(liveState, { instant: true });
    },
  });
  draw(liveState);

  function afterLiveChange() {
    if (strip.isLive) draw(liveState);
    strip.refresh();
  }

  setInterval(() => {
    if (prunePlaceholders(liveState) > 0) afterLiveChange();
  }, PLACEHOLDER_SWEEP_MS);

  return connect({
    onSnapshot(snapshot) {
      const receivedAtMs = Date.now();
      applySnapshot(liveState, snapshot, receivedAtMs);
      timeline.recordSnapshot(snapshot, receivedAtMs);
      afterLiveChange();
    },
    onEvent(name, data) {
      const receivedAtMs = Date.now();
      applyEvent(liveState, name, data, receivedAtMs);
      timeline.record(name, data, receivedAtMs);
      afterLiveChange();
    },
    onStatus(status) {
      statusElement.textContent = status;
      statusElement.dataset.status = status;
    },
  });
}

const orbitElement = typeof document === "undefined" ? null : document.getElementById("orbit");
if (orbitElement) {
  start({
    svg: orbitElement,
    statusElement: document.getElementById("status"),
    timelineElement: document.getElementById("timeline"),
    panelElement: document.getElementById("panel"),
  });
}
