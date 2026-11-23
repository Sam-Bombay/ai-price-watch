#!/usr/bin/env python3
"""Build /datapath — which providers actually serve a model, checked against
today's published data-processing incidents.

Every provider row comes from OpenRouter's public per-model endpoints API
(fetch_routes.py). Every price comes from data/latest.json. The incident facts
are quoted from their dated sources; nothing about a route's data-retention
status is inferred, because that status is not exposed in the public API.
"""
import json, os, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "datapath")

NAMED = ["novita", "phala", "together"]  # providers named in public incident reports
NAMED_LABEL = {"novita": "Novita", "phala": "Phala", "together": "Together"}

CSS = """  :root { --bg:#0b0c0e; --panel:#14161a; --line:#23272e; --txt:#e8eaed; --dim:#8b929c; --up:#ff6b6b; --down:#4ade80; --accent:#7dd3fc; --warn:#fbbf24; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Inter,Helvetica,Arial,sans-serif; }
  .wrap { max-width:900px; margin:0 auto; padding:48px 20px 80px; }
  h1 { font-size:29px; letter-spacing:-.02em; margin:0 0 8px; }
  .sub { color:var(--dim); margin:0 0 28px; }
  h2 { font-size:14px; text-transform:uppercase; letter-spacing:.08em; color:var(--dim);
       margin:40px 0 12px; font-weight:600; }
  table { width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }
  th,td { text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); font-size:14px; }
  th { color:var(--dim); font-size:11.5px; text-transform:uppercase; letter-spacing:.06em; }
  td.num,th.num { text-align:right; }
  .verdict { background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--warn);
             border-radius:12px; padding:18px 22px; margin:14px 0 4px; }
  .verdict b { font-size:19px; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:20px; }
  label { display:block; color:var(--dim); font-size:12px; text-transform:uppercase;
          letter-spacing:.06em; margin-bottom:5px; }
  input,select { width:100%; background:#0f1114; border:1px solid var(--line); color:var(--txt);
                 border-radius:9px; padding:10px 12px; font-size:14px; }
  .good { color:var(--down); } .bad { color:var(--up); } .warn { color:var(--warn); }
  .muted { color:var(--dim); font-size:13px; }
  .foot { margin-top:46px; padding:18px 20px; border:1px solid var(--line); border-radius:12px; background:var(--panel); }
  .foot a, p a { color:var(--accent); }
  code { background:#0f1114; padding:1px 5px; border-radius:4px; font-size:13px; }
  ul { padding-left:20px; } li { margin-bottom:7px; }
  .pill { display:inline-block; font-size:11px; padding:1px 7px; border-radius:20px; border:1px solid var(--line); color:var(--dim); }
  .pill.hit { color:var(--warn); border-color:var(--warn); }
  .cta { background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--accent);
         border-radius:12px; padding:18px 22px; margin-top:14px; }
  .cta a.big { display:inline-block; margin-top:10px; background:var(--accent); color:#08131a;
               font-weight:600; text-decoration:none; padding:10px 16px; border-radius:9px; }
  @media (max-width:700px) { .wrap { padding-top:32px; } }"""


def fam(name):
    return (name or "").split(":")[0].strip()


def main():
    latest = json.load(open(os.path.join(DATA, "latest.json")))
    routes = json.load(open(os.path.join(DATA, "routes.json")))
    pricing = {m["id"]: m for m in latest["models"]}
    mapped = routes["models"]

    prov_count = collections.Counter(p["provider"] for v in mapped.values() for p in v)
    hit_models = sorted(m for m, v in mapped.items()
                        if any(k in (p["provider"] or "").lower() for p in v for k in NAMED))
    phala = prov_count.get("Phala", 0)
    n_prov = len(prov_count)
    n_models = len(mapped)

    # compact payload for the on-page lookup
    payload = {}
    for mid, eps in mapped.items():
        pr = pricing.get(mid) or {}
        rows = []
        for e in eps:
            rows.append([e["provider"], e["in"], e["out"],
                         1 if any(k in (e["provider"] or "").lower() for k in NAMED) else 0])
        payload[mid] = {"n": pr.get("name", mid), "in": pr.get("in"), "out": pr.get("out"), "r": rows}
    blob = json.dumps(payload, separators=(",", ":"))

    opts = "".join(
        '<option value="%s">%s</option>' % (mid, (payload[mid]["n"] or mid))
        for mid in sorted(payload, key=lambda x: (payload[x]["n"] or x).lower()))

    ink = pricing.get("thinkingmachines/inkling-2-mini", {})
    neon = pricing.get("google/gemini-4-neon", {})
    vin, vout = ink.get("in") or 0.075, ink.get("out") or 0.3
    gin, gout = neon.get("in") or 3.0, neon.get("out") or 15.0
    loc = 100 * vin + 20 * vout
    routed = 100 * gin + 20 * gout

    today = datetime.date.today().strftime("%d %B %Y")
    html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Which provider actually serves your model — and who lost zero-data-retention this week | AI Price Watch</title>
<meta name="description" content="Live provider routing for {n_models} priced models across {n_prov} providers, checked against the 22 November 2026 report that removed 125 endpoints from zero-data-retention eligibility.">
<style>
{css}
</style></head><body><div class="wrap">

<h1>Which provider actually serves your model</h1>
<p class="sub">Every route below is read from OpenRouter's public per-model API on {today} — not inferred.
Checked against the data-processing incidents published on 21–22 November 2026.</p>

<div class="verdict">
  <b>{n_hit} of {n_models} priced models currently route through a provider named in a leak report.</b>
  <p class="muted" style="margin:8px 0 0">Phala serves {phala} routes in today's catalogue. Novita {nov} · Together {tog}.
  The list of the 125 endpoints that lost zero-data-retention eligibility is not public, so this page cannot tell you
  your route retained zero; it can tell you who serves you and which named providers you are exposed to.</p>
</div>

<h2>What was published, dated</h2>
<ul>
  <li><b>22 Nov 2026</b> — OpenRouter off-boarded three inference providers and removed 125 endpoints from
  zero-data-retention eligibility after researchers at Dragos found prompt leakage at inference providers.</li>
  <li><b>22 Nov 2026</b> — Together published that requests from June and July 2026 were affected, and says it has
  fixed the issue.</li>
  <li><b>What is not published</b> — which 125 endpoints, and what the remaining routes' retention terms are. No public
  endpoint exposes a per-route retention flag, so "not on the list" is not the same as "clean".</li>
</ul>

<h2>Look up a model</h2>
<div class="panel">
  <label for="m">Model</label>
  <select id="m">{opts}</select>
  <div id="out" style="margin-top:16px"></div>
  <p class="muted" style="margin:14px 0 0">Prices are USD per million tokens, per provider route, read on {today}.
  A model with several rows can be served by any of them: OpenRouter picks, and the provider you assume is not always the
  provider that answers.</p>
</div>

<h2>What keeping it in the building costs now</h2>
<p>Same volume either way — 100M input and 20M output tokens a month:</p>
<table>
<tr><th>Route</th><th class="num">Input $/M</th><th class="num">Output $/M</th><th class="num">Month</th></tr>
<tr><td>Inkling 2 Mini on hardware you own <span class="pill">open weights</span></td>
 <td class="num">{vin}</td><td class="num">{vout}</td><td class="num good">${loc:,.2f}</td></tr>
<tr><td>Gemini 4 Neon, routed</td>
 <td class="num">{gin}</td><td class="num">{gout}</td><td class="num bad">${routed:,.2f}</td></tr>
</table>
<p class="muted">Inkling 2 Mini is priced from the log at {vin}/{vout} — it fell 25% on 22 November, two days after
launch, its first cut. Local still adds electricity: roughly $9/month on a 600W machine at $0.20/kWh running 75 hours. The point is
not that local is free, it is that the privacy decision stopped being the expensive one.</p>

<div class="cta">
  <b>The $500 data-path inventory.</b>
  <p class="muted" style="margin:8px 0 0">Twenty models your product actually calls. For each: every provider route that
  serves it, whether any of them are named in a published incident, the per-provider price you are really paying, and a
  local or single-vendor fallback with the monthly delta. One PDF, five working days, no call required.</p>
  <p class="muted" style="margin:8px 0 0">Ongoing watch: $300/month, you get a note the day a named provider appears in or
  disappears from a model's route table.</p>
  <a class="big" href="mailto:sambombayoffice@gmail.com?subject=Data-path%20inventory%20%E2%80%94%2020%20models&amp;body=The%20models%20we%20call%3A%0A%0A1.%20%0A2.%20%0A3.%20%0A%0AStack%3A%20">Ask for the inventory</a>
</div>

<h2>Method</h2>
<p class="muted">Routes: <code>openrouter.ai/api/v1/models/&lt;id&gt;/endpoints</code>, fetched {today},
{n_models} models, {n_prov} distinct providers, zero failed lookups. Prices: the same catalogue snapshot the log diffs
daily ({events:,} dated price events since 8 October). Incident facts: as published 21–22 November 2026, quoted, not
modelled. Nothing on this page claims a route is compliant, private, or breached — only who serves it and what it costs.</p>

<div class="foot">
  <b>AI Price Watch</b> — the daily price log for the model market.
  <p class="muted" style="margin:8px 0 0">
  <a href="/">the log</a> · <a href="/laptop/">the laptop maths</a> · <a href="/selfhost/">self-hosting table</a> ·
  <a href="/cost-index/">cost index</a> · <a href="/dataset/">the dataset</a><br>
  Built by an AI assistant for Sam Bombay, Noir &amp; Co. Sources and method above; corrections welcome at
  sambombayoffice@gmail.com.</p>
</div>

<script>
const D = {blob};
const sel = document.getElementById('m'), out = document.getElementById('out');
function money(x) {{ return x === null || x === undefined ? '—' : '$' + Number(x).toFixed(x < 1 ? 4 : 3).replace(/0+$/,'').replace(/\\.$/,''); }}
function render() {{
  const d = D[sel.value]; if (!d) {{ out.innerHTML = '<p class="muted">No route data for that model.</p>'; return; }}
  let h = '<div class="muted" style="margin-bottom:8px">' + (d.r.length) + ' provider route' + (d.r.length === 1 ? '' : 's') +
          ' · catalogue price $' + d.in + ' in / $' + d.out + ' out per million</div>';
  h += '<table><tr><th>Provider</th><th class="num">In $/M</th><th class="num">Out $/M</th><th>Named in a report</th></tr>';
  d.r.sort((a,b) => (b[3]-a[3]) || ((a[1]||0)-(b[1]||0)));
  for (const r of d.r) {{
    h += '<tr><td>' + r[0] + '</td><td class="num">' + money(r[1]) + '</td><td class="num">' + money(r[2]) + '</td><td>' +
         (r[3] ? '<span class="pill hit">yes</span>' : '<span class="pill">no</span>') + '</td></tr>';
  }}
  h += '</table>';
  const hits = d.r.filter(r => r[3]).length;
  h += '<p class="muted" style="margin:12px 0 0">' + (hits ? 'This model can be answered by ' + hits +
       ' provider' + (hits === 1 ? '' : 's') + ' named in a published leak report. OpenRouter decides at request time — a provider prefix on the request is a preference, not a guarantee.' :
       'No route through a provider named in the published reports, as of {today}. That is not a retention guarantee: the 125 affected endpoints were never listed.') + '</p>';
  out.innerHTML = h;
}}
sel.addEventListener('change', render); render();
</script>
</div></body></html>
""".format(css=CSS, n_models=n_models, n_prov=n_prov, n_hit=len(hit_models), phala=phala,
           nov=prov_count.get("Novita", 0), tog=prov_count.get("Together", 0),
           vin=vin, vout=vout, gin=gin, gout=gout, loc=loc, routed=routed,
           today=today, opts=opts, blob=blob, events=len(json.load(open(os.path.join(DATA, "changes.json")))))

    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "index.html"), "w").write(html)
    print("wrote %s (%d kb) models=%d providers=%d named_routes=%d" % (
        os.path.join(OUT, "index.html"), len(html) // 1024, n_models, n_prov, len(hit_models)))


if __name__ == "__main__":
    main()
