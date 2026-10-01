// The landing page's script (site/app.js), run against a stand-in page.
//
// tests/test_javascript.py passes the script's path in TEXTWIRE_SITE_SCRIPT.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { FakeDocument, run, settle } from './dom.mjs';

const SCRIPT = readFileSync(process.env.TEXTWIRE_SITE_SCRIPT, 'utf8');

// A page with a menu button, a navigation of two links, one Copy button, and the footer year.
function page({ clipboard = async () => {} } = {}) {
  const document = new FakeDocument();
  const menu = document.element();
  menu.setAttribute('aria-expanded', 'false');
  const nav = document.element();
  nav.inside = [document.element(), document.element()];
  nav.found = { a: nav.inside[0] };
  const copy = document.element();
  copy.textContent = 'Copy';
  copy.dataset.copy = 'make simulate';
  const status = document.element('copy-status');
  const year = document.element('year');
  year.textContent = '2026';
  document.selectors = { '.menu-button': menu, '.site-nav': nav };
  document.lists = { '.copy-button': [copy] };
  document.ids = { 'copy-status': status, year };
  const copied = [];
  const timers = [];
  const navigator = {
    clipboard: {
      writeText: async (text) => {
        await clipboard(text);
        copied.push(text);
      },
    },
  };
  run(SCRIPT, { document, navigator, setTimeout: (callback, after) => timers.push({ callback, after }) });
  return { document, menu, nav, copy, status, year, copied, timers };
}

const open = (p) => p.nav.classList.contains('open');

test('the menu button opens and closes the navigation and says which', async () => {
  const p = page();
  assert.equal(open(p), false);
  await p.menu.dispatch('click');
  assert.equal(open(p), true);
  assert.equal(p.menu.getAttribute('aria-expanded'), 'true');
  await p.menu.dispatch('click');
  assert.equal(open(p), false);
  assert.equal(p.menu.getAttribute('aria-expanded'), 'false');
});

test('following a link closes the menu and leaves focus alone', async () => {
  const p = page();
  await p.menu.dispatch('click');
  await p.nav.inside[1].dispatch('click');
  assert.equal(open(p), false);
  assert.equal(p.document.activeElement, null);
});

test('Escape closes the menu and returns focus to its button', async () => {
  const p = page();
  await p.menu.dispatch('click');
  await p.document.dispatch('keydown', { key: 'Tab' });
  assert.equal(open(p), true);
  await p.document.dispatch('keydown', { key: 'Escape' });
  assert.equal(open(p), false);
  assert.equal(p.menu.getAttribute('aria-expanded'), 'false');
  assert.equal(p.document.activeElement, p.menu);
});

test('while the menu is open, focus that leaves it is brought back', async () => {
  const p = page();
  const elsewhere = p.document.element();
  // Closed: focus goes wherever it likes.
  await p.document.dispatch('focusin', { target: elsewhere });
  assert.equal(p.document.activeElement, null);
  await p.menu.dispatch('click');
  // Inside the menu or on its button: left alone.
  await p.document.dispatch('focusin', { target: p.nav.inside[1] });
  await p.document.dispatch('focusin', { target: p.menu });
  assert.equal(p.document.activeElement, null);
  // Anywhere else: back to the first link.
  await p.document.dispatch('focusin', { target: elsewhere });
  assert.equal(p.document.activeElement, p.nav.inside[0]);
});

test('a Copy button copies its command, says so, and then resets', async () => {
  const p = page();
  await p.copy.dispatch('click');
  assert.deepEqual(p.copied, ['make simulate']);
  assert.equal(p.copy.textContent, 'Copied');
  assert.equal(p.status.textContent, 'Command copied to the clipboard');
  assert.equal(p.timers.length, 1);
  assert.equal(p.timers[0].after, 1400);
  p.timers[0].callback();
  assert.equal(p.copy.textContent, 'Copy');
});

test('a clipboard that refuses is reported, not swallowed', async () => {
  const p = page({
    clipboard: async () => {
      throw new Error('denied');
    },
  });
  await p.copy.dispatch('click');
  assert.deepEqual(p.copied, []);
  assert.equal(p.copy.textContent, 'Copy failed');
  assert.equal(p.status.textContent, 'Could not copy the command');
});

test('the footer shows the current year', () => {
  const p = page();
  assert.equal(p.year.textContent, String(new Date().getFullYear()));
});

test('a page with none of these parts does not break the script', async () => {
  const document = new FakeDocument();
  run(SCRIPT, { document, navigator: {}, setTimeout: () => {} });
  await document.dispatch('keydown', { key: 'Escape' });
  await document.dispatch('focusin', { target: document.element() });
  await settle();
  assert.equal(document.activeElement, null);
});

test('a Copy button still works on a page with no status line', async () => {
  const document = new FakeDocument();
  const copy = document.element();
  copy.textContent = 'Copy';
  copy.dataset.copy = 'make run';
  document.lists = { '.copy-button': [copy] };
  const copied = [];
  run(SCRIPT, {
    document,
    navigator: { clipboard: { writeText: async (text) => copied.push(text) } },
    setTimeout: () => {},
  });
  await copy.dispatch('click');
  assert.deepEqual(copied, ['make run']);
  assert.equal(copy.textContent, 'Copied');
});
