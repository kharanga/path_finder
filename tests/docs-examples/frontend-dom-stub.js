class ClassList {
  constructor(el) { this.el = el; }
  get set() { return new Set((this.el.attrs.get("class") || "").split(/\s+/).filter(Boolean)); }
  write(s) { this.el.attrs.set("class", [...s].join(" ")); }
  add(...n) { const s = this.set; n.forEach((x) => s.add(x)); this.write(s); }
  remove(...n) { const s = this.set; n.forEach((x) => s.delete(x)); this.write(s); }
  toggle(n, force) { const s = this.set; const on = force === undefined ? !s.has(n) : force; on ? s.add(n) : s.delete(n); this.write(s); return on; }
  contains(n) { return this.set.has(n); }
}
class Style {
  constructor() { this.props = new Map(); this.transform = ""; this.left = ""; this.overflow = ""; }
  setProperty(k, v) { this.props.set(k, v); }
}
export class Element {
  constructor(tag, ns = null) {
    this.tagName = tag.toUpperCase(); this.localName = tag; this.ns = ns; this.attrs = new Map(); this.children = []; this.parentNode = null;
    this.listeners = new Map(); this.style = new Style(); this.classList = new ClassList(this); this._text = ""; this.hidden = false; this.disabled = false;
    this._value = "0"; this.min = "0"; this.max = "0"; this.title = ""; this.type = "";
    this.dataset = new Proxy({}, { get: (_, k) => this.attrs.get("data-" + camelToKebab(k)), set: (_, k, v) => { this.attrs.set("data-" + camelToKebab(k), String(v)); return true; } });
  }
  get value() { return this._value; } set value(v) { this._value = String(v); }
  get className() { return this.attrs.get("class") || ""; } set className(v) { this.attrs.set("class", String(v)); }
  setAttribute(k, v) { this.attrs.set(k, String(v)); } getAttribute(k) { return this.attrs.has(k) ? this.attrs.get(k) : null; } hasAttribute(k) { return this.attrs.has(k); }
  setAttributeNS(ns, k, v) { this.attrs.set(k, String(v)); }
  appendChild(c) { c.remove(); c.parentNode = this; this.children.push(c); return c; }
  insertBefore(c, ref) { c.remove(); c.parentNode = this; const i = ref ? this.children.indexOf(ref) : -1; i < 0 ? this.children.push(c) : this.children.splice(i, 0, c); return c; }
  removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); c.parentNode = null; return c; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  get firstChild() { return this.children[0] ?? null; }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); } set textContent(v) { this._text = String(v); this.children = []; }
  addEventListener(t, fn) { if (!this.listeners.has(t)) this.listeners.set(t, []); this.listeners.get(t).push(fn); }
  dispatchEvent(ev) { ev.target = this; ev.preventDefault ??= () => {}; (this.listeners.get(ev.type) || []).forEach((fn) => fn(ev)); return true; }
  click() { this.dispatchEvent({ type: "click" }); }
  focus() { document.activeElement = this; }
  getBoundingClientRect() { return { x: 0, y: 0, width: 0, height: 0 }; }
  matches(sel) { return matchSimple(this, sel); }
  querySelectorAll(sel) { const parts = sel.trim().split(/\s+/); let set = [this]; for (const part of parts) { const next = []; for (const base of set) walk(base, (el) => { if (el !== base && matchSimple(el, part) && !next.includes(el)) next.push(el); }); set = next; } return set; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] ?? null; }
  getElementById(id) { let found = null; walk(this, (el) => { if (!found && el.attrs.get("id") === id) found = el; }); return found; }
}
function camelToKebab(k) { return k.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase()); }
function walk(el, fn) { fn(el); for (const c of el.children) walk(c, fn); }
function matchSimple(el, sel) {
  const m = sel.match(/^([a-zA-Z]*)((?:[.#\[][^.#\[]*)*)$/); if (!m) return false;
  if (m[1] && el.localName !== m[1]) return false;
  const tokens = m[2].match(/\.[^.#\[]+|#[^.#\[]+|\[[^\]]+\]/g) || [];
  for (const t of tokens) {
    if (t[0] === ".") { if (!el.classList.contains(t.slice(1))) return false; }
    else if (t[0] === "#") { if (el.attrs.get("id") !== t.slice(1)) return false; }
    else { const a = t.slice(1, -1).match(/^([^=]+)(?:=(.*))?$/); const v = a[2]?.replace(/^["']|["']$/g, ""); if (!el.attrs.has(a[1])) return false; if (a[2] !== undefined && el.attrs.get(a[1]) !== v) return false; }
  }
  return true;
}
export const document = new Element("html");
document.createElement = (tag) => new Element(tag);
document.createElementNS = (ns, tag) => new Element(tag, ns);
document.activeElement = null;
export function installGlobals() {
  globalThis.document = document;
  globalThis.Event = class { constructor(type) { this.type = type; } preventDefault() {} };
  globalThis.location = { search: "" };
}
