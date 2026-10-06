class ClassList {
  constructor() {
    this.names = new Set();
  }
  add(...names) {
    for (const name of names) this.names.add(name);
  }
  remove(...names) {
    for (const name of names) this.names.delete(name);
  }
  toggle(name, force) {
    const on = force === undefined ? !this.names.has(name) : force;
    on ? this.names.add(name) : this.names.delete(name);
    return on;
  }
  contains(name) {
    return this.names.has(name);
  }
}

class StubElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.attributes = {};
    this.children = [];
    this.parentNode = null;
    this.textContent = "";
    this.classList = new ClassList();
    const attributes = this.attributes;
    this.dataset = new Proxy({}, {
      set(target, key, value) {
        target[key] = String(value);
        attributes[`data-${String(key).replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}`] = String(value);
        return true;
      },
    });
    this.style = { setProperty(name, value) { this[name] = value; } };
    this.listeners = new Map();
    this.disabled = false;
    this.hidden = false;
  }
  get className() {
    return [...this.classList.names].join(" ");
  }
  set className(value) {
    this.classList.names = new Set(String(value).split(/\s+/).filter(Boolean));
  }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }
  dispatchEvent(event) {
    event.preventDefault ??= () => {};
    for (const listener of this.listeners.get(event.type) ?? []) listener(event);
    return true;
  }
  click() {
    this.dispatchEvent({ type: "click" });
  }
  focus() {
    if (globalThis.document) globalThis.document.activeElement = this;
  }
  get firstChild() {
    return this.children[0] ?? null;
  }
  removeChild(child) {
    this.children = this.children.filter((element) => element !== child);
    child.parentNode = null;
    return child;
  }
  setAttributeNS(_namespace, name, value) {
    this.attributes[name] = String(value);
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name.startsWith("data-")) this.dataset[name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value;
    if (name === "class") this.classList.add(...String(value).split(/\s+/).filter(Boolean));
  }
  getAttribute(name) {
    return this.attributes[name] ?? null;
  }
  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  remove() {
    if (this.parentNode) this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
    this.parentNode = null;
  }
  descendants() {
    return this.children.flatMap((child) => [child, ...child.descendants()]);
  }
  querySelectorAll(selector) {
    return this.descendants().filter((element) => matchesSelector(element, selector));
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
}

function matchesSimple(element, simple) {
  if (/^[a-z]+$/i.test(simple)) return element.tagName === simple;
  const attributeOnly = simple.match(/^\[([\w-]+)="?([^"\]]*)"?\]$/);
  if (attributeOnly) return element.attributes[attributeOnly[1]] === attributeOnly[2];
  const match = simple.match(/^\.([\w-]+)(?:\[data-([\w-]+)="([^"]*)"\])?$/);
  if (!match) return false;
  if (!element.classList.contains(match[1])) return false;
  return match[2] === undefined || element.attributes[`data-${match[2]}`] === match[3];
}

function matchesSelector(element, selector) {
  const parts = selector.trim().split(/\s+/);
  if (!matchesSimple(element, parts.at(-1))) return false;
  if (parts.length === 1) return true;
  for (let ancestor = element.parentNode; ancestor; ancestor = ancestor.parentNode) {
    if (matchesSimple(ancestor, parts[0])) return true;
  }
  return false;
}

/** Installs a minimal document, requestAnimationFrame, and matchMedia on globalThis and returns a fresh root element. */
export function installDomStub({ reducedMotion = false } = {}) {
  globalThis.document = {
    createElementNS: (_namespace, tagName) => new StubElement(tagName),
    createElement: (tagName) => new StubElement(tagName),
    addEventListener() {},
    body: new StubElement("body"),
    activeElement: null,
  };
  globalThis.requestAnimationFrame = (callback) => setTimeout(callback, 0);
  globalThis.matchMedia = () => ({ matches: reducedMotion, addEventListener() {} });
  return new StubElement("svg");
}

/** Removes the stubbed globals so later tests see a plain Node environment. */
export function uninstallDomStub() {
  delete globalThis.document;
  delete globalThis.requestAnimationFrame;
  delete globalThis.matchMedia;
}
