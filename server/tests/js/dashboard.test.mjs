// The dashboard's script, run against a stand-in page and a stand-in server.
//
// tests/test_javascript.py extracts the script from the page the server serves
// and passes its path in TEXTWIRE_DASHBOARD_SCRIPT, so this tests what is shipped.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { FakeDocument, run, settle } from './dom.mjs';

const SCRIPT = readFileSync(process.env.TEXTWIRE_DASHBOARD_SCRIPT, 'utf8');

const overview = (changes = {}) => ({
  environment: 'development',
  now: '2026-10-01T12:34:56.789012+00:00',
  version: '0.1.0',
  transport: 'twilio',
  number: '+447700900000',
  allowed: 1,
  alphabet: 'b64',
  page_frames: 12,
  outbound_today: 16,
  budget: { used: 16, limit: 200, estimated_cost: 0.896, actual_cost: 0.9, currency: 'USD', day: '2026-10-01' },
  requests: [],
  documents: [],
  config: { TEXTWIRE_PAGE_FRAMES: 12, TEXTWIRE_DASHBOARD: true },
  ...changes,
});

const json = (body, ok = true, status = 200) => ({ ok, status, json: async () => body });

// Starts the dashboard with a server that answers each path from `routes`.
async function start(routes) {
  const document = new FakeDocument({ invent: true });
  const button = document.element();
  document.getElementById('probe').found.button = button;
  const calls = [];
  const timers = [];
  const fetch = async (path, options = {}) => {
    calls.push({ path, options });
    const answer = routes[path];
    if (answer instanceof Error) throw answer;
    return typeof answer === 'function' ? answer(options) : answer;
  };
  const context = run(SCRIPT, { document, fetch, setInterval: (callback, every) => timers.push({ callback, every }) });
  await settle();
  return { document, button, calls, timers, context, text: (id) => document.getElementById(id).textContent };
}

test('the overview fills the status and the budget', async () => {
  const page = await start({ '/api/overview': json(overview()) });
  assert.equal(page.text('status'), 'serving');
  assert.equal(page.document.getElementById('status').className, 'pill ok');
  assert.equal(page.text('subtitle'), 'development · 2026-10-01 12:34:56 UTC');
  assert.equal(page.text('transport'), 'twilio');
  assert.equal(page.text('number'), '+447700900000');
  assert.equal(page.text('allowed'), 1);
  assert.equal(page.text('alphabet'), 'b64');
  assert.equal(page.text('page_frames'), '12 SMS');
  assert.equal(page.text('version'), 'v0.1.0');
  assert.equal(page.text('used'), 16);
  assert.equal(page.text('limit'), 200);
  assert.equal(page.text('estimate'), '~0.90 USD');
  assert.equal(page.text('actual'), '0.90 USD');
  assert.equal(page.text('outbound'), '16 SMS');
  assert.equal(page.text('day'), '2026-10-01');
  assert.equal(page.document.getElementById('bar').style.width, '8%');
  assert.equal(page.document.getElementById('meter').getAttribute('aria-valuenow'), '8');
  assert.equal(page.calls[0].path, '/api/overview');
  assert.equal(page.calls[0].options.cache, 'no-store');
});

test('with nothing to show, the empty messages stay and the tables are empty', async () => {
  const page = await start({ '/api/overview': json(overview({ number: '' })) });
  assert.equal(page.text('number'), 'not set');
  assert.equal(page.document.getElementById('requests-empty').style.display, '');
  assert.equal(page.document.getElementById('documents-empty').style.display, '');
  assert.equal(page.document.getElementById('requests').innerHTML, '');
  assert.equal(page.document.getElementById('documents').innerHTML, '');
});

test('requests and documents become rows and hide the empty messages', async () => {
  const page = await start({
    '/api/overview': json(
      overview({
        requests: [
          { received_at: '2026-10-01T12:00:00+00:00', number: '+44…0123', body: 'a7 g example.com', replies: 12, handled_at: '2026-10-01T12:00:02+00:00' },
          { received_at: '2026-10-01T12:01:00+00:00', number: '+44…0123', body: 'a8 s tea', replies: 0, handled_at: null },
        ],
        documents: [
          { created_at: '2026-10-01T12:00:01+00:00', number: '+44…0123', tag: 'a7', kind: 'page', title: 'Example', page_size: 12, plain: false },
          { created_at: '', number: '+44…0123', tag: 'a9', kind: 'search', title: 'tea', page_size: 3, plain: true },
        ],
      }),
    ),
  });
  const requests = page.document.getElementById('requests').innerHTML;
  assert.equal(requests.match(/<tr>/g).length, 2);
  assert.match(requests, /<td class="mono">a7 g example\.com<\/td><td>12<\/td><td><span class="pill ok">answered<\/span>/);
  assert.match(requests, /<td class="mono">a8 s tea<\/td><td>0<\/td><td><span class="pill warn">in progress<\/span>/);
  const documents = page.document.getElementById('documents').innerHTML;
  assert.match(documents, /<td class="mono">a7<\/td><td>page<\/td><td>Example<\/td><td>12 SMS<\/td>/);
  assert.match(documents, /<tr><td><\/td>.*<td>tea<\/td><td>3 plain<\/td>/);
  assert.equal(page.document.getElementById('requests-empty').style.display, 'none');
  assert.equal(page.document.getElementById('documents-empty').style.display, 'none');
});

test('what a phone texted is shown as text, never run as markup', async () => {
  const attack = `<img src=x onerror="alert('x')"> & more`;
  const page = await start({
    '/api/overview': json(
      overview({
        requests: [{ received_at: '', number: attack, body: attack, replies: attack, handled_at: null }],
        documents: [{ created_at: '', number: attack, tag: attack, kind: attack, title: attack, page_size: attack, plain: false }],
      }),
    ),
  });
  for (const id of ['requests', 'documents']) {
    const html = page.document.getElementById(id).innerHTML;
    assert.ok(!html.includes('<img'), id);
    assert.ok(!html.includes(`"alert`), id);
    assert.ok(!html.includes(`'x'`), id);
    assert.ok(html.includes('&lt;img src=x onerror=&quot;alert(&#39;x&#39;)&quot;&gt; &amp; more'), id);
  }
});

test('the budget bar changes colour as the day is spent', async () => {
  const colour = async (used, limit) => {
    const budget = { ...overview().budget, used, limit };
    const page = await start({ '/api/overview': json(overview({ budget })) });
    const bar = page.document.getElementById('bar');
    return [bar.style.width, bar.style.background];
  };
  assert.deepEqual(await colour(0, 200), ['0%', 'var(--signal)']);
  assert.deepEqual(await colour(118, 200), ['59%', 'var(--signal)']);
  assert.deepEqual(await colour(120, 200), ['60%', 'var(--warn)']);
  assert.deepEqual(await colour(180, 200), ['90%', 'var(--live)']);
  assert.deepEqual(await colour(500, 200), ['100%', 'var(--live)']);
  // A budget of zero refuses everything; it must not divide by zero.
  assert.deepEqual(await colour(0, 0), ['0%', 'var(--signal)']);
});

test('a server that does not answer is said to be unreachable', async () => {
  for (const answer of [new Error('offline'), json({}, false, 503)]) {
    const page = await start({ '/api/overview': answer });
    assert.equal(page.text('status'), 'unreachable');
    assert.equal(page.document.getElementById('status').className, 'pill bad');
    assert.equal(page.text('subtitle'), 'the server is not answering');
    assert.equal(page.text('transport'), '');
  }
});

test('the page asks again every five seconds', async () => {
  const page = await start({ '/api/overview': json(overview()) });
  assert.equal(page.timers.length, 1);
  assert.equal(page.timers[0].every, 5000);
  await page.timers[0].callback();
  assert.equal(page.calls.filter((call) => call.path === '/api/overview').length, 2);
});

test('the probe posts the number and reports what was sent', async () => {
  const page = await start({
    '/api/overview': json(overview()),
    '/api/probe': json({ id: 'SM1', characters: 160, to: '+44…0123' }),
  });
  page.document.getElementById('probe-number').value = '  +447700900123 ';
  let prevented = false;
  let disabledWhileSending = null;
  const probe = page.document.getElementById('probe');
  const original = page.calls.length;
  const sending = probe.dispatch('submit', { preventDefault: () => (prevented = true) });
  disabledWhileSending = page.button.disabled;
  assert.equal(page.text('result'), 'sending…');
  await sending;
  await settle();
  assert.ok(prevented);
  assert.equal(disabledWhileSending, true);
  assert.equal(page.button.disabled, false);
  assert.equal(page.text('result'), 'sent SM1 (160 characters) to +44…0123');
  const post = page.calls[original];
  assert.equal(post.path, '/api/probe');
  assert.equal(post.options.method, 'POST');
  assert.deepEqual(JSON.parse(post.options.body), { number: '+447700900123' });
  assert.equal(post.options.headers['Content-Type'], 'application/json');
  // The overview is fetched again so the SMS the probe cost shows at once.
  assert.equal(page.calls.at(-1).path, '/api/overview');
  assert.equal(page.calls.length, original + 2);
});

test('a refused probe says why', async () => {
  const page = await start({
    '/api/overview': json(overview()),
    '/api/probe': json({ detail: 'that number is not on the allowlist' }, false, 403),
  });
  await page.document.getElementById('probe').dispatch('submit');
  assert.equal(page.text('result'), 'refused: that number is not on the allowlist');
  assert.equal(page.button.disabled, false);
});

test('a probe the server never answers says so and frees the button', async () => {
  const page = await start({ '/api/overview': json(overview()), '/api/probe': new Error('offline') });
  await page.document.getElementById('probe').dispatch('submit');
  assert.equal(page.text('result'), 'the server did not answer');
  assert.equal(page.button.disabled, false);
});

const CONFIG = {
  TEXTWIRE_SEARCH_REGION: 'uk-en',
  TEXTWIRE_SEARCH_SAFESEARCH: 'moderate',
  TEXTWIRE_PAGE_FRAMES: 12,
  TEXTWIRE_DASHBOARD: true,
  TEXTWIRE_DEBUG: false,
  TEXTWIRE_ALLOWED_NUMBERS: ['+44…0123', '+44…0456'],
  TEXTWIRE_DEBUG_DROP_ONCE: [],
  TEXTWIRE_GATEWAY_URL: '',
  TEXTWIRE_TWILIO_AUTH_TOKEN: 'set',
  TEXTWIRE_USER_AGENT: '<b>agent</b>',
};

// The settings drawn, as name and value pairs read back out of the rows' markup.
const drawn = (page) =>
  [...page.document.getElementById('config').innerHTML.matchAll(/<span>(.*?)<\/span><span>(.*?)<\/span>/g)].map(
    (match) => [match[1], match[2]],
  );

test('every setting is listed, switches read on and off, and nothing reads as a dash', async () => {
  const page = await start({ '/api/overview': json(overview({ config: CONFIG })) });
  assert.deepEqual(drawn(page), [
    ['TEXTWIRE_SEARCH_REGION', 'uk-en'],
    ['TEXTWIRE_SEARCH_SAFESEARCH', 'moderate'],
    ['TEXTWIRE_PAGE_FRAMES', '12'],
    ['TEXTWIRE_DASHBOARD', 'on'],
    ['TEXTWIRE_DEBUG', 'off'],
    ['TEXTWIRE_ALLOWED_NUMBERS', '+44…0123, +44…0456'],
    ['TEXTWIRE_DEBUG_DROP_ONCE', '–'],
    ['TEXTWIRE_GATEWAY_URL', '–'],
    ['TEXTWIRE_TWILIO_AUTH_TOKEN', 'set'],
    ['TEXTWIRE_USER_AGENT', '&lt;b&gt;agent&lt;/b&gt;'],
  ]);
  assert.equal(page.document.getElementById('config-empty').style.display, 'none');
});

test('the filter finds settings by name, with spaces for underscores, and by value', async () => {
  const page = await start({ '/api/overview': json(overview({ config: CONFIG })) });
  const filter = page.document.getElementById('config-filter');
  const names = async (typed) => {
    filter.value = typed;
    await filter.dispatch('input');
    return drawn(page).map(([name]) => name);
  };
  assert.deepEqual(await names('search'), ['TEXTWIRE_SEARCH_REGION', 'TEXTWIRE_SEARCH_SAFESEARCH']);
  assert.deepEqual(await names('  Page Frames '), ['TEXTWIRE_PAGE_FRAMES']);
  assert.deepEqual(await names('off'), ['TEXTWIRE_DEBUG']);
  assert.deepEqual(await names('0456'), ['TEXTWIRE_ALLOWED_NUMBERS']);
  assert.deepEqual(await names('nothing like this'), []);
  assert.equal(page.document.getElementById('config-empty').style.display, '');
  assert.equal((await names('')).length, Object.keys(CONFIG).length);
  assert.equal(page.document.getElementById('config-empty').style.display, 'none');
});

test('settings are redrawn only when the server reports different ones', async () => {
  let config = CONFIG;
  const page = await start({ '/api/overview': () => json(overview({ config }))  });
  const list = page.document.getElementById('config');
  list.innerHTML = 'kept';
  await page.timers[0].callback();
  assert.equal(list.innerHTML, 'kept');
  config = { ...CONFIG, TEXTWIRE_PAGE_FRAMES: 20 };
  await page.timers[0].callback();
  assert.ok(drawn(page).some(([name, value]) => name === 'TEXTWIRE_PAGE_FRAMES' && value === '20'));
});

test('before the first answer the empty message stays hidden', async () => {
  const page = await start({ '/api/overview': new Error('offline') });
  const filter = page.document.getElementById('config-filter');
  filter.value = 'x';
  await filter.dispatch('input');
  assert.equal(page.document.getElementById('config-empty').style.display, 'none');
  assert.equal(page.document.getElementById('config').innerHTML, '');
});
