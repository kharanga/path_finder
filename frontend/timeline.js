import { createState, applySnapshot, applyEvent } from "./state.js";

// Creates a timeline that records every event and can rebuild the dashboard state at any instant.
export function createTimeline() {
  const entries = [];
  let replaySeq = 0;

  function push(name, data, receivedAtMs) {
    const parsed = typeof data?.ts === "string" ? Date.parse(data.ts) : NaN;
    const tsMs = Number.isNaN(parsed) ? receivedAtMs : parsed;
    entries.push({ name, data, tsMs, receivedAtMs });
    entries.sort((a, b) => a.tsMs - b.tsMs);
  }

  return {
    // Records a snapshot as individual session and message entries.
    recordSnapshot(snapshot, receivedAtMs = Date.now()) {
      for (const session of snapshot?.sessions ?? []) push("session", session, receivedAtMs);
      for (const message of snapshot?.messages ?? []) push("message", message, receivedAtMs);
    },
    // Records one incremental event.
    record(name, data, receivedAtMs = Date.now()) {
      push(name, data, receivedAtMs);
    },
    // Returns the earliest and latest timestamps in ms, or null when empty.
    range() {
      if (entries.length === 0) return null;
      return { startMs: entries[0].tsMs, endMs: entries[entries.length - 1].tsMs };
    },
    // Returns the timestamps in ms of recorded messages, for tick marks.
    messageTimes() {
      return entries.filter((entry) => entry.name === "message").map((entry) => entry.tsMs);
    },
    // Returns recorded messages with their timestamps, oldest first.
    messages() {
      return entries.filter((entry) => entry.name === "message").map((entry) => ({ tsMs: entry.tsMs, data: entry.data }));
    },
    // Rebuilds the state as of tsMs by replaying every entry at or before it.
    stateAt(tsMs) {
      const state = createState();
      replaySeq -= 1;
      applySnapshot(state, { sessions: [], messages: [] });
      state.snapshotSeq = replaySeq;
      for (const entry of entries) {
        if (entry.tsMs > tsMs) break;
        applyEvent(state, entry.name, entry.data, entry.receivedAtMs);
      }
      return state;
    },
    // Number of recorded entries.
    get size() {
      return entries.length;
    },
  };
}

// Mounts the scrubber UI onto a container and returns controls to keep it in sync with the timeline.
export function mountTimelineStrip(container, timeline, { onScrub, onLive, onTick }) {
  const liveButton = container.querySelector("[data-role=live]");
  const slider = container.querySelector("[data-role=scrubber]");
  const timeLabel = container.querySelector("[data-role=time]");
  const ticks = container.querySelector("[data-role=ticks]");
  let live = true;

  function refresh() {
    const range = timeline.range();
    container.dataset.mode = live ? "live" : "scrub";
    liveButton.disabled = live;
    if (!range || range.endMs === range.startMs) {
      slider.disabled = true;
      slider.min = 0;
      slider.max = 0;
      slider.value = 0;
    } else {
      slider.disabled = false;
      slider.min = range.startMs;
      slider.max = range.endMs;
      if (live) slider.value = range.endMs;
    }
    timeLabel.textContent = live ? "Live" : formatClock(Number(slider.value));
    renderTicks(ticks, timeline.messages(), range, onTick);
  }

  slider.addEventListener("input", () => {
    live = false;
    refresh();
    onScrub(Number(slider.value));
  });
  liveButton.addEventListener("click", () => {
    live = true;
    refresh();
    onLive();
  });
  refresh();
  return {
    // Re-reads the timeline range and ticks; call after every recorded event.
    refresh,
    // Whether the strip is following the live stream.
    get isLive() {
      return live;
    },
  };
}

// Formats a millisecond timestamp as a local HH:MM:SS clock string.
export function formatClock(tsMs) {
  const date = new Date(tsMs);
  if (Number.isNaN(date.getTime())) return "";
  return [date.getHours(), date.getMinutes(), date.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":");
}

function renderTicks(ticks, messages, range, onTick) {
  while (ticks.firstChild) ticks.removeChild(ticks.firstChild);
  if (!range || range.endMs === range.startMs) return;
  const span = range.endMs - range.startMs;
  for (const { tsMs, data } of messages) {
    const tick = document.createElement("button");
    tick.type = "button";
    tick.className = "tick";
    tick.style.left = `${(((tsMs - range.startMs) / span) * 100).toFixed(2)}%`;
    const sender = typeof data.from === "string" ? data.from : "unknown sender";
    tick.setAttribute("aria-label", `Message from ${sender} to ${data.to} at ${formatClock(tsMs)}`);
    tick.title = `${sender} → ${data.to}, ${formatClock(tsMs)}`;
    if (onTick) tick.addEventListener("click", () => onTick(data, tsMs));
    ticks.appendChild(tick);
  }
}
