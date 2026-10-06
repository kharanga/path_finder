import { NOT_LIVE_STATES } from "./schema.js";

/** How many recent message events the state keeps for the snapshot. */
export const DEFAULT_MESSAGE_LIMIT = 500;

/** Creates an empty in-memory dashboard state. */
export function createState(messageLimit = DEFAULT_MESSAGE_LIMIT) {
  return { sessions: new Map(), messages: [], messageLimit };
}

function mergeSession(previous, event) {
  return {
    ts: event.ts,
    type: "session",
    session: event.session ?? previous?.session ?? null,
    folder: event.folder || previous?.folder || "",
    pid: event.pid,
    state: event.state,
    role: event.role ?? previous?.role ?? null,
  };
}

/** Applies one valid event to the state and returns the object the server should broadcast. */
export function applyEvent(state, event) {
  if (event.type === "session") {
    const merged = mergeSession(state.sessions.get(event.pid), event);
    state.sessions.set(event.pid, merged);
    return merged;
  }
  state.messages.push(event);
  if (state.messages.length > state.messageLimit) {
    state.messages.splice(0, state.messages.length - state.messageLimit);
  }
  return event;
}

/** Returns true when a session is on the board: any state except ended or removed. */
export function isLive(session) {
  return !NOT_LIVE_STATES.includes(session.state);
}

/** Returns every session that is neither ended nor removed, sorted by ts. */
export function liveSessions(state) {
  return [...state.sessions.values()].filter(isLive).sort((a, b) => a.ts.localeCompare(b.ts));
}

/** Returns the latest session object for a display name, preferring a live one; removed sessions are never returned. */
export function findSessionByName(state, name) {
  for (const session of state.sessions.values()) {
    if (session.session === name && isLive(session)) return session;
  }
  for (const session of state.sessions.values()) {
    if (session.session === name && session.state !== "removed") return session;
  }
  return undefined;
}

/** Builds the SSE snapshot payload: every known session except removed ones, plus recent messages, oldest first. */
export function snapshot(state) {
  return {
    sessions: [...state.sessions.values()].filter((session) => session.state !== "removed").sort((a, b) => a.ts.localeCompare(b.ts)),
    messages: [...state.messages],
  };
}
