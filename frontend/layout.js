const TOP_OF_RING = -Math.PI / 2;
const CENTER_BAND = 0.2;

// Places sessions evenly on a ring, grouped by folder, and returns positions keyed by PID.
export function ringPositions(sessions, { cx, cy, radius }) {
  const ordered = [...sessions].sort(compareByFolderThenLabel);
  const positions = new Map();
  const count = ordered.length;
  ordered.forEach((session, index) => {
    const angle = TOP_OF_RING + (index / Math.max(count, 1)) * Math.PI * 2;
    positions.set(session.pid, {
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      angle,
    });
  });
  return positions;
}

// Returns the side a label should sit on so it points away from the ring center.
export function labelSide(angle) {
  const cos = Math.cos(angle);
  if (Math.abs(cos) < CENTER_BAND) return Math.sin(angle) < 0 ? "top" : "bottom";
  return cos > 0 ? "right" : "left";
}

// Computes where the name and role text go relative to a body so neighbors never overlap.
export function labelPlacement(angle, { bodyRadius, lineHeight, hasRole }) {
  const side = labelSide(angle);
  const gap = bodyRadius + 14;
  const anchor = side === "right" ? "start" : side === "left" ? "end" : "middle";
  if (side === "top") {
    const bottomLine = -gap - 4;
    return { anchor, x: 0, nameY: hasRole ? bottomLine - lineHeight : bottomLine, roleY: bottomLine };
  }
  if (side === "bottom") {
    const firstLine = gap + lineHeight;
    return { anchor, x: 0, nameY: firstLine, roleY: firstLine + lineHeight };
  }
  const x = side === "right" ? gap : -gap;
  if (!hasRole) return { anchor, x, nameY: lineHeight * 0.35, roleY: lineHeight * 0.35 };
  return { anchor, x, nameY: -lineHeight * 0.15, roleY: lineHeight * 0.85 };
}

// Builds the curved SVG path a message travels from one point to another, bowing toward the ring center.
export function messageCurve(from, to, center, { bow = 0.55, sideOffset = 40 } = {}) {
  const midX = (from.x + to.x) / 2;
  const midY = (from.y + to.y) / 2;
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const distance = Math.hypot(dx, dy) || 1;
  const perpX = -dy / distance;
  const perpY = dx / distance;
  const control = {
    x: midX + (center.x - midX) * bow + perpX * sideOffset,
    y: midY + (center.y - midY) * bow + perpY * sideOffset,
  };
  return {
    d: `M ${round(from.x)} ${round(from.y)} Q ${round(control.x)} ${round(control.y)} ${round(to.x)} ${round(to.y)}`,
    control,
    length: quadraticLength(from, control, to),
  };
}

// Shortens a label to at most maxChars characters, ending with an ellipsis when cut.
export function truncateLabel(label, maxChars) {
  if (label.length <= maxChars) return label;
  return `${label.slice(0, Math.max(maxChars - 1, 1))}…`;
}

function quadraticLength(p0, p1, p2, steps = 24) {
  let length = 0;
  let previous = p0;
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    const x = (1 - t) * (1 - t) * p0.x + 2 * (1 - t) * t * p1.x + t * t * p2.x;
    const y = (1 - t) * (1 - t) * p0.y + 2 * (1 - t) * t * p1.y + t * t * p2.y;
    length += Math.hypot(x - previous.x, y - previous.y);
    previous = { x, y };
  }
  return length;
}

function round(value) {
  return Math.round(value * 10) / 10;
}

function compareByFolderThenLabel(a, b) {
  const folderOrder = a.folder.localeCompare(b.folder);
  if (folderOrder !== 0) return folderOrder;
  return String(a.session ?? a.pid).localeCompare(String(b.session ?? b.pid));
}
