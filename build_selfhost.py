#!/usr/bin/env python3
"""
/selfhost — does self-hosting beat paying per token, at YOUR volume?

Built 03 Nov 2026 because Revolut moving to self-hosted GLM was the top AI story on HN
and the question "should we self-host instead" is now being asked by every CFO who has
read an AI bill. The answer is arithmetic, not opinion, and nobody publishes it.

Inputs:
  - today's hosted prices from data/latest.json (fetched by fetch_prices.py)
  - published GPU rental rates (Runpod public pricing page, dated below)

What is NOT measured, and is labelled as such in the page: per-GPU throughput. We use a
stated assumption and show the sensitivity, so a reader can substitute their own number.
Nothing here is a benchmark of our own hardware.
"""
import json
import os
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "selfhost")

# Published GPU rates. Source: https://www.runpod.io/pricing, page states
# "Updated October 28, 2026", read 03 Nov 2026. Per hour, on-demand.
GPU_RATES = [
    ("RTX 4090",            24,  0.89, "24 GB - too small for a 100B+ class model"),
    ("A40",                 48,  0.59, "48 GB"),
    ("L40S",                48,  1.09, "48 GB"),
    ("A100 PCIe",           80,  1.79, "80 GB"),
    ("RTX Pro 6000",        96,  2.49, "96 GB - fits a 120B MoE at 4-bit"),
    ("H100 PCIe",           80,  2.89, "80 GB"),
    ("H100 SXM",            80,  3.99, "80 GB, faster interconnect"),
    ("H200",               141,  5.29, "141 GB"),
    ("B200",               180,  7.99, "180 GB"),
]
HOURS_MONTH = 730  # 24/7

# Stated assumptions, not measurements. Sensitivity is shown on the page.
ASSUMED_OUT_TPS = 1200   # aggregate output tokens/sec on one 80-96GB GPU, batched
ASSUMED_IN_TPS = 4000    # aggregate input (prefill) tokens/sec on the same GPU


def load_models():
    with open(os.path.join(DATA, "latest.json")) as f:
        d = json.load(f)
    return d["updated"], d.get("models", [])


def cost_month(m, tin, tout):
    return (tin / 1e6) * m["in"] + (tout / 1e6) * m["out"]


def quantile(vals, q):
    if not vals:
        return 0.0
    vals = sorted(vals)
    i = min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))
    return vals[i]


def money(x):
    if x >= 1000:
        return f"${x:,.0f}"
    if x >= 10:
        return f"${x:,.0f}" if x >= 100 else f"${x:,.2f}"
    return f"${x:,.2f}"


def main():
    updated, models = load_models()
    capable = [m for m in models
               if isinstance(m.get("in"), (int, float)) and isinstance(m.get("out"), (int, float))
               and (m.get("ctx") or 0) >= 100000 and m["in"] >= 0]

    # default workload = the index workload: a 40-person company's month
    tin, tout = 120_000_000, 18_000_000

    costs = sorted(((cost_month(m, tin, tout), m) for m in capable), key=lambda t: t[0])
    cheapest_c, cheapest_m = costs[0]
    median_c = quantile([c for c, _ in costs], 0.5)
    p90_c = quantile([c for c, _ in costs], 0.9)
    top_c, top_m = costs[-1]

    # GPU-hours this workload actually needs, at the stated throughput
    gpu_hours = (tin / ASSUMED_IN_TPS + tout / ASSUMED_OUT_TPS) / 3600.0
    duty = min(730.0, max(gpu_hours, 0.1))

    rows = []
    for name, vram, rate, note in GPU_RATES:
        always = rate * HOURS_MONTH
        burst = rate * gpu_hours
        rows.append((name, vram, rate, always, burst, note))

    # break-even: monthly hosted spend at which always-on self-hosting pays for itself
    cheapest_always = min(r[3] for r in rows if r[1] >= 80)
    cheapest_always_gpu = [r[0] for r in rows if r[3] == cheapest_always][0]
    break_even_multiple = cheapest_always / median_c if median_c else 0

    os.makedirs(OUT, exist_ok=True)
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Self-host or pay per token? The break-even, computed | AI Price Watch</title>
<meta name="description" content="Whether self-hosting an AI model is cheaper than paying per token, computed from today's published model prices and dated GPU rental rates. Batch workloads and 24/7 workloads are not the same answer.">
<style>
  :root {{ --bg:#0b0c0e; --panel:#14161a; --line:#23272e; --txt:#e8eaed; --dim:#8b929c; --up:#ff6b6b; --down:#4ade80; --accent:#7dd3fc; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt);
         font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Inter,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:900px; margin:0 auto; padding:48px 20px 80px; }}
  h1 {{ font-size:29px; letter-spacing:-.02em; margin:0 0 8px; }}
  .sub {{ color:var(--dim); margin:0 0 28px; }}
  h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.08em; color:var(--dim);
       margin:40px 0 12px; font-weight:600; }}
  table {{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }}
  th,td {{ text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); font-size:14px; }}
  th {{ color:var(--dim); font-size:11.5px; text-transform:uppercase; letter-spacing:.06em; }}
  td.num,th.num {{ text-align:right; }}
  .verdict {{ background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--accent);
             border-radius:12px; padding:18px 22px; margin:14px 0 4px; }}
  .verdict b {{ font-size:19px; }}
  .calc {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:20px; }}
  .g {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
  label {{ display:block; color:var(--dim); font-size:12px; text-transform:uppercase;
          letter-spacing:.06em; margin-bottom:5px; }}
  input,select {{ width:100%; background:#0f1114; border:1px solid var(--line); color:var(--txt);
                 border-radius:9px; padding:10px 12px; font-size:14px; }}
  .out {{ margin-top:16px; border-top:1px solid var(--line); }}
  .out .row {{ display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--line); }}
  .out .row span {{ color:var(--dim); }}
  .out .row b {{ font-variant-numeric:tabular-nums; }}
  .good {{ color:var(--down); }} .bad {{ color:var(--up); }}
  .muted {{ color:var(--dim); font-size:13px; }}
  .foot {{ margin-top:46px; padding:18px 20px; border:1px solid var(--line); border-radius:12px; background:var(--panel); }}
  .foot a, p a {{ color:var(--accent); }}
  code {{ background:#0f1114; padding:1px 5px; border-radius:4px; font-size:13px; }}
  @media (max-width:700px) {{ .g {{ grid-template-columns:1fr; }} }}
</style></head><body><div class="wrap">

<h1>Self-host, or keep paying per token?</h1>
<p class="sub">Computed {updated} from {len(capable)} hosted models with 100k+ context, against published GPU rental
rates. Two workloads, two different answers.</p>

<div class="verdict">
  <b>The short answer: it depends on whether your load is batchable.</b>
  <p class="muted" style="margin:6px 0 0">
  A 24/7 user-facing product pays for the GPU whether or not anyone is typing, so it only wins above
  roughly {money(cheapest_always)}/month of hosted spend. Batch and overnight work pays for GPU-hours only,
  and wins almost immediately. Most AI bills are a mix and nobody has separated the two — which is exactly
  where the money is.</p>
</div>

<h2>Your workload</h2>
<div class="calc">
  <div class="g">
    <div><label>Input tokens / month (millions)</label><input id="tin" type="number" value="120" step="10"></div>
    <div><label>Output tokens / month (millions)</label><input id="tout" type="number" value="18" step="1"></div>
  </div>
  <div class="g" style="margin-top:12px">
    <div><label>GPU</label><select id="gpu"></select></div>
    <div><label>Assumed throughput</label>
      <select id="tps">
        <option value="600">Conservative — 600 out tok/s</option>
        <option value="1200" selected>Typical — 1,200 out tok/s</option>
        <option value="2400">Batched hard — 2,400 out tok/s</option>
      </select></div>
  </div>
  <div class="out" id="out"></div>
  <p class="muted" style="margin:12px 0 0">Throughput is an assumption, not a measurement of your hardware or ours.
  Change it and watch the answer move — that sensitivity is the honest part of this page.</p>
</div>

<h2>Published GPU rates used</h2>
<table>
  <tr><th>GPU</th><th class="num">VRAM</th><th class="num">$/hr</th><th class="num">24/7 per month</th><th class="num">GPU-hours for the example workload</th></tr>
  {''.join(f'<tr><td>{n}</td><td class="num">{v} GB</td><td class="num">${r:.2f}</td><td class="num">{money(a)}</td><td class="num">{burst:.1f} h = {money(burst)}</td></tr>' for n, v, r, a, burst, note in rows)}
</table>
<p class="muted">Rates: Runpod public pricing page, states “Updated October 28, 2026”, read 3 Nov 2026.
GPU-hours column uses this page's default workload ({tin/1e6:.0f}M in / {tout/1e6:.0f}M out)
at 1,200 output tok/s and 4,000 input tok/s. Storage, egress, redundancy and an engineer's time are
not included — all three push the real self-hosted number up.</p>

<h2>The same workload, priced on hosted APIs</h2>
<table>
  <tr><th>Route</th><th>Model</th><th class="num">$/month</th><th class="num">× cheapest</th></tr>
  <tr><td class="good">Cheapest capable</td><td>{cheapest_m['name']}</td><td class="num">{money(cheapest_c)}</td><td class="num">1.0×</td></tr>
  <tr><td>Median</td><td class="muted">of {len(capable)} models</td><td class="num">{money(median_c)}</td><td class="num">{median_c/cheapest_c:.0f}×</td></tr>
  <tr><td>90th percentile</td><td class="muted">the “we picked a big name” bill</td><td class="num">{money(p90_c)}</td><td class="num">{p90_c/cheapest_c:.0f}×</td></tr>
  <tr><td class="bad">Most expensive</td><td>{top_m['name']}</td><td class="num">{money(top_c)}</td><td class="num">{top_c/cheapest_c:.0f}×</td></tr>
</table>
<p class="muted">Same tokens, same day, same market: a {top_c/cheapest_c:.0f}× spread between the most and least
expensive route for identical work. That spread is the entire audit offer, and it is public data.</p>

<div class="foot">
  <p><b>If the arithmetic says you are overpaying:</b> I audit what a business actually spends on AI and
  software, cut what can honestly be cut, and take 30% of what is saved — no savings, no fee.
  Enter a monthly spend and see what a re-bid is worth: <a href="/repricing">/repricing</a>.
  Nine questions to ask before you renew: <a href="/clinic/checklist">the checklist</a>.</p>
  <p class="muted">Every number on this page rebuilds from the daily price pull.
  Machine-readable source: <a href="/data/latest.json">/data/latest.json</a>,
  the log itself: <a href="https://huggingface.co/datasets/sambombay/ai-model-price-changes">Hugging Face</a>,
  the index: <a href="/cost-index/">AI Cost Index</a>.</p>
</div>
</div>
<script>
const GPUS = {json.dumps([[n, v, r] for n, v, r, a, b, note in rows])};
const HOURS = {HOURS_MONTH};
const IN_TPS = {ASSUMED_IN_TPS};
const sel = document.getElementById('gpu');
GPUS.forEach(([n, v, r]) => {{
  const o = document.createElement('option');
  o.value = String(r); o.textContent = n + ' — ' + v + ' GB — $' + r.toFixed(2) + '/hr';
  if (v >= 80 && r === Math.min(...GPUS.filter(g => g[1] >= 80).map(g => g[2]))) o.selected = true;
  sel.appendChild(o);
}});
function money(x) {{
  if (x >= 100) return '$' + Math.round(x).toLocaleString();
  return '$' + x.toFixed(2);
}}
function calc() {{
  const tin = Math.max(0, parseFloat(document.getElementById('tin').value) || 0) * 1e6;
  const tout = Math.max(0, parseFloat(document.getElementById('tout').value) || 0) * 1e6;
  const rate = parseFloat(sel.value);
  const outTps = parseFloat(document.getElementById('tps').value);
  const inTps = outTps * (IN_TPS / {ASSUMED_OUT_TPS});
  const hours = (tin / inTps + tout / outTps) / 3600;
  const always = rate * HOURS;
  const burst = rate * Math.max(hours, 0);
  document.getElementById('out').innerHTML = `
    <div class="row"><span>Self-hosted, 24/7 (one GPU)</span><b>${{money(always)}}/mo</b></div>
    <div class="row"><span>Self-hosted, batch only (${{hours.toFixed(1)}} GPU-hours)</span><b class="good">${{money(burst)}}/mo</b></div>
    <div class="row"><span>Hosted, cheapest capable model</span><b id="hc">…</b></div>
    <div class="row"><span>Hosted, median model</span><b id="hm">…</b></div>`;
  // hosted side is recomputed in-page from the same catalogue snapshot
  const MODELS = {json.dumps([[m['in'], m['out']] for m in capable])};
  const costs = MODELS.map(([a, b]) => (tin / 1e6) * a + (tout / 1e6) * b).sort((x, y) => x - y);
  const q = (p) => costs[Math.min(costs.length - 1, Math.round(p * (costs.length - 1)))];
  const c = costs[0], m = q(0.5);
  document.getElementById('hc').textContent = money(c) + '/mo';
  document.getElementById('hm').textContent = money(m) + '/mo';
  const rowsEl = document.getElementById('out');
  const verdict = document.createElement('div');
  verdict.className = 'row';
  const winner = burst < c ? 'self-host in batch mode' : (always < c ? 'self-host 24/7' : 'stay hosted');
  verdict.innerHTML = '<span>Cheaper today</span><b class="' + (winner === 'stay hosted' ? 'bad' : 'good') + '">' + winner + '</b>';
  rowsEl.appendChild(verdict);
}}
['tin', 'tout', 'tps'].forEach(id => document.getElementById(id).addEventListener('input', calc));
sel.addEventListener('change', calc);
calc();
</script>
</body></html>
"""
    with open(os.path.join(OUT, "index.html"), "w") as f:
        f.write(html)

    # small machine-readable companion so the arithmetic can be checked
    with open(os.path.join(OUT, "breakdown.json"), "w") as f:
        json.dump({
            "as_of": updated,
            "workload_default": {"input_tokens_month": tin, "output_tokens_month": tout},
            "hosted": {"cheapest": {"name": cheapest_m["name"], "usd_month": round(cheapest_c, 2)},
                        "median_usd_month": round(median_c, 2), "p90_usd_month": round(p90_c, 2),
                        "max": {"name": top_m["name"], "usd_month": round(top_c, 2)}},
            "gpu_rates": [{"gpu": n, "vram_gb": v, "usd_hr": r, "usd_month_247": round(a, 2),
                           "gpu_hours_default": round(burst / r, 2), "usd_batch_default": round(burst, 2)}
                          for n, v, r, a, burst, note in rows],
            "assumptions": {"out_tokens_per_sec_per_gpu": ASSUMED_OUT_TPS,
                            "in_tokens_per_sec_per_gpu": ASSUMED_IN_TPS,
                            "hours_per_month": HOURS_MONTH,
                            "excluded": ["storage", "egress", "redundancy", "operations labour"]},
            "gpu_rate_source": "https://www.runpod.io/pricing (page states 'Updated October 28, 2026'; read 2026-11-03)",
            "built": datetime.datetime.now().isoformat(timespec="seconds"),
        }, f, indent=1)

    print(f"selfhost built: {len(capable)} capable models, cheapest {money(cheapest_c)}, "
          f"median {money(median_c)}, always-on 80GB+ from {money(cheapest_always)} ({cheapest_always_gpu}), "
          f"batch default {money(min(r[4] for r in rows if r[1]>=80))}")


if __name__ == "__main__":
    main()
