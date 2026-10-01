// A stand-in for the few parts of a browser page the project's scripts touch.
//
// The dashboard's script and the site's app.js are plain JavaScript with no build step and
// no dependencies, so their tests have none either: this file, node:test and node:vm.

import vm from 'node:vm';

export class FakeElement {
  constructor(document, id = '') {
    this.document = document;
    this.id = id;
    this.textContent = '';
    this.className = '';
    this.innerHTML = '';
    this.value = '';
    this.disabled = false;
    this.style = {};
    this.dataset = {};
    this.attributes = {};
    this.listeners = {};
    this.inside = [];
    this.found = {};
    const classes = new Set();
    this.classList = {
      toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)),
      contains: (name) => classes.has(name),
    };
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  getAttribute(name) {
    return this.attributes[name] ?? null;
  }

  addEventListener(type, listener) {
    (this.listeners[type] ??= []).push(listener);
  }

  // Runs every listener for the event and waits for the asynchronous ones.
  async dispatch(type, event = {}) {
    const sent = { target: this, preventDefault() {}, ...event };
    for (const listener of this.listeners[type] ?? []) await listener(sent);
  }

  querySelector(selector) {
    return this.found[selector] ?? null;
  }

  querySelectorAll(selector) {
    return selector === 'a' ? this.inside : [];
  }

  contains(element) {
    return this.inside.includes(element);
  }

  focus() {
    this.document.activeElement = this;
  }
}

export class FakeDocument {
  // With `invent`, getElementById makes the element on first use, the way a full page would
  // already hold it; without, only registered elements exist.
  constructor({ invent = false } = {}) {
    this.invent = invent;
    this.ids = {};
    this.selectors = {};
    this.lists = {};
    this.listeners = {};
    this.activeElement = null;
  }

  element(id = '') {
    return new FakeElement(this, id);
  }

  getElementById(id) {
    if (!(id in this.ids) && this.invent) this.ids[id] = this.element(id);
    return this.ids[id] ?? null;
  }

  querySelector(selector) {
    return this.selectors[selector] ?? null;
  }

  querySelectorAll(selector) {
    return this.lists[selector] ?? [];
  }

  addEventListener(type, listener) {
    (this.listeners[type] ??= []).push(listener);
  }

  async dispatch(type, event = {}) {
    for (const listener of this.listeners[type] ?? []) await listener(event);
  }
}

// Runs a script the way a <script> tag would, with these globals and nothing else.
export function run(code, globals) {
  const context = vm.createContext({ console, ...globals });
  vm.runInContext(code, context);
  return context;
}

// Lets every promise the script started settle.
export const settle = () => new Promise((resolve) => setImmediate(resolve));
