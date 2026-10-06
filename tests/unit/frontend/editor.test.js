import { test } from "node:test";
import assert from "node:assert/strict";
import { installDomStub, uninstallDomStub } from "../../helpers/dom-stub.js";
import { removeUrl, endedSessions, describeRemoval, createEditor } from "../../../frontend/editor.js";
import { createState, applySessionEvent } from "../../../frontend/state.js";

const FIXTURE_HINT = "Removal needs the server. Fixture mode has none.";
const session = (overrides) => ({ ts: "2026-10-06T09:00:00Z", type: "session", session: "listings-bc", folder: "listings", pid: 29904, state: "idle", role: null, ...overrides });
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

test.before(() => installDomStub());
test.after(() => uninstallDomStub());

const markup = () => {
  const element = (tag, attributes = {}) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    return node;
  };
  const confirmElement = element("div", { role: "alertdialog" });
  confirmElement.hidden = true;
  const parts = { confirmText: element("span", { "data-role": "confirm-text" }), confirmYes: element("button", { "data-role": "confirm-yes" }), confirmNo: element("button", { "data-role": "confirm-no" }) };
  for (const part of Object.values(parts)) confirmElement.appendChild(part);
  return { toggleButton: element("button"), removeAllButton: element("button"), hintElement: element("span"), confirmElement, ...parts };
};

const build = (overrides = {}) => {
  const elements = markup();
  const state = createState();
  const editingCalls = [];
  const calls = [];
  const draw = { setEditing: (value) => editingCalls.push(value) };
  const request = overrides.request ?? (async (url, init) => { calls.push([url, init.method]); return { ok: true, status: 204 }; });
  const editor = createEditor({ toggleButton: elements.toggleButton, removeAllButton: elements.removeAllButton, hintElement: elements.hintElement, confirmElement: elements.confirmElement, getState: () => state, draw, request });
  return { ...elements, state, editor, calls, editingCalls };
};

test("removeUrl encodes the pid into the endpoint path", () => {
  assert.equal(removeUrl(29904), "/sessions/29904/remove");
  assert.equal(removeUrl("a b"), "/sessions/a%20b/remove");
});

test("endedSessions lists only sessions in state ended", () => {
  const state = createState();
  applySessionEvent(state, session({ pid: 1, state: "ended" }));
  applySessionEvent(state, session({ pid: 2, state: "idle" }));
  applySessionEvent(state, session({ pid: 3, state: "removed" }));
  applySessionEvent(state, session({ pid: 4, session: "z-4", state: "ended" }));
  assert.deepEqual(endedSessions(state).map((s) => s.pid), [1, 4]);
  assert.deepEqual(endedSessions(createState()), []);
});

test("describeRemoval writes the confirmation sentence", () => {
  assert.equal(describeRemoval([]), "Nothing to remove.");
  assert.equal(describeRemoval([{ pid: 29904, session: "listings-bc" }]), "Remove listings-bc from the board?");
  assert.equal(describeRemoval([{ pid: 7, session: null }]), "Remove pid 7 from the board?");
  assert.equal(describeRemoval([{ pid: 1 }, { pid: 2 }]), "Remove 2 ended sessions from the board?");
});

test("the editor starts unavailable with the fixture hint and ignores remove requests", () => {
  const { editor, toggleButton, removeAllButton, hintElement, confirmElement, editingCalls } = build();
  assert.equal(toggleButton.disabled, true);
  assert.equal(toggleButton.textContent, "Edit");
  assert.equal(toggleButton.getAttribute("aria-pressed"), "false");
  assert.equal(removeAllButton.hidden, true);
  assert.equal(hintElement.textContent, FIXTURE_HINT);
  assert.equal(hintElement.hidden, false);
  assert.equal(document.body.dataset.mode, "view");
  assert.deepEqual(editingCalls, [false]);
  editor.requestRemove(session());
  assert.equal(confirmElement.hidden, true);
  assert.equal(editor.pending, null);
});

test("edit mode toggles controls, confirms one removal, posts to the server, and reports success", async () => {
  const { editor, toggleButton, removeAllButton, hintElement, confirmElement, confirmText, confirmYes, calls, editingCalls } = build();
  editor.setAvailable(true);
  assert.equal(toggleButton.disabled, false);
  assert.equal(hintElement.textContent, "");
  toggleButton.click();
  assert.equal(editor.isEditing, true);
  assert.equal(toggleButton.textContent, "Done");
  assert.equal(toggleButton.getAttribute("aria-pressed"), "true");
  assert.equal(document.body.dataset.mode, "edit");
  assert.equal(removeAllButton.hidden, false);
  assert.equal(removeAllButton.disabled, true);
  assert.equal(editingCalls.at(-1), true);
  assert.equal(hintElement.textContent, "Edit mode: click × on a capsule to remove it.");
  editor.requestRemove(session());
  assert.equal(confirmElement.hidden, false);
  assert.equal(confirmText.textContent, "Remove listings-bc from the board?");
  assert.deepEqual(editor.pending.map((s) => s.pid), [29904]);
  assert.equal(document.activeElement, confirmYes);
  assert.deepEqual(calls, []);
  confirmYes.click();
  await tick();
  assert.deepEqual(calls, [["/sessions/29904/remove", "POST"]]);
  assert.equal(confirmElement.hidden, true);
  assert.equal(editor.pending, null);
  assert.equal(hintElement.textContent, "Removed listings-bc.");
  toggleButton.click();
  assert.equal(editor.isEditing, false);
  assert.equal(toggleButton.textContent, "Edit");
  assert.equal(removeAllButton.hidden, true);
  assert.equal(editingCalls.at(-1), false);
  assert.equal(hintElement.textContent, "");
});

test("cancel closes the confirmation without a request, and leaving edit mode or losing the server closes it too", async () => {
  const { editor, toggleButton, confirmElement, confirmNo, calls } = build();
  editor.setAvailable(true);
  toggleButton.click();
  editor.requestRemove(session());
  confirmNo.click();
  assert.equal(confirmElement.hidden, true);
  assert.equal(editor.pending, null);
  editor.requestRemove(session());
  toggleButton.click();
  assert.equal(confirmElement.hidden, true);
  toggleButton.click();
  editor.requestRemove(session());
  editor.setAvailable(false);
  assert.equal(editor.isEditing, false);
  assert.equal(confirmElement.hidden, true);
  assert.equal(toggleButton.disabled, true);
  await tick();
  assert.deepEqual(calls, []);
});

test("remove all ended targets every ended session with one confirmation and one request each", async () => {
  const { editor, state, toggleButton, removeAllButton, confirmText, confirmYes, hintElement, calls } = build();
  editor.setAvailable(true);
  toggleButton.click();
  removeAllButton.click();
  assert.equal(hintElement.textContent, "No ended sessions to remove.");
  applySessionEvent(state, session({ pid: 1, session: "a-1", state: "ended" }));
  applySessionEvent(state, session({ pid: 2, session: "b-2", state: "ended" }));
  applySessionEvent(state, session({ pid: 3, session: "c-3", state: "busy" }));
  editor.refresh();
  assert.equal(removeAllButton.disabled, false);
  removeAllButton.click();
  assert.equal(confirmText.textContent, "Remove 2 ended sessions from the board?");
  confirmYes.click();
  await tick();
  await tick();
  assert.deepEqual(calls.map(([url]) => url), ["/sessions/1/remove", "/sessions/2/remove"]);
  assert.equal(hintElement.textContent, "Removed 2 sessions.");
});

test("a failing or throwing request leaves the page untouched and reports the failure in the hint", async () => {
  const responses = [{ ok: false, status: 404 }, new Error("socket closed")];
  const { editor, toggleButton, confirmYes, hintElement, confirmElement } = build({ request: async () => { const next = responses.shift(); if (next instanceof Error) throw next; return next; } });
  editor.setAvailable(true);
  toggleButton.click();
  editor.requestRemove(session());
  confirmYes.click();
  await tick();
  assert.equal(hintElement.textContent, "Removal failed for listings-bc: 404.");
  assert.equal(confirmElement.hidden, true);
  editor.requestRemove(session({ pid: 5, session: null }));
  confirmYes.click();
  await tick();
  assert.equal(hintElement.textContent, "Removal failed for 5: socket closed.");
});

test("createEditor throws when the confirmation markup is incomplete", () => {
  const { toggleButton, removeAllButton, hintElement } = markup();
  assert.throws(() => createEditor({ toggleButton, removeAllButton, hintElement, confirmElement: document.createElement("div"), getState: createState, draw: { setEditing() {} } }), TypeError);
});
