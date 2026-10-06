const LIVE_STATES = new Set(["started", "busy", "waiting", "idle"]);
const MAX_FINISHED_THREADS = 50;
const PLACEHOLDER_MAX_AGE_MS = 60000;
const NAME_ID_SUFFIX = /-[0-9a-f]{2}$/i;

// Creates an empty dashboard state: sessions keyed by PID, placeholders keyed by name, messages, and threads.
export function createState() {
  return { sessions: new Map(), placeholders: new Map(), messages: [], threads: [], lastEventTs: null, snapshotSeq: 0 };
}

// Replaces the state with a server snapshot of sessions and recent messages.
export function applySnapshot(state, snapshot, receivedAtMs = Date.now()) {
  state.sessions = new Map();
  state.placeholders = new Map();
  state.messages = [];
  state.threads = [];
  state.snapshotSeq += 1;
  for (const session of snapshot?.sessions ?? []) applySessionEvent(state, session);
  for (const message of snapshot?.messages ?? []) applyMessageEvent(state, message, receivedAtMs);
  return state;
}

// Applies one incremental SSE event by its event name and returns the state.
export function applyEvent(state, eventName, data, receivedAtMs = Date.now()) {
  if (eventName === "session" || eventName === "liveness") return applySessionEvent(state, data);
  if (eventName === "message") return applyMessageEvent(state, data, receivedAtMs);
  return state;
}

// Records the latest state of a session, keyed by PID, preserving earlier-known name and role.
export function applySessionEvent(state, event) {
  if (!event || typeof event.pid !== "number") return state;
  const previous = state.sessions.get(event.pid);
  const name = event.session ?? previous?.session ?? null;
  if (name !== null) {
    resolveThreadsFor(state, name, event.state, event.ts);
    state.placeholders.delete(name);
  }
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

// Appends a message to history, oldest first, adding placeholder bodies for names not yet on the ring.
export function applyMessageEvent(state, event, receivedAtMs = Date.now()) {
  if (!event || typeof event.to !== "string") return state;
  if (event.from !== null && event.from !== undefined && typeof event.from !== "string") return state;
  for (const name of [event.from, event.to]) {
    if (typeof name === "string" && !sessionByName(state, name)) {
      state.placeholders.set(name, { name, folder: folderFromName(name), createdAtMs: receivedAtMs });
    }
  }
  const message = {
    ts: event.ts ?? null,
    from: event.from ?? null,
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

// Removes placeholder bodies older than maxAgeMs and returns how many were removed.
export function prunePlaceholders(state, nowMs = Date.now(), maxAgeMs = PLACEHOLDER_MAX_AGE_MS) {
  let removed = 0;
  for (const [name, placeholder] of state.placeholders) {
    if (nowMs - placeholder.createdAtMs >= maxAgeMs) {
      state.placeholders.delete(name);
      removed += 1;
    }
  }
  return removed;
}

// Derives the folder a display name most likely came from by stripping its trailing -<id>.
export function folderFromName(name) {
  return name.replace(NAME_ID_SUFFIX, "");
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

// Returns live sessions plus placeholder bodies, sorted by folder then name.
export function liveSessions(state) {
  const live = [...state.sessions.values()].filter((session) => LIVE_STATES.has(session.state));
  const placeholders = [...state.placeholders.values()].map(placeholderAsSession);
  return live.concat(placeholders).sort(compareByFolderThenName);
}

// Finds a session or placeholder by its display name, or undefined when neither has that name.
export function sessionByName(state, name) {
  if (typeof name !== "string") return undefined;
  for (const session of state.sessions.values()) {
    if (session.session === name) return session;
  }
  const placeholder = state.placeholders.get(name);
  return placeholder ? placeholderAsSession(placeholder) : undefined;
}

function placeholderAsSession(placeholder) {
  return { pid: `placeholder:${placeholder.name}`, session: placeholder.name, folder: placeholder.folder, role: null, state: "placeholder", ts: null, firstSeen: null };
}

// Returns the display label for a session: its name, or its PID while the name is unknown.
export function sessionLabel(session) {
  return session.session ?? `pid ${session.pid}`;
}

function compareByFolderThenName(a, b) {
  const folderOrder = folderSortKey(a.folder).localeCompare(folderSortKey(b.folder));
  if (folderOrder !== 0) return folderOrder;
  return sessionLabel(a).localeCompare(sessionLabel(b));
}

function folderSortKey(folder) {
  return folder.replace(/_/g, "-");
}

function bumpTs(state, ts) {
  if (typeof ts !== "string") return;
  if (state.lastEventTs === null || ts > state.lastEventTs) state.lastEventTs = ts;
}
