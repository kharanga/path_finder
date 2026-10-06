const UNKNOWN_SENDER = "unknown sender";

// Turns a message into the display fields the side panel shows.
export function describeMessage(message) {
  return {
    from: typeof message.from === "string" ? message.from : UNKNOWN_SENDER,
    fromKnown: typeof message.from === "string",
    to: message.to,
    time: formatTimestamp(message.ts),
    iso: typeof message.ts === "string" ? message.ts : "",
    text: message.text ?? "",
    notify: Boolean(message.notify_on_idle),
  };
}

// Formats an ISO timestamp as a local date and time, or "unknown time" when missing or invalid.
export function formatTimestamp(ts) {
  const date = new Date(ts ?? NaN);
  if (Number.isNaN(date.getTime())) return "unknown time";
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

// Binds the side panel markup and returns show, hide, and the current selection.
export function createPanel(element, { onClose } = {}) {
  const fields = {
    from: element.querySelector("[data-field=from]"),
    to: element.querySelector("[data-field=to]"),
    time: element.querySelector("[data-field=time]"),
    text: element.querySelector("[data-field=text]"),
    notify: element.querySelector("[data-field=notify]"),
  };
  const closeButton = element.querySelector("[data-role=close]");
  let selectedIndex = null;

  function hide() {
    element.hidden = true;
    selectedIndex = null;
    onClose?.();
  }

  closeButton.addEventListener("click", hide);

  return {
    // Fills the panel with one message and opens it.
    show(message, index) {
      const view = describeMessage(message);
      fields.from.textContent = view.from;
      fields.from.classList.toggle("unknown", !view.fromKnown);
      fields.to.textContent = view.to;
      fields.time.textContent = view.time;
      fields.time.setAttribute("title", view.iso);
      fields.text.textContent = view.text;
      fields.notify.hidden = !view.notify;
      element.hidden = false;
      selectedIndex = index ?? null;
      closeButton.focus?.();
    },
    hide,
    // Index of the message being shown, or null when closed.
    get selectedIndex() {
      return selectedIndex;
    },
  };
}
