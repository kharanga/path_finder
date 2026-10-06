/** Returns true when two axis-aligned boxes {x, y, width, height} overlap. */
export function boxesOverlap(a, b) {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

/** Returns true when an orthogonal segment from p to q passes through the interior of a box (touching the edge does not count). */
export function segmentCrossesBox(p, q, box, inset = 0.5) {
  const x0 = box.x + inset;
  const x1 = box.x + box.width - inset;
  const y0 = box.y + inset;
  const y1 = box.y + box.height - inset;
  if (p.x === q.x) {
    if (p.x <= x0 || p.x >= x1) return false;
    return Math.min(p.y, q.y) < y1 && Math.max(p.y, q.y) > y0;
  }
  if (p.y <= y0 || p.y >= y1) return false;
  return Math.min(p.x, q.x) < x1 && Math.max(p.x, q.x) > x0;
}

/** Returns the overlapping stretch of two collinear orthogonal segments with length above tolerance, or null. */
export function sharedStretch(a0, a1, b0, b1, tolerance = 0.01) {
  const aVertical = Math.abs(a0.x - a1.x) <= tolerance;
  const bVertical = Math.abs(b0.x - b1.x) <= tolerance;
  if (aVertical !== bVertical) return null;
  const axis = aVertical ? "x" : "y";
  const along = aVertical ? "y" : "x";
  if (Math.abs(a0[axis] - b0[axis]) > tolerance) return null;
  const start = Math.max(Math.min(a0[along], a1[along]), Math.min(b0[along], b1[along]));
  const end = Math.min(Math.max(a0[along], a1[along]), Math.max(b0[along], b1[along]));
  if (end - start <= tolerance) return null;
  return { axis, at: a0[axis], from: start, to: end };
}

/** Lists every shared stretch between two orthogonal routes given as point arrays. */
export function sharedSegments(routeA, routeB, tolerance = 0.01) {
  const found = [];
  for (let i = 1; i < routeA.length; i += 1) {
    for (let j = 1; j < routeB.length; j += 1) {
      const stretch = sharedStretch(routeA[i - 1], routeA[i], routeB[j - 1], routeB[j], tolerance);
      if (stretch) found.push({ a: i - 1, b: j - 1, ...stretch });
    }
  }
  return found;
}

/** Returns every pair of route keys that share a segment, for a map of key to point array. */
export function routesSharingSegments(routes, tolerance = 0.01) {
  const keys = [...routes.keys()];
  const pairs = [];
  for (let i = 0; i < keys.length; i += 1) {
    for (let j = i + 1; j < keys.length; j += 1) {
      const shared = sharedSegments(routes.get(keys[i]), routes.get(keys[j]), tolerance);
      if (shared.length > 0) pairs.push({ a: keys[i], b: keys[j], shared });
    }
  }
  return pairs;
}
