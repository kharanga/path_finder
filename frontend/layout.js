export const BOARD = { width: 1360, height: 1000, marginX: 60, marginTop: 70, marginBottom: 70, labelWidth: 170, labelAbove: 0 };
export const BOARD_PORTRAIT = { width: 760, height: 1100, marginX: 60, marginTop: 60, marginBottom: 60, labelWidth: 0, labelAbove: 30 };
export const CAPSULE = { width: 220, height: 56, gapX: 36, rowGap: 64, cornerRadius: 14 };
const DEFAULT_PITCH = CAPSULE.height + CAPSULE.rowGap;
export const LANE = { gap: 6, pinGap: 20 };

// Returns the board constants for the landscape or the portrait (phone) orientation.
export function boardFor(portrait) {
  return portrait ? BOARD_PORTRAIT : BOARD;
}

// Groups sessions into one row per folder and returns capsule boxes keyed by PID plus the row list.
export function boardLayout(sessions, { portrait = false, width, height } = {}) {
  const board = boardFor(portrait);
  const boardWidth = width ?? board.width;
  const boardHeight = height ?? board.height;
  const rows = groupIntoRows(sessions);
  const perLine = Math.max(1, Math.floor((boardWidth - board.marginX * 2 - board.labelWidth + CAPSULE.gapX) / (CAPSULE.width + CAPSULE.gapX)));
  const lines = [];
  for (const row of rows) {
    for (let start = 0; start < row.sessions.length; start += perLine) {
      lines.push({ row, sessions: row.sessions.slice(start, start + perLine), firstOfRow: start === 0 });
    }
  }
  const lineHeight = CAPSULE.height + board.labelAbove;
  const usable = boardHeight - board.marginTop - board.marginBottom - lineHeight;
  const pitch = lines.length > 1 ? Math.min(lineHeight + CAPSULE.rowGap, usable / (lines.length - 1)) : 0;
  const stackHeight = (lines.length - 1) * pitch + lineHeight;
  const startY = board.marginTop + (usable + lineHeight - stackHeight) / 2 + board.labelAbove;
  const startX = board.marginX + board.labelWidth;
  const capsules = new Map();
  const rowBoxes = [];
  lines.forEach((line, lineIndex) => {
    const y = startY + lineIndex * pitch;
    if (line.firstOfRow) {
      rowBoxes.push(board.labelAbove > 0
        ? { folder: line.row.folder, label: line.row.folder, x: startX, y, cy: y + CAPSULE.height / 2, labelX: startX, labelY: y - 10, anchor: "start" }
        : { folder: line.row.folder, label: line.row.folder, x: board.marginX, y, cy: y + CAPSULE.height / 2, labelX: board.marginX, labelY: y + CAPSULE.height / 2, anchor: "start" });
    }
    line.sessions.forEach((session, index) => {
      const x = startX + index * (CAPSULE.width + CAPSULE.gapX);
      capsules.set(session.pid, { pid: session.pid, folder: line.row.folder, x, y, width: CAPSULE.width, height: CAPSULE.height, cx: x + CAPSULE.width / 2, cy: y + CAPSULE.height / 2, line: lineIndex, index, pitch: pitch || DEFAULT_PITCH, columnOrigin: startX });
    });
  });
  return { capsules, rows: rowBoxes, lineCount: lines.length, perLine, board: { width: boardWidth, height: boardHeight, portrait } };
}

// Routes an orthogonal trace between two boxes along its lanes and pins; returns the path, corner points, and length.
export function tracePath(from, to, { cornerRadius = 12, laneShift = 0, shifts = {}, fromPinShift = 0, toPinShift = 0 } = {}) {
  const points = routePoints(from, to, (corridorId) => shifts[corridorId] ?? laneShift, fromPinShift, toPinShift);
  return { d: roundedPath(points, cornerRadius), points, length: pathLength(points, cornerRadius) };
}

// Lists the corridors a trace between two boxes runs through: gaps below a line ("gap:<line>") and column gaps ("col:<gap>").
export function traceCorridors(from, to) {
  if (from.line === to.line) return [`gap:${from.line}`];
  const upper = Math.min(from.line, to.line);
  if (Math.abs(from.line - to.line) === 1) return [`gap:${upper}`];
  const lower = Math.max(from.line, to.line);
  return [`gap:${from.line < to.line ? from.line : from.line - 1}`, `col:${Math.max(from.index, to.index) + 1}`, `gap:${from.line < to.line ? to.line - 1 : to.line}`];
}

// Assigns every capsule pair a lane per corridor it uses and a pin per endpoint column, in order of first appearance so earlier pairs never move.
export function assignLanes(pairKeys, { columnOf = (pid) => pid, corridorsOf = () => [] } = {}) {
  const lanes = new Map();
  const pins = new Map();
  const corridorLanes = new Map();
  const columns = new Map();
  const perColumn = new Map();
  const perCorridor = new Map();
  for (const key of pairKeys) {
    if (lanes.has(key)) continue;
    lanes.set(key, lanes.size);
    const pinEntry = {};
    for (const endpoint of key.split("|")) {
      const column = String(columnOf(endpoint));
      const count = perColumn.get(column) ?? 0;
      perColumn.set(column, count + 1);
      pinEntry[endpoint] = count;
      columns.set(endpoint, column);
    }
    pins.set(key, pinEntry);
    const laneEntry = {};
    for (const corridor of new Set(corridorsOf(key))) {
      const count = perCorridor.get(corridor) ?? 0;
      perCorridor.set(corridor, count + 1);
      laneEntry[corridor] = count;
    }
    corridorLanes.set(key, laneEntry);
  }
  return { lanes, pins, corridorLanes, columns, perColumn, perCorridor };
}

// Converts a lane or pin index into a signed offset: 0, +gap, -gap, +2·gap, -2·gap, …
export function laneOffset(index, gap = LANE.gap) {
  if (index <= 0) return 0;
  const magnitude = Math.ceil(index / 2) * gap;
  return index % 2 === 1 ? magnitude : -magnitude;
}

// The gap between lanes that lets `count` lanes fit inside a corridor of the given half-width: the standard gap, or a smaller one when crowded.
export function fittedGap(halfWidth, count, gap = LANE.gap) {
  const sides = Math.ceil(Math.max(count - 1, 0) / 2);
  if (sides === 0) return gap;
  return Math.max(Math.min(gap, (halfWidth - 2) / sides), 1);
}

// Returns the tracePath options for one pair: per-corridor lane shifts and the two pin shifts, with gaps shrunk only where a corridor or column is crowded.
export function laneOptions(assignment, key, from, to) {
  const pins = assignment.pins.get(key) ?? {};
  const laneEntry = assignment.corridorLanes?.get(key) ?? {};
  const halfGap = Math.max(((from.pitch ?? CAPSULE.height + CAPSULE.rowGap) - from.height) / 2, 4);
  const shifts = {};
  for (const [corridor, index] of Object.entries(laneEntry)) {
    const count = assignment.perCorridor?.get(corridor) ?? 1;
    const halfWidth = corridor.startsWith("col:") ? CAPSULE.gapX / 2 : halfGap;
    shifts[corridor] = laneOffset(index, fittedGap(halfWidth, count));
  }
  const pinShift = (box) => {
    const column = assignment.columns?.get(String(box.pid));
    const count = column === undefined ? 1 : assignment.perColumn?.get(column) ?? 1;
    return laneOffset(pins[String(box.pid)] ?? 0, fittedGap(box.width / 2 - 10, count, LANE.pinGap));
  };
  return { shifts, fromPinShift: pinShift(from), toPinShift: pinShift(to) };
}

// Returns the order-independent key that identifies the trace between two PIDs.
export function traceKey(pidA, pidB) {
  return [String(pidA), String(pidB)].sort().join("|");
}

// Returns a zero-width box at the left edge of a capsule's line, used as the origin for an unknown sender.
export function edgeBox(nearBox) {
  const x = (nearBox.columnOrigin ?? BOARD.marginX + BOARD.labelWidth) - CAPSULE.gapX;
  return { pid: null, folder: nearBox.folder, x, y: nearBox.y, width: 0, height: nearBox.height, cx: x, cy: nearBox.cy, line: nearBox.line, index: -1, pitch: nearBox.pitch, columnOrigin: nearBox.columnOrigin };
}

// Shortens a label to at most maxChars characters, ending with an ellipsis when cut.
export function truncateLabel(label, maxChars) {
  if (label.length <= maxChars) return label;
  return `${label.slice(0, Math.max(maxChars - 1, 1))}…`;
}

function groupIntoRows(sessions) {
  const byFolder = new Map();
  for (const session of sessions) {
    const key = folderSortKey(session.folder);
    if (!byFolder.has(key)) byFolder.set(key, { key, folder: session.folder, sessions: [] });
    byFolder.get(key).sessions.push(session);
  }
  const rows = [...byFolder.values()].sort((a, b) => a.key.localeCompare(b.key));
  for (const row of rows) row.sessions.sort(compareByFirstSeenThenLabel);
  return rows;
}

function compareByFirstSeenThenLabel(a, b) {
  const aSeen = a.firstSeen ?? "~";
  const bSeen = b.firstSeen ?? "~";
  if (aSeen !== bSeen) return aSeen < bSeen ? -1 : 1;
  return String(a.session ?? a.pid).localeCompare(String(b.session ?? b.pid));
}

function folderSortKey(folder) {
  return String(folder).replace(/_/g, "-");
}

function routePoints(from, to, shiftFor, fromPinShift, toPinShift) {
  const lineGap = Math.max((from.pitch ?? DEFAULT_PITCH) - from.height, 8);
  const halfGap = lineGap / 2;
  const fromX = from.cx + fromPinShift;
  const toX = to.cx + toPinShift;
  const corridors = traceCorridors(from, to);
  if (from.line === to.line) {
    if (Math.abs(fromX - toX) < 1) return [{ x: fromX, y: from.cy }, { x: toX, y: to.cy }];
    const channelY = from.y + from.height + halfGap + shiftFor(corridors[0]);
    return [{ x: fromX, y: from.y + from.height }, { x: fromX, y: channelY }, { x: toX, y: channelY }, { x: toX, y: to.y + to.height }];
  }
  const downward = to.cy > from.cy;
  const startY = downward ? from.y + from.height : from.y;
  const endY = downward ? to.y : to.y + to.height;
  if (Math.abs(from.line - to.line) === 1) {
    if (Math.abs(fromX - toX) < 1) return [{ x: fromX, y: startY }, { x: toX, y: endY }];
    const channelY = (startY + endY) / 2 + shiftFor(corridors[0]);
    return [{ x: fromX, y: startY }, { x: fromX, y: channelY }, { x: toX, y: channelY }, { x: toX, y: endY }];
  }
  const nearChannelY = (downward ? startY + halfGap : startY - halfGap) + shiftFor(corridors[0]);
  const farChannelY = (downward ? endY - halfGap : endY + halfGap) + shiftFor(corridors[2]);
  const busX = columnGapX(from.columnOrigin ?? BOARD.marginX + BOARD.labelWidth, Math.max(from.index, to.index) + 1) + shiftFor(corridors[1]);
  return [
    { x: fromX, y: startY },
    { x: fromX, y: nearChannelY },
    { x: busX, y: nearChannelY },
    { x: busX, y: farChannelY },
    { x: toX, y: farChannelY },
    { x: toX, y: endY },
  ];
}

function columnGapX(columnOrigin, gapIndex) {
  return columnOrigin + gapIndex * (CAPSULE.width + CAPSULE.gapX) - CAPSULE.gapX / 2;
}

function roundedPath(points, radius) {
  const r = (v) => Math.round(v * 10) / 10;
  if (points.length < 3) return `M ${r(points[0].x)} ${r(points[0].y)} L ${r(points[1].x)} ${r(points[1].y)}`;
  let d = `M ${r(points[0].x)} ${r(points[0].y)}`;
  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1];
    const corner = points[i];
    const next = points[i + 1];
    const inLen = Math.hypot(corner.x - prev.x, corner.y - prev.y);
    const outLen = Math.hypot(next.x - corner.x, next.y - corner.y);
    const rad = Math.min(radius, inLen / 2, outLen / 2);
    const inX = corner.x - Math.sign(corner.x - prev.x) * rad;
    const inY = corner.y - Math.sign(corner.y - prev.y) * rad;
    const outX = corner.x + Math.sign(next.x - corner.x) * rad;
    const outY = corner.y + Math.sign(next.y - corner.y) * rad;
    d += ` L ${r(inX)} ${r(inY)} Q ${r(corner.x)} ${r(corner.y)} ${r(outX)} ${r(outY)}`;
  }
  const last = points[points.length - 1];
  d += ` L ${r(last.x)} ${r(last.y)}`;
  return d;
}

function pathLength(points, radius) {
  let length = 0;
  for (let i = 1; i < points.length; i++) length += Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y);
  const corners = Math.max(points.length - 2, 0);
  return length - corners * (2 * radius - (Math.PI / 2) * radius);
}
