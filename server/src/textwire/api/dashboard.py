"""The dashboard page: one self-contained HTML document, no external assets.

It polls ``/api/overview`` every five seconds and renders the server's state: whether it is
alive and configured, today's budget and cost, the requests it answered, the documents it
is holding for paging, and a button to send the route probe.
"""

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>textwire</title>
<style>
  :root {
    --bg: #f6f7f4; --card: #ffffff; --ink: #1d2a1f; --muted: #5d6b5f; --line: #dfe5df;
    --accent: #1b5e20; --accent-ink: #ffffff; --warn: #b26a00; --bad: #b3261e; --good: #2e7d32;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #121613; --card: #1b211c; --ink: #e7ebe6; --muted: #9aa69c; --line: #2b352d;
      --accent: #7cc47f; --accent-ink: #0d1a0e; --warn: #f0b24a; --bad: #ff8a80; --good: #81c784;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         background: var(--bg); color: var(--ink); }
  header { display: flex; align-items: baseline; gap: 12px; padding: 20px 24px 8px; }
  header h1 { margin: 0; font-size: 22px; letter-spacing: 0.02em; }
  header .sub { color: var(--muted); }
  main { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; padding: 8px 24px 32px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; min-width: 0; }
  .card h2 { margin: 0 0 10px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
  .wide { grid-column: 1 / -1; }
  .big { font-size: 34px; font-weight: 600; line-height: 1.1; }
  .row { display: flex; justify-content: space-between; gap: 12px; padding: 4px 0; border-bottom: 1px solid var(--line); }
  .row:last-child { border-bottom: 0; }
  .muted { color: var(--muted); }
  .pill { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .ok { background: color-mix(in srgb, var(--good) 18%, transparent); color: var(--good); }
  .warn { background: color-mix(in srgb, var(--warn) 18%, transparent); color: var(--warn); }
  .bad { background: color-mix(in srgb, var(--bad) 18%, transparent); color: var(--bad); }
  .bar { height: 10px; border-radius: 999px; background: var(--line); overflow: hidden; margin: 10px 0 6px; }
  .bar > div { height: 100%; background: var(--accent); transition: width 0.4s; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; }
  td.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; word-break: break-all; }
  form { display: flex; gap: 8px; margin-top: 8px; }
  input { flex: 1; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--bg); color: var(--ink); font: inherit; }
  button { padding: 8px 14px; border: 0; border-radius: 8px; background: var(--accent); color: var(--accent-ink); font: inherit; font-weight: 600; cursor: pointer; }
  button:disabled { opacity: 0.5; cursor: default; }
  #result { margin-top: 8px; font-size: 14px; }
  .empty { color: var(--muted); font-style: italic; }
  footer { padding: 0 24px 24px; color: var(--muted); font-size: 13px; }
</style>
</head>
<body>
<header>
  <h1>textwire</h1>
  <span class="sub" id="subtitle">connecting&hellip;</span>
</header>
<main>
  <section class="card">
    <h2>Status</h2>
    <div class="row"><span>Server</span><span id="status" class="pill warn">waiting</span></div>
    <div class="row"><span>Transport</span><span id="transport" class="muted">&ndash;</span></div>
    <div class="row"><span>Number</span><span id="number" class="muted">&ndash;</span></div>
    <div class="row"><span>Allowed phones</span><span id="allowed" class="muted">&ndash;</span></div>
    <div class="row"><span>Frame alphabet</span><span id="alphabet" class="muted">&ndash;</span></div>
    <div class="row"><span>Page size</span><span id="page_frames" class="muted">&ndash;</span></div>
  </section>
  <section class="card">
    <h2>Today's budget</h2>
    <div class="big"><span id="used">0</span><span class="muted"> / <span id="limit">0</span> SMS</span></div>
    <div class="bar"><div id="bar" style="width:0%"></div></div>
    <div class="row"><span>Estimated cost</span><span id="estimate">&ndash;</span></div>
    <div class="row"><span>Charged so far (from the provider)</span><span id="actual">&ndash;</span></div>
    <div class="row"><span>Sent today</span><span id="outbound">&ndash;</span></div>
    <div class="row"><span>Day (UTC)</span><span id="day" class="muted">&ndash;</span></div>
  </section>
  <section class="card">
    <h2>Route probe</h2>
    <p class="muted" style="margin:0">Sends one frame holding every byte value to a phone on the allowlist. The app's Diagnostics screen must decode it without a CRC error before the denser alphabet is switched on.</p>
    <form id="probe"><input id="probe-number" placeholder="+447700900123" required><button type="submit">Send probe</button></form>
    <div id="result" class="muted"></div>
  </section>
  <section class="card wide">
    <h2>Recent requests</h2>
    <table><thead><tr><th>When</th><th>From</th><th>Request</th><th>Replies</th><th>State</th></tr></thead><tbody id="requests"></tbody></table>
    <p id="requests-empty" class="empty">No requests yet. Text the number from a phone on the allowlist.</p>
  </section>
  <section class="card wide">
    <h2>Documents held for paging and links</h2>
    <table><thead><tr><th>When</th><th>For</th><th>Reply</th><th>Kind</th><th>Title</th><th>Size</th></tr></thead><tbody id="documents"></tbody></table>
    <p id="documents-empty" class="empty">Nothing fetched yet.</p>
  </section>
</main>
<footer>A REX Technologies product. <span id="version"></span> &middot; refreshes every 5 seconds &middot; <a href="/healthy">/healthy</a> &middot; <a href="/ready">/ready</a> &middot; <a href="/api/overview">/api/overview</a></footer>
<script>
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
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
    $("bar").style.background = share >= 90 ? "var(--bad)" : share >= 60 ? "var(--warn)" : "var(--accent)";
    $("estimate").textContent = `~${b.estimated_cost.toFixed(2)} ${b.currency}`;
    $("actual").textContent = `${b.actual_cost.toFixed(2)} ${b.currency}`;
    $("outbound").textContent = `${data.outbound_today} SMS`;
    $("day").textContent = b.day;
    const requests = data.requests;
    $("requests-empty").style.display = requests.length ? "none" : "";
    $("requests").innerHTML = requests.map((r) => {
      const state = r.handled_at ? '<span class="pill ok">answered</span>' : '<span class="pill warn">in progress</span>';
      return `<tr><td>${when(r.received_at)}</td><td class="mono">${esc(r.number)}</td><td class="mono">${esc(r.body)}</td><td>${r.replies}</td><td>${state}</td></tr>`;
    }).join("");
    const documents = data.documents;
    $("documents-empty").style.display = documents.length ? "none" : "";
    $("documents").innerHTML = documents.map((d) =>
      `<tr><td>${when(d.created_at)}</td><td class="mono">${esc(d.number)}</td><td class="mono">${esc(d.tag)}</td><td>${esc(d.kind)}</td><td>${esc(d.title)}</td><td>${d.page_size} ${d.plain ? "plain" : "SMS"}</td></tr>`
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
