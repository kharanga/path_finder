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

// Shortens a label to at most maxChars characters, ending with an ellipsis when cut.
export function truncateLabel(label, maxChars) {
  if (label.length <= maxChars) return label;
  return `${label.slice(0, Math.max(maxChars - 1, 1))}…`;
}

function compareByFolderThenLabel(a, b) {
  const folderOrder = a.folder.localeCompare(b.folder);
  if (folderOrder !== 0) return folderOrder;
  return String(a.session ?? a.pid).localeCompare(String(b.session ?? b.pid));
}
