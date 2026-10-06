import { request } from "node:http";

/** Opens an SSE connection to url and returns {frames, waitFor, close}; frames are {event, data} objects parsed as they arrive. */
export function connectSse(url) {
  const frames = [];
  const waiters = [];
  let buffer = "";
  let response = null;
  const notify = () => {
    for (const waiter of [...waiters]) {
      if (waiter.predicate(frames)) {
        waiters.splice(waiters.indexOf(waiter), 1);
        clearTimeout(waiter.timer);
        waiter.resolve(frames);
      }
    }
  };
  const consume = (chunk) => {
    buffer += chunk;
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const lines = block.split("\n");
      const eventLine = lines.find((line) => line.startsWith("event: "));
      const dataLine = lines.find((line) => line.startsWith("data: "));
      if (eventLine && dataLine) frames.push({ event: eventLine.slice(7), data: JSON.parse(dataLine.slice(6)) });
      else if (block.startsWith(":")) frames.push({ event: "comment", data: block.slice(1).trim() });
      boundary = buffer.indexOf("\n\n");
    }
    notify();
  };
  const opened = new Promise((resolve, reject) => {
    const req = request(url, (res) => {
      response = res;
      res.setEncoding("utf8");
      res.on("data", consume);
      resolve(res);
    });
    req.on("error", reject);
    req.end();
  });
  return {
    frames,
    opened,
    waitFor(predicate, timeoutMs = 2000) {
      if (predicate(frames)) return Promise.resolve(frames);
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          waiters.splice(waiters.findIndex((w) => w.resolve === resolve), 1);
          reject(new Error(`timed out waiting for SSE frames; have ${JSON.stringify(frames.map((f) => f.event))}`));
        }, timeoutMs);
        waiters.push({ predicate, resolve, reject, timer });
      });
    },
    close() {
      response?.destroy();
    },
  };
}
