const TOP_OF_RING = -Math.PI / 2;

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
  if (Math.abs(cos) < 0.2) return "center";
  return cos > 0 ? "right" : "left";
}

function compareByFolderThenLabel(a, b) {
  const folderOrder = a.folder.localeCompare(b.folder);
  if (folderOrder !== 0) return folderOrder;
  return String(a.session ?? a.pid).localeCompare(String(b.session ?? b.pid));
}
