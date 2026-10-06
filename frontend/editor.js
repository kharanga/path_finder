const FIXTURE_HINT = "Removal needs the server. Fixture mode has none.";

// Builds the removal URL for a PID.
export function removeUrl(pid) {
  return `/sessions/${encodeURIComponent(String(pid))}/remove`;
}

// Lists the sessions currently in state ended, the targets of "Remove all ended".
export function endedSessions(state) {
  return [...state.sessions.values()].filter((session) => session.state === "ended");
}

// Describes what a removal would do, for the confirmation line.
export function describeRemoval(targets) {
  if (targets.length === 0) return "Nothing to remove.";
  if (targets.length === 1) return `Remove ${targets[0].session ?? `pid ${targets[0].pid}`} from the board?`;
  return `Remove ${targets.length} ended sessions from the board?`;
}

// Wires the Edit toggle, the Remove-all-ended button, and the confirmation bar; returns the editor controls.
export function createEditor({ toggleButton, removeAllButton, hintElement, confirmElement, getState, draw, request = (url, init) => fetch(url, init) }) {
  const confirmText = confirmElement.querySelector("[data-role=confirm-text]");
  const confirmButton = confirmElement.querySelector("[data-role=confirm-yes]");
  const cancelButton = confirmElement.querySelector("[data-role=confirm-no]");
  let available = false;
  let editing = false;
  let pending = null;

  function showHint(text) {
    hintElement.textContent = text;
    hintElement.hidden = !text;
  }

  function closeConfirm() {
    pending = null;
    confirmElement.hidden = true;
    confirmText.textContent = "";
  }

  function openConfirm(targets) {
    if (targets.length === 0) {
      showHint("No ended sessions to remove.");
      return;
    }
    pending = targets;
    confirmText.textContent = describeRemoval(targets);
    confirmElement.hidden = false;
    confirmButton.focus?.();
  }

  function refresh() {
    toggleButton.disabled = !available;
    toggleButton.setAttribute("aria-pressed", String(editing));
    toggleButton.textContent = editing ? "Done" : "Edit";
    removeAllButton.hidden = !editing;
    removeAllButton.disabled = endedSessions(getState()).length === 0;
    document.body.dataset.mode = editing ? "edit" : "view";
    draw.setEditing(editing);
    if (!available) showHint(FIXTURE_HINT);
    else if (!editing) showHint("");
    else showHint("Edit mode: click × on a capsule to remove it.");
  }

  async function performRemoval(targets) {
    const failures = [];
    for (const target of targets) {
      try {
        const response = await request(removeUrl(target.pid), { method: "POST" });
        if (!response.ok) failures.push(`${target.session ?? target.pid}: ${response.status}`);
      } catch (error) {
        failures.push(`${target.session ?? target.pid}: ${error.message}`);
      }
    }
    closeConfirm();
    if (failures.length > 0) showHint(`Removal failed for ${failures.join(", ")}.`);
    else if (editing) showHint(`Removed ${targets.length === 1 ? (targets[0].session ?? `pid ${targets[0].pid}`) : `${targets.length} sessions`}.`);
    return failures;
  }

  toggleButton.addEventListener("click", () => {
    editing = !editing;
    closeConfirm();
    refresh();
  });
  removeAllButton.addEventListener("click", () => openConfirm(endedSessions(getState())));
  confirmButton.addEventListener("click", () => { if (pending) performRemoval(pending); });
  cancelButton.addEventListener("click", closeConfirm);

  refresh();
  return {
    // Enables the editor when a live server is connected; disables it with the fixture hint otherwise.
    setAvailable(value) {
      available = Boolean(value);
      if (!available) {
        editing = false;
        closeConfirm();
      }
      refresh();
    },
    // Opens the confirmation for one capsule, called by the renderer's remove control.
    requestRemove(session) {
      if (!editing || !available) return;
      openConfirm([session]);
    },
    // Re-evaluates the Remove-all-ended button after state changes.
    refresh,
    get isEditing() {
      return editing;
    },
    get pending() {
      return pending;
    },
  };
}
