/** The only legal values of a session event's state field. */
export const SESSION_STATES = ["started", "busy", "waiting", "idle", "ended"];

const SESSION_FIELDS = ["ts", "type", "session", "folder", "pid", "state", "role"];
const MESSAGE_FIELDS = ["ts", "type", "from", "to", "text", "notify_on_idle"];

function isIsoTimestamp(value) {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

function isStringOrNull(value) {
  return value === null || typeof value === "string";
}

function unknownFields(event, allowed) {
  return Object.keys(event).filter((key) => !allowed.includes(key));
}

/** Checks one dashboard event against the §3 schema and returns {ok, errors}. */
export function validateEvent(event) {
  const errors = [];
  if (event === null || typeof event !== "object" || Array.isArray(event)) {
    return { ok: false, errors: ["event must be an object"] };
  }
  if (!isIsoTimestamp(event.ts)) errors.push("ts must be an ISO 8601 string");
  if (event.type === "session") {
    if (!isStringOrNull(event.session)) errors.push("session must be a string or null");
    if (typeof event.folder !== "string") errors.push("folder must be a string");
    if (!Number.isInteger(event.pid) || event.pid <= 0) errors.push("pid must be a positive integer");
    if (!SESSION_STATES.includes(event.state)) errors.push(`state must be one of ${SESSION_STATES.join(", ")}`);
    if (!isStringOrNull(event.role)) errors.push("role must be a string or null");
    for (const key of unknownFields(event, SESSION_FIELDS)) errors.push(`unknown field ${key}`);
  } else if (event.type === "message") {
    if (!isStringOrNull(event.from)) errors.push("from must be a string or null");
    if (typeof event.to !== "string") errors.push("to must be a string");
    if (typeof event.text !== "string") errors.push("text must be a string");
    if (typeof event.notify_on_idle !== "boolean") errors.push("notify_on_idle must be a boolean");
    for (const key of unknownFields(event, MESSAGE_FIELDS)) errors.push(`unknown field ${key}`);
  } else {
    errors.push("type must be session or message");
  }
  return { ok: errors.length === 0, errors };
}

/** Parses one events.jsonl line and returns the event, or null when the line is malformed or invalid. */
export function parseEventLine(line) {
  const trimmed = line.trim();
  if (trimmed === "") return null;
  let event;
  try {
    event = JSON.parse(trimmed);
  } catch {
    return null;
  }
  return validateEvent(event).ok ? event : null;
}
