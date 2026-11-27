#!/usr/bin/env python3
"""Build /zdr — the retention-route swap table.

For every model in today's catalogue: which provider routes serve it, which of
those were named in the 21-25 November 2026 data-processing reports, and what
the cheapest route that is NOT named costs instead. The point /datapath did not
answer: what do you do about it, and what does it cost.

Routes come from OpenRouter's public per-model endpoints API (fetch_routes.py).
Prices come from the same catalogue snapshot the daily log diffs. Nothing here
claims a route is compliant or breached — only who serves it and what it costs.
"""
import json, os, datetime, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "zdr")

# Providers named in published reports, 21-25 November 2026. Sources are quoted
# on the page; this list is evidence of naming, not of misconduct.
NAMED = ["novita", "streamlake", "ant digital", "siliconflow", "together"]
NAMED_LABEL = "Novita, StreamLake, Ant Digital, SiliconFlow, Together"

WIN, WOUT = 100, 20  # million tokens per month, the fixed comparison workload

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
  select { width:100%; background:#0f1114; border:1px solid var(--line); color:var(--txt);
           border-radius:9px; padding:10px 12px; font-size:14px; }
  .good { color:var(--down); } .bad { color:var(--up); } .warn { color:var(--warn); }
  .muted { color:var(--dim); font-size:13px; }
  .foot { margin-top:46px; padding:18px 20px; border:1px solid var(--line); border-radius:12px; background:var(--panel); }
  .foot a, p a { color:var(--accent); }
  code { background:#0f1114; padding:1px 5px; border-radius:4px; font-size:13px; }
  ul { padding-left:20px; } li { margin-bottom:7px; }
  .pill { display:inline-block; font-size:11px; padding:1px 7px; border-radius:20px; border:1px solid var(--line); color:var(--dim); }
  .pill.hit { color:var(--warn); border-color:var(--warn); }
  .kpi { display:flex; gap:12px; flex-wrap:wrap; margin:18px 0 0; }
  .kpi div { flex:1 1 150px; background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
  .kpi b { display:block; font-size:24px; letter-spacing:-.02em; }
  .kpi span { color:var(--dim); font-size:12px; }
  .cta { background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--accent);
         border-radius:12px; padding:18px 22px; margin-top:14px; }
  .cta a.big { display:inline-block; margin-top:10px; background:var(--accent); color:#08131a;
               font-weight:600; text-decoration:none; padding:10px 16px; border-radius:9px; }
  @media (max-width:700px) { .wrap { padding-top:32px; } }"""


def is_named(p):
    return any(n in (p or "").lower() for n in NAMED)


def cost(e):
    return WIN * e["in"] + WOUT * e["out"]


def main():
    latest = json.load(open(os.path.join(DATA, "latest.json")))
    routes = json.load(open(os.path.join(DATA, "routes.json")))
    pricing = {m["id"]: m for m in latest["models"]}
    mapped = routes["models"]

    hit_models, clean_models, stuck, deltas = [], [], [], []
    payload = {}
    for mid, eps in mapped.items():
        rows = [e for e in eps if e.get("in") is not None and e.get("out") is not None]
        if not rows:
            continue
        named_rows = [e for e in rows if is_named(e["provider"])]
        clean_rows = [e for e in rows if not is_named(e["provider"])]
        pr = pricing.get(mid) or {}
        entry = {
            "n": pr.get("name", mid),
            "r": [[e["provider"], e["in"], e["out"], 1 if is_named(e["provider"]) else 0] for e in rows],
            "c": None,
            "d": None,
        }
        if named_rows:
            hit_models.append(mid)
            if clean_rows:
                clean_models.append(mid)
                cheapest_all = min(rows, key=cost)
                cheapest_clean = min(clean_rows, key=cost)
                cc, ca = cost(cheapest_clean), cost(cheapest_all)
                delta = (cc - ca) / ca if ca else 0.0
                deltas.append(delta)
                entry["c"] = [cheapest_clean["provider"], cheapest_clean["in"], cheapest_clean["out"], round(cc, 4)]
                entry["d"] = round(delta, 4)
                entry["was"] = [cheapest_all["provider"], round(ca, 4)]
            else:
                stuck.append(mid)
        payload[mid] = entry

    blob = json.dumps(payload, separators=(",", ":"))
    med = statistics.median(deltas) if deltas else 0.0
    free_or_cheaper = sum(1 for d in deltas if d <= 0)
    within_quarter = sum(1 for d in deltas if 0 < d <= 0.25)
    expensive = sum(1 for d in deltas if d > 1.0)

    # models worth leading with: named route present, clean swap at no extra cost
    notable = sorted(
        (m for m in clean_models if (payload[m]["d"] or 0) <= 0),
        key=lambda m: (payload[m]["n"] or m).lower(),
    )[:14]

    opts = "".join(
        '<option value="%s">%s</option>' % (mid, (payload[mid]["n"] or mid))
        for mid in sorted(payload, key=lambda x: (payload[x]["n"] or x).lower())
    )

    today = datetime.date.today().strftime("%d %B %Y")
    fetched = routes.get("fetched") or ""
    route_day = (datetime.datetime.fromisoformat(fetched).strftime("%d %B %Y") if fetched else today)
    price_day = (datetime.date.fromisoformat(latest["updated"]).strftime("%d %B %Y")
                 if latest.get("updated") else today)
    events = len(json.load(open(os.path.join(DATA, "changes.json"))))
    n_models, n_prov = len(mapped), len({p["provider"] for v in mapped.values() for p in v})

    html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The retention route swap — {n_hit} models clear, {n_free} at no extra cost | AI Price Watch</title>
<meta name="description" content="Every provider route behind {n_models} priced models, checked against the 21-25 November 2026 data-processing reports, with the cheapest unnamed alternative and its monthly delta.">
<style>
{css}
</style></head><body><div class="wrap">

<h1>The retention route swap</h1>
<p class="sub">Every route behind {n_models} priced models, read from OpenRouter's public per-model API on {route_day},
with the cost of moving off a provider named in this week's reports.</p>

<div class="verdict">
  <b>{n_hit} of {n_models} models can be answered by a provider named in the 21-25 November reports.
  {n_free} of them can be moved to a route that is not named, at the same price or lower.</b>
  <p class="muted" style="margin:8px 0 0">Median delta across all {n_clean} swappable models: {med:+.1f}%.
  {stuck_n} models have no unnamed route at all in today's catalogue. Routes are read live; the
  reports are quoted and dated below.</p>
</div>

<div class="kpi">
  <div><b>{n_hit}</b><span>models with a named route</span></div>
  <div><b>{n_free}</b><span>swappable at no extra cost</span></div>
  <div><b>{stuck_n}</b><span>no clean route exists</span></div>
  <div><b>{med:+.1f}%</b><span>median swap delta</span></div>
</div>

<h2>What was published, dated</h2>
<ul>
  <li><b>24 Nov 2026</b> — OpenRouter's notice that requests to MiniMax models "may have been read".
  A researcher embedded unique URLs in prompts; a third party opened them 40 to 130 hours later.
  It happened on non-MiniMax providers too: AtlasCloud, Novita and StreamLake told OpenRouter they had
  forwarded OpenRouter requests for MiniMax models to MiniMax.</li>
  <li><b>25 Nov 2026</b> — a public trace of provider traffic (<code>kendell.dev/blog/arkwrapper</code>) reports
  DeepSeek tokens on routes traced to ByteDance Ark through Novita, StreamLake and Ant Digital, plus
  StreamLake returning Novita gateway errors and tool-call ids on GLM 5.3 Flash, and SiliconFlow passing
  through StreamLake request ids on DeepSeek V4.1 Flash, V4 Pro and GLM 5.</li>
  <li><b>22 Nov 2026</b> — OpenRouter off-boarded three providers and removed 125 endpoints from
  zero-data-retention eligibility. The list of those 125 was never published.</li>
  <li><b>What is still not public</b> — a per-route retention flag. Nothing on this page claims a route is
  compliant, private or breached. It shows who serves you and what the alternative costs.</li>
</ul>

<h2>Look up a model</h2>
<div class="panel">
  <label for="m">Model</label>
  <select id="m">{opts}</select>
  <div id="out" style="margin-top:16px"></div>
  <p class="muted" style="margin:14px 0 0">Monthly figures are the same fixed workload for every row:
  {win}M input and {wout}M output tokens. Prices are USD per million tokens per route, from the {price_day} catalogue.</p>
</div>

<h2>Models that clear at no extra cost ({n_free})</h2>
<p class="muted">A named route is in the table; an unnamed route is the same price or cheaper. First {notable_n} shown, alphabetical.</p>
<table>
<tr><th>Model</th><th>Named route carries</th><th>Move to</th><th class="num">Month after</th><th class="num">Delta</th></tr>
{notable_rows}
</table>

<h2>Models with no unnamed route ({stuck_n})</h2>
<p class="muted">{stuck_list}</p>

<div class="cta">
  <b>The $500 route review.</b>
  <p class="muted" style="margin:8px 0 0">Twenty models your product actually calls. For each: every route that serves it,
  which of those are named in a published report, the provider prefix to pin if you want the unnamed one, and the
  monthly delta. Five working days, one PDF, no call required. You do not need to be a client to ask; you do not
  need to buy to keep the method.</p>
  <p class="muted" style="margin:8px 0 0">Ongoing watch: $300/month — a note the day a named provider appears in or
  disappears from the route table of a model you list.</p>
  <a class="big" href="mailto:sambombayoffice@gmail.com?subject=Route%20review%20%E2%80%94%2020%20models&amp;body=The%20models%20we%20call%3A%0A%0A1.%20%0A2.%20%0A3.%20%0A%0AStack%3A%20">Ask for the review</a>
</div>

<h2>Method</h2>
<p class="muted">Routes: <code>openrouter.ai/api/v1/models/&lt;id&gt;/endpoints</code>, fetched {route_day},
{n_models} models, {n_prov} distinct providers. Prices: the {price_day} catalogue snapshot, the same one the log diffs daily
({events:,} dated events since 8 October). Delta = cheapest route not named in a report, minus cheapest route
overall, on the {win}/{wout}M workload. A negative delta means the unnamed route is cheaper. Report facts are
quoted from their published sources, not modelled.</p>

<div class="foot">
  <b>AI Price Watch</b> — the daily price log for the model market.
  <p class="muted" style="margin:8px 0 0">
  <a href="/">the log</a> · <a href="/datapath/">full route map</a> · <a href="/laptop/">the laptop maths</a> ·
  <a href="/selfhost/">self-hosting table</a> · <a href="/dataset/">the dataset</a><br>
  Built by an AI assistant for Sam Bombay, Noir &amp; Co. Sources and method above; corrections welcome at
  sambombayoffice@gmail.com.</p>
</div>

<script>
const D = {blob};
const sel = document.getElementById('m'), out = document.getElementById('out');
function money(x) {{ return (x === null || x === undefined) ? '—' : '$' + Number(x).toFixed(x < 1 ? 4 : 3).replace(/0+$/,'').replace(/\\.$/,''); }}
function pct(x) {{ return (x*100 >= 0 ? '+' : '') + (x*100).toFixed(1) + '%'; }}
function render() {{
  const d = D[sel.value]; if (!d) {{ out.innerHTML = '<p class="muted">No route data for that model.</p>'; return; }}
  const namedN = d.r.filter(r => r[3]).length;
  let h = '<div class="muted" style="margin-bottom:8px">' + d.r.length + ' provider route' + (d.r.length === 1 ? '' : 's') +
          ' · ' + namedN + ' named in a published report</div>';
  h += '<table><tr><th>Provider</th><th class="num">In $/M</th><th class="num">Out $/M</th><th>Named</th></tr>';
  d.r.sort((a,b) => (b[3]-a[3]) || ((a[1]||0)-(b[1]||0)));
  for (const r of d.r) {{
    h += '<tr><td>' + r[0] + '</td><td class="num">' + money(r[1]) + '</td><td class="num">' + money(r[2]) + '</td><td>' +
         (r[3] ? '<span class="pill hit">yes</span>' : '<span class="pill">no</span>') + '</td></tr>';
  }}
  h += '</table>';
  if (d.c) {{
    h += '<div class="verdict" style="margin-top:16px;border-left-color:' + (d.d <= 0 ? '#4ade80' : '#fbbf24') + '">' +
         '<b>Move to ' + d.c[0] + ' — ' + money(d.c[3]) + ' a month</b>' +
         '<p class="muted" style="margin:8px 0 0">Cheapest unnamed route: ' + money(d.c[1]) + ' in / ' + money(d.c[2]) + ' out. ' +
         'Cheapest route overall right now: ' + d.was[0] + ' at ' + money(d.was[1]) + ' a month. Delta ' +
         '<b class="' + (d.d <= 0 ? 'good' : 'bad') + '">' + pct(d.d) + '</b>.</p></div>';
  }} else if (namedN) {{
    h += '<div class="verdict" style="margin-top:16px"><b>No unnamed route in today\\'s catalogue.</b>' +
         '<p class="muted" style="margin:8px 0 0">Every route for this model is served by a provider named in a published report. ' +
         'If you are under a data-processing agreement, this model is a decision you have to make explicitly, not a default.</p></div>';
  }} else {{
    h += '<p class="muted" style="margin:12px 0 0">No route through a named provider in the {route_day} route table. That is not a retention guarantee — the 125 affected endpoints were never published.</p>';
  }}
  out.innerHTML = h;
}}
sel.addEventListener('change', render); render();
</script>
</div></body></html>
""".format(
        css=CSS, n_models=n_models, n_prov=n_prov, n_hit=len(hit_models), n_free=free_or_cheaper,
        n_clean=len(clean_models), stuck_n=len(stuck), med=med * 100, today=today, route_day=route_day, price_day=price_day, opts=opts, blob=blob,
        events=events, win=WIN, wout=WOUT, notable_n=len(notable_lbls := notable),
        notable_rows="".join(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td class=\"num\">$%.2f</td><td class=\"num %s\">%+.1f%%</td></tr>"
            % (payload[m]["n"] or m, payload[m]["was"][0], payload[m]["c"][0], payload[m]["c"][3],
               "good" if (payload[m]["d"] or 0) <= 0 else "bad", (payload[m]["d"] or 0) * 100)
            for m in notable),
        stuck_list=", ".join(sorted(payload[m]["n"] or m for m in stuck)) or "none in today's catalogue",
    )

    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "index.html"), "w").write(html)
    print("wrote %s (%d kb) models=%d providers=%d named=%d swappable=%d free_at_or_below=%d stuck=%d median=%+.1f%%"
          % (os.path.join(OUT, "index.html"), len(html) // 1024, n_models, n_prov, len(hit_models),
             len(clean_models), free_or_cheaper, len(stuck), med * 100))


if __name__ == "__main__":
    main()
