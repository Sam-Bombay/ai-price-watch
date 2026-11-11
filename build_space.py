#!/usr/bin/env python3
"""
Build the interactive AI Price Index as a Hugging Face Space (static, $0 forever).

Why a Space: the dataset sambombay/ai-model-price-changes already gets downloads from
analysts and tooling authors, but a CSV is a dead end — it has no link back and no
reason to be opened twice. A Space sits inside Hugging Face, where that same audience
already is, and every visit is a visit to our funnel with zero ad spend and no cold email.

Everything is baked at build time: no fetch, no API key, no runtime cost, cannot 404.
"""
import json
import os
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "space")

SITE = "https://ai-price-watch-beta.vercel.app"
MIRROR = "https://sam-bombay.github.io/ai-price-watch"


def main():
    latest = json.load(open(os.path.join(DATA, "latest.json")))
    idx = json.load(open(os.path.join(DATA, "index.json")))
    changes = json.load(open(os.path.join(DATA, "changes.json")))

    models = [m for m in latest.get("models", [])
              if isinstance(m.get("in"), (int, float)) and isinstance(m.get("out"), (int, float))]
    today = latest.get("updated")
    todays = [c for c in changes if c.get("date") == today and c.get("field") == "output"]
    todays.sort(key=lambda c: c.get("pct") or 0)

    s = idx.get("summary", {})
    series = idx.get("series", [])
    wl = s.get("workload", {})
    tin, tout = wl.get("input_tokens_month", 120_000_000), wl.get("output_tokens_month", 18_000_000)

    payload = {
        "as_of": today,
        "index": s.get("index"),
        "change_pct": s.get("change_pct_since_baseline"),
        "median": s.get("median_cost_month"),
        "cheapest": s.get("cheapest_cost_month"),
        "cheapest_name": s.get("cheapest_capable_name"),
        "p90": s.get("p90_cost_month"),
        "models": len(models),
        "panel": s.get("panel_models"),
        "events": s.get("events_logged"),
        "series": [{"d": r["date"], "i": r.get("index"), "m": r.get("median")} for r in series],
        # every model, priced on the index workload, so the page can re-rank in the browser
        "cat": sorted(
            [{"n": m["name"], "i": m["in"], "o": m["out"], "c": m.get("ctx") or 0,
              "b": round((tin / 1e6) * m["in"] + (tout / 1e6) * m["out"], 2)}
             for m in models],
            key=lambda x: x["b"]),
        "movers": [{"n": c["name"], "from": c.get("from"), "to": c.get("to"), "pct": c.get("pct")}
                   for c in todays[:12]],
        "workload": {"in": tin, "out": tout},
        "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "data.json"), "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Price Index — what the same workload costs, every day</title>
<meta name="description" content="One fixed workload, priced against every published AI model, rebuilt daily from OpenRouter's catalogue. Live index, cheapest capable model, and the price moves logged today.">
<style>
 :root{--bg:#0b0c0e;--panel:#14161a;--line:#23272e;--txt:#e8eaed;--dim:#8b929c;--up:#ff6b6b;--down:#4ade80;--acc:#7dd3fc}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Inter,Helvetica,Arial,sans-serif}
 .wrap{max-width:960px;margin:0 auto;padding:44px 20px 70px}
 h1{font-size:28px;letter-spacing:-.02em;margin:0 0 6px}
 .sub{color:var(--dim);margin:0 0 26px;font-size:14px}
 h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin:38px 0 12px;font-weight:600}
 .stats{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 8px}
 .stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 18px;flex:1;min-width:150px}
 .stat b{display:block;font-size:24px;letter-spacing:-.02em}
 .stat span{color:var(--dim);font-size:11.5px;text-transform:uppercase;letter-spacing:.06em}
 table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
 th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);font-size:14px}
 th{color:var(--dim);font-size:11.5px;text-transform:uppercase;letter-spacing:.06em}
 td.num,th.num{text-align:right}
 .cut{color:var(--down);font-weight:600}.rise{color:var(--up);font-weight:600}
 .cta{display:block;text-align:center;margin-top:12px;padding:11px;border-radius:10px;background:#e8eaed;color:#0b0c0e;font-weight:600;text-decoration:none}
 .calc{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px}
 .g{display:grid;grid-template-columns:1fr 1fr;gap:12px}
 label{display:block;color:var(--dim);font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px}
 input{width:100%;background:#0f1114;border:1px solid var(--line);color:var(--txt);border-radius:8px;padding:9px 12px;font-size:14px}
 .bar{height:9px;background:#0f1114;border-radius:5px;overflow:hidden;margin:2px 0 6px}
 .bar i{display:block;height:100%;background:var(--acc)}
 .foot{margin-top:40px;padding:18px;border:1px solid var(--line);border-radius:12px;background:var(--panel);font-size:14px}
 .foot p{margin:0 0 8px}.foot a{color:var(--acc)}
 .muted{color:var(--dim);font-size:12.5px}
 svg{width:100%;height:120px;display:block}
 @media(max-width:640px){.g{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<h1>AI Price Index</h1>
<p class="sub" id="sub">One fixed workload — 120M input / 18M output tokens a month — priced against every
published model, rebuilt daily.</p>

<div class="stats">
  <div class="stat"><b id="s-index">—</b><span>Index (8 Oct = 100)</span></div>
  <div class="stat"><b id="s-chg">—</b><span>Since baseline</span></div>
  <div class="stat"><b id="s-med">—</b><span>Median model / month</span></div>
  <div class="stat"><b id="s-cheap">—</b><span>Cheapest capable / month</span></div>
</div>
<p class="muted" id="basis">—</p>

<h2>The index, day by day</h2>
<svg id="chart" viewBox="0 0 900 120" preserveAspectRatio="none"></svg>
<p class="muted" id="chart-note">—</p>

<h2>Re-price your own workload</h2>
<div class="calc">
  <div class="g">
    <div><label>Input tokens / month (millions)</label><input id="tin" type="number" value="120" step="10"></div>
    <div><label>Output tokens / month (millions)</label><input id="tout" type="number" value="18" step="1"></div>
  </div>
  <p style="margin:16px 0 4px"><b id="you">—</b> <span class="muted">at the median model</span></p>
  <div class="bar"><i id="bar" style="width:0%"></i></div>
  <p class="muted" id="spread">—</p>
</div>
<a class="cta" id="cta" href="#">See what a re-bid of that bill is worth →</a>

<h2>Cheapest routes right now</h2>
<table id="cheap"><tr><th>Model</th><th class="num">Your cost / mo</th><th class="num">$/M out</th><th class="num">Context</th></tr></table>

<h2>Price moves logged today</h2>
<table id="movers"><tr><th>Model</th><th class="num">Was</th><th class="num">Now</th><th class="num">Change</th></tr></table>

<div class="foot">
  <p><b>Running an AI bill you have not re-bid?</b> I audit what a business actually spends on models and
  software, cut what can honestly be cut, and take 30% of the saving — no saving, no fee.
  The calculator: <a id="f-repricing" href="#">repricing</a>. The checklist: <a id="f-clinic" href="#">nine questions before you renew</a>.</p>
  <p class="muted">Built from the same daily pull that publishes
  <a href="https://huggingface.co/datasets/sambombay/ai-model-price-changes">this dataset</a>.
  Full site, including the self-host break-even: <a href="__SITE__">ai-price-watch</a>.
  Mirror if that is down: <a href="__MIRROR__">github pages</a>.
  Price source: OpenRouter public model catalogue. Throughput and self-hosting arithmetic are stated separately on the site.</p>
</div>
</div>
<script>
const D = __PAYLOAD__;
const money = x => x>=100 ? '$'+Math.round(x).toLocaleString() : '$'+x.toFixed(2);
const pct = x => (x>=0?'+':'') + x.toFixed(1) + '%';
document.getElementById('sub').innerHTML = 'One fixed workload — ' + (D.workload.in/1e6) + 'M input / ' + (D.workload.out/1e6) +
  'M output tokens a month — priced against ' + D.models + ' published models. Rebuilt daily. Last build ' + D.built + '.';
document.getElementById('s-index').textContent = D.index ? D.index.toFixed(1) : '—';
const chg = document.getElementById('s-chg');
if (D.change_pct != null) { chg.textContent = pct(D.change_pct); chg.style.color = D.change_pct>0?'var(--up)':'var(--down)'; }
document.getElementById('s-med').textContent = D.median!=null ? money(D.median) : '—';
document.getElementById('s-cheap').textContent = D.cheapest!=null ? money(D.cheapest) : '—';
document.getElementById('basis').textContent = 'Cheapest capable today: ' + (D.cheapest_name||'—') +
  '. ' + (D.events||0) + ' price changes logged since 8 Oct. Panel held fixed at ' + (D.panel||'—') + ' models so the index measures the market, not the catalogue.';

// index sparkline
(function(){
  const s = D.series.filter(r => r.i != null);
  if (s.length < 2) return;
  const min = Math.min(...s.map(r=>r.i)), max = Math.max(...s.map(r=>r.i));
  const span = (max-min) || 1;
  const pts = s.map((r,i) => [i/(s.length-1)*900, 108 - ((r.i-min)/span)*96]);
  const line = pts.map((p,i)=> (i?'L':'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
  const area = line + ' L900 120 L0 120 Z';
  document.getElementById('chart').innerHTML =
    '<path d="' + area + '" fill="rgba(125,211,252,.12)"/>' +
    '<path d="' + line + '" fill="none" stroke="#7dd3fc" stroke-width="2"/>';
  document.getElementById('chart-note').textContent = s[0].d + ' to ' + s[s.length-1].d + ', low ' +
    min.toFixed(1) + ' high ' + max.toFixed(1) + '. Rising index = the same work costs more.';
})();

// movers
(function(){
  const t = document.getElementById('movers');
  if (!D.movers.length) { t.insertAdjacentHTML('beforeend','<tr><td colspan="4" class="muted">No output-price moves logged today.</td></tr>'); return; }
  D.movers.forEach(m => {
    const c = (m.pct||0) <= 0 ? 'cut' : 'rise';
    t.insertAdjacentHTML('beforeend','<tr><td>'+m.n+'</td><td class="num">$'+m.from+'</td><td class="num">$'+m.to+'</td><td class="num '+c+'">'+pct(m.pct||0)+'</td></tr>');
  });
})();

// calculator + cheapest table
function calc(){
  const tin = Math.max(0,parseFloat(document.getElementById('tin').value)||0)*1e6;
  const tout = Math.max(0,parseFloat(document.getElementById('tout').value)||0)*1e6;
  const cost = m => (tin/1e6)*m.i + (tout/1e6)*m.o;
  const ranked = D.cat.map(m => [cost(m), m]).sort((a,b)=>a[0]-b[0]);
  const cheap = ranked[0][0], med = ranked[Math.round((ranked.length-1)/2)][0], dear = ranked[ranked.length-1][0];
  document.getElementById('you').textContent = money(med) + '/mo';
  document.getElementById('bar').style.width = Math.min(100, cheap/dear*100) + '%';
  document.getElementById('spread').textContent =
    'Cheapest route ' + money(cheap) + '/mo · median ' + money(med) + '/mo · most expensive ' + money(dear) +
    '/mo — a ' + (dear/cheap).toFixed(0) + '× spread for identical tokens.';
  const href = '__SITE__/repricing?spend=' + Math.round(med) + '&in=' + (tin/1e6) + '&out=' + (tout/1e6);
  document.getElementById('cta').href = href;
  const t = document.getElementById('cheap');
  t.querySelectorAll('tr:not(:first-child)').forEach(r=>r.remove());
  ranked.slice(0,10).forEach(([c,m]) => {
    t.insertAdjacentHTML('beforeend','<tr><td>'+m.n+'</td><td class="num">'+money(c)+'</td><td class="num">$'+(m.o).toFixed(2)+'</td><td class="num">'+(m.c/1000).toFixed(0)+'k</td></tr>');
  });
}
document.getElementById('f-repricing').href = '__SITE__/repricing';
document.getElementById('f-clinic').href = '__SITE__/clinic';
['tin','tout'].forEach(id=>document.getElementById(id).addEventListener('input',calc));
calc();
</script>
</body></html>
"""
    html = (html.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
                .replace("__SITE__", SITE).replace("__MIRROR__", MIRROR))
    with open(os.path.join(OUT, "index.html"), "w") as f:
        f.write(html)

    with open(os.path.join(OUT, "README.md"), "w") as f:
        f.write(f"""---
title: AI Price Index
emoji: 📉
colorFrom: gray
colorTo: blue
sdk: static
pinned: false
license: mit
---

# AI Price Index

One fixed workload (120M input / 18M output tokens a month) priced against every model in
OpenRouter's public catalogue, rebuilt daily. Tracks the direction of AI cost the way a CPI
tracks the direction of groceries.

Index base 100 = 8 Oct 2026. Panel held fixed so the number measures the market, not
changes in the catalogue.

- Live site: {SITE}
- Mirror: {MIRROR}
- Data: [sambombay/ai-model-price-changes](https://huggingface.co/datasets/sambombay/ai-model-price-changes)
- Built: {payload['built']}

If your AI bill has not been re-bid since these cuts, that is the arbitrage: 30% of the saving,
no saving no fee.
""")

    print(f"space built: index={payload['index']} models={payload['models']} movers={len(payload['movers'])} built={payload['built']}")


if __name__ == "__main__":
    main()
