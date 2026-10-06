const EVENT_NAMES = ["session", "message", "liveness"];

// Opens the SSE stream at /events and falls back to a local fixture when the endpoint is absent.
export function connect({ onSnapshot, onEvent, onStatus, fixtureUrl = "./fixtures/empty.json" }) {
  const forcedFixture = new URLSearchParams(location.search).get("fixture");
  if (forcedFixture) return loadFixture(`./fixtures/${forcedFixture}.json`, { onSnapshot, onEvent, onStatus });

  const source = new EventSource("/events");
  let opened = false;
  source.addEventListener("open", () => {
    opened = true;
    onStatus?.("live");
  });
  source.addEventListener("snapshot", (event) => onSnapshot(parseJson(event.data)));
  for (const name of EVENT_NAMES) {
    source.addEventListener(name, (event) => onEvent(name, parseJson(event.data)));
  }
  source.addEventListener("error", () => {
    if (opened) {
      onStatus?.("reconnecting");
      return;
    }
    source.close();
    loadFixture(fixtureUrl, { onSnapshot, onEvent, onStatus });
  });
  return () => source.close();
}

// Loads a fixture file and replays its snapshot and timed events through the same callbacks.
export async function loadFixture(url, { onSnapshot, onEvent, onStatus }) {
  const timers = [];
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`fixture ${url} returned ${response.status}`);
    const fixture = await response.json();
    onStatus?.("fixture");
    onSnapshot(fixture.snapshot ?? { sessions: [], messages: [] });
    let elapsed = 0;
    for (const step of fixture.events ?? []) {
      elapsed += step.delayMs ?? 0;
      timers.push(setTimeout(() => onEvent(step.event, step.data), elapsed));
    }
  } catch (error) {
    onStatus?.("offline");
    onSnapshot({ sessions: [], messages: [] });
  }
  return () => timers.forEach(clearTimeout);
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
