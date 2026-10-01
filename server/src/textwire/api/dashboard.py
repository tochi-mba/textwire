"""The dashboard page: one self-contained HTML document, no external assets.

It polls ``/api/overview`` every five seconds and renders the server's state: whether it is
alive and configured, today's budget and cost, the requests it answered, the documents it
is holding for paging, and a button to send the route probe.

The colours are the REX ink/signal palette, the same one the site and the app use. The
script is plain JavaScript with no build step; ``tests/test_javascript.py`` runs it in Node
against a stand-in page.
"""

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#080A09">
<title>textwire dashboard - REX Technologies</title>
<style>
  :root {
    --ink: #080A09; --panel: #111512; --raised: #181E19; --line: #29302A; --text: #F2F5EE;
    --muted: #858D83; --signal: #D7FF3F; --live: #FF774D; --warn: #FFC857;
    --mono: "Cascadia Mono", "SF Mono", Consolas, ui-monospace, Menlo, monospace;
    color-scheme: dark;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.5 Inter, "Segoe UI", system-ui, -apple-system, sans-serif;
         background: var(--ink); color: var(--text); -webkit-font-smoothing: antialiased; }
  a { color: var(--signal); }
  :focus-visible { outline: 2px solid var(--signal); outline-offset: 3px; border-radius: 4px; }
  .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
  header { display: flex; align-items: center; gap: 14px; padding: 16px 24px; border-bottom: 1px solid var(--line); background: var(--panel); }
  .mark { width: 36px; height: 36px; border-radius: 9px; display: grid; place-items: center; background: var(--raised); border: 1px solid var(--line); }
  .mark svg { width: 23px; fill: none; stroke: var(--signal); stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
  .lockup { display: flex; flex-direction: column; line-height: 1.15; }
  .company { font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--signal); }
  header h1 { margin: 0; font-size: 16px; font-weight: 700; }
  header .sub { margin-left: auto; color: var(--muted); font-size: 13px; text-align: right; }
  main { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; padding: 20px 24px 32px; max-width: 1280px; margin: 0 auto; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 20px 22px; min-width: 0; }
  .card h2 { margin: 0 0 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.14em; color: var(--signal); }
  .wide { grid-column: 1 / -1; }
  .big { font-size: 40px; font-weight: 900; letter-spacing: -0.03em; line-height: 1.1; }
  .row { display: flex; justify-content: space-between; gap: 12px; padding: 6px 0; border-bottom: 1px solid var(--line); }
  .row:last-child { border-bottom: 0; }
  .muted { color: var(--muted); }
  .pill { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
  .ok { background: rgba(215,255,63,.12); color: var(--signal); }
  .warn { background: rgba(255,200,87,.14); color: var(--warn); }
  .bad { background: rgba(255,119,77,.16); color: var(--live); }
  .bar { height: 10px; border-radius: 999px; background: var(--raised); border: 1px solid var(--line); overflow: hidden; margin: 12px 0 8px; }
  .bar > div { height: 100%; background: var(--signal); transition: width 0.4s; }
  .scroll { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
  tbody tr:last-child td { border-bottom: 0; }
  th { color: var(--muted); font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.14em; white-space: nowrap; }
  td.mono { font-family: var(--mono); font-size: 13px; word-break: break-all; }
  form { display: flex; gap: 8px; margin-top: 12px; }
  input { flex: 1; min-width: 0; min-height: 44px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--ink); color: var(--text); font: inherit; }
  input::placeholder { color: var(--muted); }
  button { min-height: 44px; padding: 8px 16px; border: 0; border-radius: 8px; background: var(--signal); color: var(--ink); font: inherit; font-weight: 700; cursor: pointer; }
  button:disabled { opacity: 0.5; cursor: default; }
  #result { margin-top: 10px; font-size: 14px; min-height: 1.5em; }
  .empty { color: var(--muted); margin: 12px 0 0; }
  footer { padding: 0 24px 28px; color: var(--muted); font-size: 13px; max-width: 1280px; margin: 0 auto; }
  @media (prefers-reduced-motion: reduce) { .bar > div { transition: none; } }
  @media (max-width: 520px) { header .sub { display: none; } main, footer { padding-inline: 16px; } }
</style>
</head>
<body>
<header>
  <span class="mark" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M6 8h20v13H15l-5 4v-4H6z"/><path d="M10 15h3l2-3 2 6 2-3h3"/></svg></span>
  <div class="lockup"><span class="company">REX Technologies</span><h1>textwire</h1></div>
  <span class="sub" id="subtitle">connecting&hellip;</span>
</header>
<main>
  <section class="card" aria-labelledby="status-heading">
    <h2 id="status-heading">Status</h2>
    <div class="row"><span>Server</span><span id="status" class="pill warn" role="status">waiting</span></div>
    <div class="row"><span>Transport</span><span id="transport" class="muted">&ndash;</span></div>
    <div class="row"><span>Number</span><span id="number" class="muted">&ndash;</span></div>
    <div class="row"><span>Allowed phones</span><span id="allowed" class="muted">&ndash;</span></div>
    <div class="row"><span>Frame alphabet</span><span id="alphabet" class="muted">&ndash;</span></div>
    <div class="row"><span>Page size</span><span id="page_frames" class="muted">&ndash;</span></div>
  </section>
  <section class="card" aria-labelledby="budget-heading">
    <h2 id="budget-heading">Today's budget</h2>
    <div class="big"><span id="used">0</span><span class="muted"> / <span id="limit">0</span> SMS</span></div>
    <div class="bar" id="meter" role="progressbar" aria-labelledby="budget-heading" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div id="bar" style="width:0%"></div></div>
    <div class="row"><span>Estimated cost</span><span id="estimate">&ndash;</span></div>
    <div class="row"><span>Charged so far (from the provider)</span><span id="actual">&ndash;</span></div>
    <div class="row"><span>Sent today</span><span id="outbound">&ndash;</span></div>
    <div class="row"><span>Day (UTC)</span><span id="day" class="muted">&ndash;</span></div>
  </section>
  <section class="card" aria-labelledby="probe-heading">
    <h2 id="probe-heading">Route probe</h2>
    <p class="muted" style="margin:0">Sends one frame holding every byte value to a phone on the allowlist. The app's Diagnostics screen must decode it without a CRC error before the denser alphabet is switched on. It costs one SMS.</p>
    <form id="probe"><label class="sr-only" for="probe-number">Phone number to probe</label><input id="probe-number" type="tel" inputmode="tel" autocomplete="off" placeholder="+447700900123" required><button type="submit">Send probe</button></form>
    <div id="result" class="muted" role="status"></div>
  </section>
  <section class="card wide" aria-labelledby="requests-heading">
    <h2 id="requests-heading">Recent requests</h2>
    <div class="scroll"><table><thead><tr><th scope="col">When</th><th scope="col">From</th><th scope="col">Request</th><th scope="col">Replies</th><th scope="col">State</th></tr></thead><tbody id="requests"></tbody></table></div>
    <p id="requests-empty" class="empty">No requests yet. Text the number from a phone on the allowlist.</p>
  </section>
  <section class="card wide" aria-labelledby="documents-heading">
    <h2 id="documents-heading">Documents held for paging and links</h2>
    <div class="scroll"><table><thead><tr><th scope="col">When</th><th scope="col">For</th><th scope="col">Reply</th><th scope="col">Kind</th><th scope="col">Title</th><th scope="col">Size</th></tr></thead><tbody id="documents"></tbody></table></div>
    <p id="documents-empty" class="empty">Nothing fetched yet.</p>
  </section>
</main>
<footer>A REX Technologies product. <span id="version"></span> &middot; refreshes every 5 seconds &middot; <a href="/healthy">/healthy</a> &middot; <a href="/ready">/ready</a> &middot; <a href="/api/overview">/api/overview</a></footer>
<script>
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const when = (iso) => iso ? new Date(iso).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"}) : "";
  async function refresh() {
    let data;
    try {
      const response = await fetch("/api/overview", {cache: "no-store"});
      if (!response.ok) throw new Error(response.status);
      data = await response.json();
    } catch (error) {
      $("status").textContent = "unreachable"; $("status").className = "pill bad";
      $("subtitle").textContent = "the server is not answering";
      return;
    }
    $("status").textContent = "serving"; $("status").className = "pill ok";
    $("subtitle").textContent = `${data.environment} · ${data.now.replace("T", " ").slice(0, 19)} UTC`;
    $("transport").textContent = data.transport;
    $("number").textContent = data.number || "not set";
    $("allowed").textContent = data.allowed;
    $("alphabet").textContent = data.alphabet;
    $("page_frames").textContent = `${data.page_frames} SMS`;
    $("version").textContent = `v${data.version}`;
    const b = data.budget;
    $("used").textContent = b.used; $("limit").textContent = b.limit;
    const share = b.limit ? Math.min(100, Math.round(100 * b.used / b.limit)) : 0;
    $("bar").style.width = share + "%";
    $("bar").style.background = share >= 90 ? "var(--live)" : share >= 60 ? "var(--warn)" : "var(--signal)";
    $("meter").setAttribute("aria-valuenow", String(share));
    $("estimate").textContent = `~${b.estimated_cost.toFixed(2)} ${b.currency}`;
    $("actual").textContent = `${b.actual_cost.toFixed(2)} ${b.currency}`;
    $("outbound").textContent = `${data.outbound_today} SMS`;
    $("day").textContent = b.day;
    const requests = data.requests;
    $("requests-empty").style.display = requests.length ? "none" : "";
    $("requests").innerHTML = requests.map((r) => {
      const state = r.handled_at ? '<span class="pill ok">answered</span>' : '<span class="pill warn">in progress</span>';
      return `<tr><td>${esc(when(r.received_at))}</td><td class="mono">${esc(r.number)}</td><td class="mono">${esc(r.body)}</td><td>${esc(r.replies)}</td><td>${state}</td></tr>`;
    }).join("");
    const documents = data.documents;
    $("documents-empty").style.display = documents.length ? "none" : "";
    $("documents").innerHTML = documents.map((d) =>
      `<tr><td>${esc(when(d.created_at))}</td><td class="mono">${esc(d.number)}</td><td class="mono">${esc(d.tag)}</td><td>${esc(d.kind)}</td><td>${esc(d.title)}</td><td>${esc(d.page_size)} ${d.plain ? "plain" : "SMS"}</td></tr>`
    ).join("");
  }
  $("probe").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.target.querySelector("button");
    button.disabled = true; $("result").textContent = "sending…";
    try {
      const response = await fetch("/api/probe", {method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({number: $("probe-number").value.trim()})});
      const body = await response.json();
      $("result").textContent = response.ok ? `sent ${body.id} (${body.characters} characters) to ${body.to}` : `refused: ${body.detail}`;
    } catch (error) {
      $("result").textContent = "the server did not answer";
    } finally {
      button.disabled = false; refresh();
    }
  });
  refresh();
  setInterval(refresh, 5000);
</script>
</body>
</html>
"""
