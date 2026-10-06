const LIVE_STATES = new Set(["started", "busy", "idle"]);

// Creates an empty dashboard state: sessions keyed by PID plus a message history.
export function createState() {
  return { sessions: new Map(), messages: [], lastEventTs: null };
}

// Replaces the state with a server snapshot of sessions and recent messages.
export function applySnapshot(state, snapshot) {
  state.sessions = new Map();
  state.messages = [];
  for (const session of snapshot?.sessions ?? []) applySessionEvent(state, session);
  for (const message of snapshot?.messages ?? []) applyMessageEvent(state, message);
  return state;
}

// Applies one incremental SSE event by its event name and returns the state.
export function applyEvent(state, eventName, data) {
  if (eventName === "session" || eventName === "liveness") return applySessionEvent(state, data);
  if (eventName === "message") return applyMessageEvent(state, data);
  return state;
}

// Records the latest state of a session, keyed by PID, preserving earlier-known name and role.
export function applySessionEvent(state, event) {
  if (!event || typeof event.pid !== "number") return state;
  const previous = state.sessions.get(event.pid);
  state.sessions.set(event.pid, {
    pid: event.pid,
    session: event.session ?? previous?.session ?? null,
    folder: event.folder ?? previous?.folder ?? "unknown",
    role: event.role ?? previous?.role ?? null,
    state: event.state ?? previous?.state ?? "started",
    ts: event.ts ?? previous?.ts ?? null,
    firstSeen: previous?.firstSeen ?? event.ts ?? null,
  });
  bumpTs(state, event.ts);
  return state;
}

// Appends a message to history, oldest first.
export function applyMessageEvent(state, event) {
  if (!event || typeof event.from !== "string" || typeof event.to !== "string") return state;
  state.messages.push({
    ts: event.ts ?? null,
    from: event.from,
    to: event.to,
    text: event.text ?? "",
    notify_on_idle: Boolean(event.notify_on_idle),
  });
  bumpTs(state, event.ts);
  return state;
}

// Returns sessions whose state is started, busy, or idle, sorted by folder then name.
export function liveSessions(state) {
  return [...state.sessions.values()]
    .filter((session) => LIVE_STATES.has(session.state))
    .sort(compareByFolderThenName);
}

// Finds a session by its display name, or undefined when no session has that name.
export function sessionByName(state, name) {
  for (const session of state.sessions.values()) {
    if (session.session === name) return session;
  }
  return undefined;
}

// Returns the display label for a session: its name, or its PID while the name is unknown.
export function sessionLabel(session) {
  return session.session ?? `pid ${session.pid}`;
}

function compareByFolderThenName(a, b) {
  const folderOrder = a.folder.localeCompare(b.folder);
  if (folderOrder !== 0) return folderOrder;
  return sessionLabel(a).localeCompare(sessionLabel(b));
}

function bumpTs(state, ts) {
  if (typeof ts !== "string") return;
  if (state.lastEventTs === null || ts > state.lastEventTs) state.lastEventTs = ts;
}
