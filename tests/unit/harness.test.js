import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { installDomStub, uninstallDomStub } from "../helpers/dom-stub.js";
import { makeTmpDir } from "../helpers/tmp-dir.js";

test("dom stub resolves class, data-pid, and tag selectors", () => {
  const root = installDomStub();
  const group = document.createElementNS("svg", "g");
  group.setAttribute("class", "body entering");
  group.setAttribute("data-pid", "42");
  const title = group.appendChild(document.createElementNS("svg", "title"));
  root.appendChild(group);
  assert.equal(root.querySelector('.body[data-pid="42"] title'), title);
  assert.equal(root.querySelectorAll(".entering").length, 1);
  group.classList.remove("entering");
  assert.equal(root.querySelector(".entering"), null);
  uninstallDomStub();
  assert.equal(typeof document, "undefined");
});

test("tmp dir helper creates and removes a directory", () => {
  const { path, cleanup } = makeTmpDir();
  assert.ok(existsSync(path));
  cleanup();
  assert.equal(existsSync(path), false);
});
