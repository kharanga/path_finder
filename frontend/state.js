const LIVE_STATES = new Set(["started", "busy", "waiting", "idle"]);
const MAX_FINISHED_THREADS = 50;

// Creates an empty dashboard state: sessions keyed by PID, message history, and notify threads.
export function createState() {
  return { sessions: new Map(), messages: [], threads: [], lastEventTs: null, snapshotSeq: 0 };
}

// Replaces the state with a server snapshot of sessions and recent messages.
export function applySnapshot(state, snapshot) {
  state.sessions = new Map();
  state.messages = [];
  state.threads = [];
  state.snapshotSeq += 1;
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
  const name = event.session ?? previous?.session ?? null;
  if (name !== null) resolveThreadsFor(state, name, event.state, event.ts);
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
  const message = {
    ts: event.ts ?? null,
    from: event.from,
    to: event.to,
    text: event.text ?? "",
    notify_on_idle: Boolean(event.notify_on_idle),
  };
  state.messages.push(message);
  if (message.notify_on_idle) {
    state.threads.push({ id: state.messages.length - 1, from: message.from, to: message.to, ts: message.ts, status: "waiting", resolvedTs: null });
  }
  bumpTs(state, event.ts);
  return state;
}

// Returns threads still waiting for the recipient to go idle.
export function waitingThreads(state) {
  return state.threads.filter((thread) => thread.status === "waiting");
}

function resolveThreadsFor(state, recipientName, newState, ts) {
  if (newState !== "idle" && newState !== "ended") return;
  for (const thread of state.threads) {
    if (thread.status !== "waiting" || thread.to !== recipientName) continue;
    thread.status = newState === "idle" ? "snapped" : "dropped";
    thread.resolvedTs = ts ?? null;
  }
  pruneFinishedThreads(state);
}

function pruneFinishedThreads(state) {
  const finished = state.threads.filter((thread) => thread.status !== "waiting");
  if (finished.length <= MAX_FINISHED_THREADS) return;
  const dropCount = finished.length - MAX_FINISHED_THREADS;
  let dropped = 0;
  state.threads = state.threads.filter((thread) => {
    if (thread.status === "waiting" || dropped >= dropCount) return true;
    dropped += 1;
    return false;
  });
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
