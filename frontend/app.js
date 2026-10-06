import { createState, applySnapshot, applyEvent, prunePlaceholders } from "./state.js";
import { createRenderer } from "./render.js";
import { connect } from "./connect.js";
import { createTimeline, mountTimelineStrip } from "./timeline.js";
import { createPanel } from "./panel.js";
import { createEditor } from "./editor.js";

const PLACEHOLDER_SWEEP_MS = 5000;

// Boots the dashboard: wires the event source to the live state, the timeline, and the renderer.
export function start({ svg, statusElement, timelineElement, panelElement, editorElements }) {
  const liveState = createState();
  const timeline = createTimeline();
  const panel = createPanel(panelElement, { onClose: () => draw.select(null) });
  const portraitQuery = typeof matchMedia === "function" ? matchMedia("(max-width: 600px)") : null;
  const draw = createRenderer(svg, {
    reducedMotion: forcedReducedMotion(),
    portrait: Boolean(portraitQuery?.matches),
    onSelect(message, index) {
      panel.show(message, index);
      draw.select(index);
    },
    onRemove(session) {
      editor.requestRemove(session);
    },
  });
  const editor = createEditor({ ...editorElements, getState: () => liveState, draw });
  portraitQuery?.addEventListener?.("change", (event) => {
    draw.setPortrait(event.matches);
    draw(strip.isLive ? liveState : timeline.stateAt(Number(timelineElement.querySelector("[data-role=scrubber]").value)), { instant: true });
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
    onTick(message) {
      panel.show(message, null);
      draw.select(null);
    },
  });
  draw(liveState);

  function afterLiveChange() {
    if (strip.isLive) draw(liveState);
    strip.refresh();
    editor.refresh();
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
      editor.setAvailable(status === "live" || status === "reconnecting");
    },
  });
}

function forcedReducedMotion() {
  if (typeof location === "undefined") return undefined;
  const motion = new URLSearchParams(location.search).get("motion");
  if (motion === "reduce") return true;
  if (motion === "full") return false;
  return undefined;
}

const orbitElement = typeof document === "undefined" ? null : document.getElementById("orbit");
if (orbitElement) {
  start({
    svg: orbitElement,
    statusElement: document.getElementById("status"),
    timelineElement: document.getElementById("timeline"),
    panelElement: document.getElementById("panel"),
    editorElements: {
      toggleButton: document.getElementById("edit-toggle"),
      removeAllButton: document.getElementById("remove-ended"),
      hintElement: document.getElementById("edit-hint"),
      confirmElement: document.getElementById("confirm"),
    },
  });
}
